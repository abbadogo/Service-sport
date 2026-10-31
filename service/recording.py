"""Record a whole match into a compact, JSON-friendly replay (used by the API and scripts)."""

from __future__ import annotations

from typing import Any

from service.core.types import Team
from service.engine.events import (
    MatchEnded,
    MatchEvent,
    MatchPhase,
    PointReason,
    PointScored,
    ServeLaunched,
    StrikeMade,
    StrikeMishit,
    SuddenDeathStarted,
    SwingMissed,
    TeamRotated,
)
from service.engine.state_machine import ServiceMatch

# Frame layout: HEAD fields, then PLAYER_FIELDS for each player in `players` order.
FRAME_HEAD = ["t", "phase", "clock", "score_a", "score_b", "cursor_a", "cursor_b",
              "ball_x", "ball_y", "ball_tilt", "ball_flat", "ball_hx", "ball_hy"]
PLAYER_FIELDS = ["x", "y", "stamina", "power"]
PHASES = {p.name: p.value for p in MatchPhase}
_WHY = {PointReason.FLAT_SLAP: "falls flat", PointReason.OUT_OF_BOUNDS: "goes out",
        PointReason.SERVE_FAULTS: "serve faults", PointReason.LAZY_SERVE: "lazy serve dies short"}


def frame_of(m: ServiceMatch, ids: list[str]) -> list[float]:
    b = m.ball
    cursors = [m.controllers[t].cursor_id for t in Team]
    clock = round(m.clock.remaining_s, 1) if not m.clock.in_overtime else -round(m.clock.overtime_s, 1)
    row: list[float] = [
        round(m.sim_time, 2), m.phase.value, clock, m.score.a, m.score.b,
        ids.index(cursors[0]) if cursors[0] else -1, ids.index(cursors[1]) if cursors[1] else -1,
        round(b.x, 2) if b else -1, round(b.y, 2) if b else -1, round(b.tilt_deg, 1) if b else 0,
        int(bool(b and b.is_flat)), round(b.hx, 2) if b else 0, round(b.hy, 2) if b else 0,
    ]
    for p in (m.players[i] for i in ids):
        row += [round(p.pos.x, 2), round(p.pos.y, 2), round(p.stamina, 2), round(p.power_bar.level, 2)]
    return row


def result_of(match: ServiceMatch) -> dict[str, Any]:
    r = match.result
    assert r is not None, "match has not finished"
    return {"score_a": r.score_a, "score_b": r.score_b,
            "winner": r.winner.value if r.winner else None, "reason": r.reason.name,
            "sim_time_s": round(r.sim_time_s, 1), "live_time_s": round(r.live_time_s, 1)}


def describe_event(e: MatchEvent) -> dict[str, Any] | None:
    """A short log entry for notable events, or None for the ones the log leaves out."""
    t = round(e.sim_time, 2)
    if isinstance(e, PointScored):
        who = "no chaser"
        if e.chaser_id and e.chaser_stamina is not None:
            who = f"{e.chaser_id}, stamina {e.chaser_stamina:.0%}"
        text = (f"{e.scorer.value} scores: ball {_WHY[e.reason]} on "
                f"{e.conceded_by.value}'s side ({who})  {e.score_a}-{e.score_b}")
        return {"t": t, "kind": "point", "text": text}
    if isinstance(e, ServeLaunched):
        return {"t": t, "kind": "serve", "text": f"{e.team.value} serves from their half (Z=0)"}
    if isinstance(e, StrikeMade) and e.long_hit:
        return {"t": t, "kind": "longhit", "text": f"{e.player_id} plays a long hit"}
    if isinstance(e, TeamRotated):
        return {"t": t, "kind": "rotate", "text": f"Team {e.team.value} rotates positions"}
    if isinstance(e, StrikeMishit):
        return {"t": t, "kind": "mishit", "text": f"{e.player_id} mishits the ball"}
    if isinstance(e, SwingMissed):
        return {"t": t, "kind": "mishit", "text": f"{e.player_id} swings and misses"}
    if isinstance(e, SuddenDeathStarted):
        return {"t": t, "kind": "sd", "text": f"Tied at 00:00: sudden death ({e.score_a}-{e.score_b})"}
    if isinstance(e, MatchEnded):
        why = e.reason.name.replace("_", " ").lower()
        return {"t": t, "kind": "end", "text": f"Final: {e.score_a}-{e.score_b}, {why}"}
    return None


def record_match(match: ServiceMatch, every_ticks: int = 12) -> dict[str, Any]:
    """Run ``match`` (not yet started) to the end and return a replay dictionary."""
    if every_ticks < 1:
        raise ValueError("every_ticks must be >= 1")
    ids = [p.pid for p in match._all]
    match.start()
    frames = [frame_of(match, ids)]
    events: list[dict[str, Any]] = []
    tick = 0
    while match.phase is not MatchPhase.FINISHED:
        for e in match.step():
            d = describe_event(e)
            if d is not None:
                events.append(d)
        tick += 1
        if tick % every_ticks == 0 or match.phase is MatchPhase.FINISHED:
            frames.append(frame_of(match, ids))
    res = match.clock.resolution
    named = {p.pid: {"name": p.name, "shirt": p.shirt} for p in match._all if p.name}
    out: dict[str, Any] = {
        "schema": {"head": FRAME_HEAD, "player_fields": PLAYER_FIELDS, "phases": PHASES},
        "players": ids, "frames": frames, "events": events,
        "result": result_of(match),
        "duration": {"requested": res.requested, "effective": res.effective, "clamped": res.clamped},
    }
    if named:  # only matches played with squads carry names, so older replays are unchanged
        out["profiles"] = named
        out["squads"] = {t.value: n for t, n in match.squad_names.items()}
    return out
