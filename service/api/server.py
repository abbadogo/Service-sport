"""HTTP server: GET /api/health, GET /api/settings, POST /api/matches.

Standard library only. Input is validated here (never trusted from the browser);
errors are returned as JSON ``{"error": {"code", "message"}}`` and unexpected
failures are logged server-side with a generic message to the client.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from service import __version__
from service.api.errors import ApiError
from service.api.logging_setup import configure_logging
from service.api.metrics import Metrics
from service.api.play import SessionStore
from service.api.settings import SettingsError, build_configs, match_fields, public_specs
from service.core.config import MatchConfig
from service.core.types import Team
from service.engine.human import HumanInput
from service.engine.match_clock import resolve_duration
from service.engine.state_machine import ServiceMatch
from service.recording import record_match

log = logging.getLogger("service.api")

MAX_BODY_BYTES = 16_384
MAX_SIM_SECONDS = 900.0  # server-side safety limit; clients cannot raise it
MAX_CONCURRENT_MATCHES = 2
MAX_SEED = 2**31 - 1
_slots = threading.BoundedSemaphore(MAX_CONCURRENT_MATCHES)


@dataclass(frozen=True)
class MatchRequest:
    minutes: float | None = None
    seed: int = 1
    opening_server: Team = Team.A
    settings: dict[str, Any] = field(default_factory=dict)
    side: Team = Team.A  # live play: the team the human controls


def parse_match_request(payload: object) -> MatchRequest:
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_request", "request body must be a JSON object")
    extra = set(payload) - {"minutes", "seed", "opening_server", "settings", "side"}
    if extra:
        raise ApiError(400, "invalid_request", f"unknown field(s): {', '.join(sorted(extra))}")

    minutes = payload.get("minutes")
    if minutes is not None:
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes):
            raise ApiError(400, "invalid_minutes", "minutes must be a finite number")
        try:
            resolve_duration(minutes)
        except ValueError as exc:
            raise ApiError(400, "invalid_minutes", str(exc)) from exc

    seed = payload.get("seed", 1)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise ApiError(400, "invalid_seed", f"seed must be an integer between 0 and {MAX_SEED}")

    opening = payload.get("opening_server", "A")
    if opening not in ("A", "B"):
        raise ApiError(400, "invalid_opening_server", "opening_server must be 'A' or 'B'")

    side = payload.get("side", "A")
    if side not in ("A", "B"):
        raise ApiError(400, "invalid_side", "side must be 'A' or 'B'")

    settings = payload.get("settings", {})
    if not isinstance(settings, dict):
        raise ApiError(400, "invalid_settings", "settings must be an object")
    return MatchRequest(minutes, seed, Team(opening), settings, Team(side))


def run_match(req: MatchRequest) -> dict[str, Any]:
    try:
        physics, strike, stamina = build_configs(req.settings)
        rules = match_fields(req.settings)
    except SettingsError as exc:
        raise ApiError(400, "invalid_settings", str(exc)) from exc
    config = MatchConfig(duration_minutes=req.minutes, seed=req.seed, opening_server=req.opening_server,
                         max_sim_seconds=MAX_SIM_SECONDS, **rules)
    if not _slots.acquire(blocking=False):
        raise ApiError(503, "busy", "the server is running other matches; try again shortly")
    try:
        replay = record_match(ServiceMatch(config, physics_config=physics, strike_config=strike,
                                           stamina_config=stamina))
        METRICS.count("matches_run")
        return replay
    finally:
        _slots.release()


STORE = SessionStore()
METRICS = Metrics()
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{8,32}")
_KNOWN_ROUTES = {"/api/health", "/api/settings", "/api/metrics", "/api/matches", "/api/play"}
_PLAY_ROUTE = re.compile(r"/api/play/[A-Za-z0-9_-]{8,32}(/step)?")


def route_of(path: str) -> str:
    """A safe name for the route, never the raw path: session ids are secrets and junk paths are untrusted."""
    path = path.split("?", 1)[0]
    if path in _KNOWN_ROUTES:
        return path
    m = _PLAY_ROUTE.fullmatch(path)
    if m:
        return "/api/play/{id}/step" if m.group(1) else "/api/play/{id}"
    return "unknown"


def start_play(req: MatchRequest) -> dict[str, Any]:
    try:
        physics, strike, stamina = build_configs(req.settings)
        rules = match_fields(req.settings)
    except SettingsError as exc:
        raise ApiError(400, "invalid_settings", str(exc)) from exc
    config = MatchConfig(duration_minutes=req.minutes, seed=req.seed, opening_server=req.opening_server,
                         max_sim_seconds=MAX_SIM_SECONDS, **rules)
    match = ServiceMatch(config, physics_config=physics, strike_config=strike,
                         stamina_config=stamina, human_team=req.side)
    session_id, session = STORE.create(match, req.side)
    METRICS.count("live_sessions_started")
    return {"session": session_id, **session.start_payload()}


def parse_input(payload: object) -> HumanInput:
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_request", "request body must be a JSON object")
    extra = set(payload) - {"move", "aim", "charge"}
    if extra:
        raise ApiError(400, "invalid_request", f"unknown field(s): {', '.join(sorted(extra))}")

    def vector(name: str) -> tuple[Any, Any]:
        v = payload.get(name, [0, 0])
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ApiError(400, "invalid_input", f"{name} must be [x, y]")
        return v[0], v[1]

    (mx, my), (ax, ay) = vector("move"), vector("aim")
    try:
        return HumanInput(mx, my, ax, ay, payload.get("charge", False))
    except ValueError as exc:
        raise ApiError(400, "invalid_input", str(exc)) from exc


class Handler(BaseHTTPRequestHandler):
    server_version = "SabisLab/" + __version__

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        log.debug("%s - %s", self.address_string(), format % args)

    _rid = "-"
    _status = 500
    _method = "-"
    _route = "unknown"
    _started = 0.0

    def _send(self, status: int, body: dict[str, Any]) -> None:
        self._status = status
        # Record the request BEFORE the reply goes out, so that by the time a client has its response the
        # log line and the metrics already include it (the other order races with whoever reads them next).
        ms = (time.monotonic() - self._started) * 1000.0
        METRICS.observe_request(status, ms)
        log.info("request rid=%s method=%s route=%s status=%d ms=%.1f",
                 self._rid, self._method, self._route, status, ms,
                 extra={"rid": self._rid, "method": self._method, "route": self._route,
                        "status": status, "ms": round(ms, 1)})
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-Id", self._rid)
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send(status, {"error": {"code": code, "message": message, "request_id": self._rid}})

    def _handle(self, method: str) -> None:
        self._rid = uuid.uuid4().hex[:12]
        self._status = 500
        self._method = method
        self._route = route_of(self.path)
        self._started = time.monotonic()
        try:
            path = self.path.split("?", 1)[0]
            if path == "/api/health":
                self._allow(method, "GET")
                self._send(200, {"status": "ok", "version": __version__})
            elif path == "/api/metrics":
                self._allow(method, "GET")
                self._send(200, METRICS.snapshot(active_sessions=len(STORE)))
            elif path == "/api/settings":
                self._allow(method, "GET")
                self._send(200, {"settings": public_specs()})
            elif path == "/api/matches":
                self._allow(method, "POST")
                self._send(200, run_match(parse_match_request(self._read_json())))
            elif path == "/api/play":
                self._allow(method, "POST")
                self._send(200, start_play(parse_match_request(self._read_json())))
            elif path.startswith("/api/play/"):
                self._handle_play(method, path)
            else:
                raise ApiError(404, "not_found", "no such endpoint")
        except ApiError as exc:
            self._error(exc.status, exc.code, exc.message)
        except Exception:  # noqa: BLE001 - last-resort guard; details go to the log, not the client
            log.exception("unhandled error", extra={"rid": self._rid, "method": method, "route": self._route})
            self._error(500, "internal_error", "something went wrong on the server")

    def _handle_play(self, method: str, path: str) -> None:
        parts = path.split("/")  # ["", "api", "play", <id>, "step"?]
        sid = parts[3] if len(parts) > 3 else ""
        if not _SESSION_ID.fullmatch(sid) or len(parts) > 5:
            raise ApiError(404, "not_found", "no such endpoint")
        tail = parts[4] if len(parts) == 5 else None
        if tail == "step":
            self._allow(method, "POST")
            session = STORE.get(sid)
            self._send(200, session.advance(parse_input(self._read_json()), STORE.clock()))
        elif tail is None:
            self._allow(method, "DELETE")
            STORE.delete(sid)
            self._send(200, {"deleted": True})
        else:
            raise ApiError(404, "not_found", "no such endpoint")

    @staticmethod
    def _allow(method: str, expected: str) -> None:
        if method != expected:
            raise ApiError(405, "method_not_allowed", f"use {expected} for this endpoint")

    def _read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError(400, "invalid_request", "bad Content-Length header") from exc
        if length < 0:
            raise ApiError(400, "invalid_request", "bad Content-Length header")
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "too_large", f"request body must be at most {MAX_BODY_BYTES} bytes")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ApiError(400, "invalid_json", "request body is not valid JSON") from exc

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._handle("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle("DELETE")


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="service-api", description="Run the Sabis Lab API server.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--log-format", choices=["text", "json"], default="text",
                   help="text, or one JSON object per line")
    args = p.parse_args(argv)
    configure_logging(args.log_format)
    server = make_server(args.host, args.port)
    log.info("Sabis Lab API listening on http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
    return 0
