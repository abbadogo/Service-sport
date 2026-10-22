"""Live matches with a human player: one session per player, advanced in real time by the API.

The browser sends its controls a few times a second; each request advances the match by the real
time that has passed since the previous one (capped), so the game keeps its pace whatever the
network delay is.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from typing import Any

from service.api.errors import ApiError
from service.core.types import Team
from service.engine.events import MatchPhase
from service.engine.human import HumanInput
from service.engine.state_machine import ServiceMatch
from service.recording import FRAME_HEAD, PHASES, PLAYER_FIELDS, describe_event, frame_of, result_of

MAX_SESSIONS = 8
IDLE_TTL_S = 300.0
MAX_CATCHUP_S = 0.25  # never simulate more than this per request: a slow client cannot stall the server


class PlaySession:
    def __init__(self, match: ServiceMatch, team: Team, now: float) -> None:
        match.start()
        self.match = match
        self.team = team
        self.ids = [p.pid for p in match._all]
        self.touched = now
        self._last = now
        self._acc = 0.0
        self._lock = threading.Lock()

    def start_payload(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": {"head": FRAME_HEAD, "player_fields": PLAYER_FIELDS, "phases": PHASES},
                "players": self.ids, "side": self.team.value,
                "frame": frame_of(self.match, self.ids),
            }

    def advance(self, inp: HumanInput, now: float) -> dict[str, Any]:
        """Advance by the real time since the last call, applying ``inp`` throughout."""
        with self._lock:
            self.touched = now
            self._acc += min(max(now - self._last, 0.0), MAX_CATCHUP_S)
            self._last = now
            dt = self.match.config.dt
            ticks = int(self._acc / dt)
            self._acc -= ticks * dt
            events: list[dict[str, Any]] = []
            for _ in range(ticks):
                if self.match.phase is MatchPhase.FINISHED:
                    break
                for e in self.match.step(inp):
                    d = describe_event(e)
                    if d is not None:
                        events.append(d)
            finished = self.match.phase is MatchPhase.FINISHED
            out: dict[str, Any] = {"frame": frame_of(self.match, self.ids), "events": events,
                                   "finished": finished, "ticks": ticks}
            if finished:
                out["result"] = result_of(self.match)
            return out


class SessionStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 max_sessions: int = MAX_SESSIONS, ttl_s: float = IDLE_TTL_S) -> None:
        self.clock = clock
        self._max = max_sessions
        self._ttl = ttl_s
        self._items: dict[str, PlaySession] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for sid in [k for k, s in self._items.items() if now - s.touched > self._ttl]:
            del self._items[sid]

    def create(self, match: ServiceMatch, team: Team) -> tuple[str, PlaySession]:
        with self._lock:
            now = self.clock()
            self._purge(now)
            if len(self._items) >= self._max:
                raise ApiError(503, "busy", "too many live matches right now; try again shortly")
            session = PlaySession(match, team, now)
            sid = secrets.token_urlsafe(12)
            self._items[sid] = session
            return sid, session

    def get(self, sid: str) -> PlaySession:
        with self._lock:
            self._purge(self.clock())
            session = self._items.get(sid)
        if session is None:
            raise ApiError(404, "no_such_match", "that live match does not exist or has expired")
        return session

    def delete(self, sid: str) -> None:
        with self._lock:
            if self._items.pop(sid, None) is None:
                raise ApiError(404, "no_such_match", "that live match does not exist or has expired")

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
