"""Court authority: zones, midline ban, serve/strike legality, hand pickup.

The referee never imports concrete player classes; it talks to anything that
satisfies the ``PlayerLike`` protocol, keeping the court layer independent of
the agents layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Protocol

from service.core.types import (
    MIDLINE_X_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Team,
    Vec2,
)


class PlayerLike(Protocol):
    pid: str
    team: Team
    pos: Vec2
    reach: float
    crouched: bool

    def move_toward(self, target: Vec2, dt: float, intensity: float = 1.0) -> float:
        ...

    def rest(self, dt: float) -> None:
        ...


class FaultCode(Enum):
    # Serve faults
    SERVER_WRONG_TEAM = auto()
    SERVER_OUTSIDE_OWN_HALF = auto()
    SERVER_NOT_CROUCHED = auto()
    SERVE_NOT_AT_GROUND_LEVEL = auto()  # launch Z must be 0
    SERVE_BALL_OUTSIDE_ZONE = auto()
    SERVE_WRONG_DIRECTION = auto()
    SERVE_SPEED_OUT_OF_RANGE = auto()
    SERVE_LEAN_TOO_LARGE = auto()
    # Strike faults
    STRIKE_BALL_DEAD = auto()
    STRIKE_OUT_OF_REACH = auto()
    STRIKE_PLAYER_OUT_OF_ZONE = auto()
    STRIKE_BALL_ON_OPPONENT_SIDE = auto()  # the ball must be struck on your own side


@dataclass(frozen=True, slots=True)
class Verdict:
    faults: tuple[FaultCode, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.faults


@dataclass(frozen=True, slots=True)
class Zone:
    """A team's rectangular territory. The midline X is shared by both."""

    team: Team
    x_min: float
    x_max: float
    y_min: float = 0.0
    y_max: float = PITCH_WIDTH_M

    def contains(self, p: Vec2, margin: float = 0.0) -> bool:
        return (self.x_min - margin <= p.x <= self.x_max + margin
                and self.y_min - margin <= p.y <= self.y_max + margin)

    def clamp(self, p: Vec2) -> Vec2:
        return Vec2(min(max(p.x, self.x_min), self.x_max),
                    min(max(p.y, self.y_min), self.y_max))


@dataclass(frozen=True, slots=True)
class ServeRequest:
    team: Team
    server_id: str
    server_position: Vec2
    launch_position: Vec2
    launch_z: float
    heading: Vec2
    speed: float
    lean_rad: float
    crouched: bool


@dataclass(frozen=True, slots=True)
class ZoneViolation:
    pid: str
    attempted: Vec2
    corrected: Vec2


@dataclass(frozen=True, slots=True)
class RefereeRules:
    z_tolerance: float = 1e-9
    serve_launch_offset_max_m: float = 1.0
    serve_max_angle_deg: float = 60.0
    serve_min_speed: float = 3.0
    serve_max_speed: float = 16.0
    serve_max_lean_deg: float = 25.0
    serve_line_margin_m: float = 0.5  # the release point must stay this far from the midline


class BoundaryReferee:
    """Single source of truth for what is legal on the pitch."""

    def __init__(self, rules: RefereeRules | None = None) -> None:
        self.rules = rules or RefereeRules()
        self._zones = {
            Team.A: Zone(Team.A, 0.0, MIDLINE_X_M),
            Team.B: Zone(Team.B, MIDLINE_X_M, PITCH_LENGTH_M),
        }

    # ------------------------------------------------------------- geometry
    def zone(self, team: Team) -> Zone:
        return self._zones[team]

    @staticmethod
    def side_of(x: float, fallback: Team | None = None) -> Team:
        """Which half an X coordinate lies in. Exactly on the line -> fallback."""
        if x < MIDLINE_X_M:
            return Team.A
        if x > MIDLINE_X_M:
            return Team.B
        return fallback if fallback is not None else Team.A

    @staticmethod
    def ball_out_of_bounds(x: float, y: float) -> bool:
        return not (0.0 <= x <= PITCH_LENGTH_M and 0.0 <= y <= PITCH_WIDTH_M)

    def serve_zone(self, team: Team) -> Zone:
        """Where a serve may be taken from: anywhere in the team's own half, kept a
        small margin back from the midline so the release point stays in the half."""
        z, m = self._zones[team], self.rules.serve_line_margin_m
        if team is Team.A:
            return Zone(team, z.x_min, z.x_max - m, z.y_min, z.y_max)
        return Zone(team, z.x_min + m, z.x_max, z.y_min, z.y_max)

    def default_serve_spot(self, team: Team) -> Vec2:
        """Opening-serve position: the centre of the team's own half."""
        cx = MIDLINE_X_M / 2.0 if team is Team.A else PITCH_LENGTH_M - MIDLINE_X_M / 2.0
        return Vec2(cx, PITCH_WIDTH_M / 2.0)

    # ------------------------------------------------------ midline ban
    def clamp_player_position(self, team: Team, pos: Vec2) -> Vec2:
        return self._zones[team].clamp(pos)

    def enforce_zones(self, players: Iterable[PlayerLike]) -> list[ZoneViolation]:
        """Hard-correct any player outside their zone. Safety net: movement
        code already clamps targets, so this should normally return []."""
        out: list[ZoneViolation] = []
        for p in players:
            fixed = self._zones[p.team].clamp(p.pos)
            if fixed.x != p.pos.x or fixed.y != p.pos.y:
                out.append(ZoneViolation(p.pid, p.pos, fixed))
                p.pos = fixed
        return out

    # --------------------------------------------------------------- serve
    def validate_serve(self, req: ServeRequest, expected_team: Team) -> Verdict:
        r = self.rules
        faults: list[FaultCode] = []
        if req.team is not expected_team:
            faults.append(FaultCode.SERVER_WRONG_TEAM)
        if not self._zones[req.team].contains(req.server_position):
            faults.append(FaultCode.SERVER_OUTSIDE_OWN_HALF)
        if not req.crouched:
            faults.append(FaultCode.SERVER_NOT_CROUCHED)
        if not math.isfinite(req.launch_z) or abs(req.launch_z) > r.z_tolerance:
            faults.append(FaultCode.SERVE_NOT_AT_GROUND_LEVEL)
        zone = self._zones[req.team]
        if (not zone.contains(req.launch_position)
                or req.launch_position.distance_to(req.server_position)
                > r.serve_launch_offset_max_m):
            faults.append(FaultCode.SERVE_BALL_OUTSIDE_ZONE)
        h = req.heading.normalized()
        min_cos = math.cos(math.radians(r.serve_max_angle_deg))
        if h.length_sq() == 0.0 or h.x * req.team.forward_sign < min_cos:
            faults.append(FaultCode.SERVE_WRONG_DIRECTION)
        if not (r.serve_min_speed <= req.speed <= r.serve_max_speed):
            faults.append(FaultCode.SERVE_SPEED_OUT_OF_RANGE)
        if abs(req.lean_rad) > math.radians(r.serve_max_lean_deg):
            faults.append(FaultCode.SERVE_LEAN_TOO_LARGE)
        return Verdict(tuple(faults))

    # -------------------------------------------------------------- strike
    def validate_strike(self, player: PlayerLike, ball_x: float, ball_y: float,
                        ball_is_live: bool, reach_bonus: float = 0.0) -> Verdict:
        faults: list[FaultCode] = []
        if not ball_is_live:
            faults.append(FaultCode.STRIKE_BALL_DEAD)
        if not self._zones[player.team].contains(player.pos):
            faults.append(FaultCode.STRIKE_PLAYER_OUT_OF_ZONE)
        if not (self._zones[player.team].x_min <= ball_x <= self._zones[player.team].x_max):
            faults.append(FaultCode.STRIKE_BALL_ON_OPPONENT_SIDE)
        if math.hypot(player.pos.x - ball_x, player.pos.y - ball_y) > player.reach + reach_bonus:
            faults.append(FaultCode.STRIKE_OUT_OF_REACH)
        return Verdict(tuple(faults))


class PickupPhase(Enum):
    WALK_TO_BALL = auto()
    PICKING_UP = auto()
    READY = auto()  # server is crouched in their own half, ready to serve


class HandPickupTransition:
    """Dead-ball state: the conceding team fetches the flat slipper by hand, then
    serves from wherever in their own half they picked it up. The match clock must
    stay paused for the whole transition."""

    PICKUP_RADIUS_M = 0.6
    WALK_INTENSITY = 0.8

    def __init__(self, team: Team, picker_id: str, ball_rest: Vec2,
                 referee: BoundaryReferee, pickup_duration_s: float = 1.0,
                 timeout_s: float = 90.0, serve_spot: Vec2 | None = None) -> None:
        """``serve_spot`` given means the server already holds the ball (opening
        serve, or a re-serve) and is ready immediately."""
        self.team = team
        self.picker_id = picker_id
        self.referee = referee
        # The slipper may have died out of bounds; fetch it at the nearest legal point.
        self.ball_target = referee.zone(team).clamp(ball_rest)
        self.pickup_duration_s = pickup_duration_s
        self.timeout_s = timeout_s
        self.elapsed = 0.0
        self.forced = False
        self._pickup_timer = 0.0
        self.serve_spot: Vec2 | None = None
        if serve_spot is not None:
            self.serve_spot = referee.serve_zone(team).clamp(serve_spot)
            self.phase = PickupPhase.READY
        else:
            self.phase = PickupPhase.WALK_TO_BALL

    @property
    def is_ready(self) -> bool:
        return self.phase is PickupPhase.READY

    def _become_ready(self, picker: PlayerLike) -> None:
        spot = self.serve_spot or self.referee.serve_zone(self.team).clamp(picker.pos)
        self.serve_spot = spot
        picker.pos = spot
        picker.crouched = True  # crouched stance for the serve
        self.phase = PickupPhase.READY

    def advance(self, picker: PlayerLike, dt: float) -> PickupPhase:
        if self.phase is PickupPhase.READY:
            if self.serve_spot is not None and picker.pos != self.serve_spot:
                picker.pos = self.serve_spot
            picker.crouched = True
            picker.rest(dt)
            return self.phase
        self.elapsed += dt
        if self.elapsed > self.timeout_s:  # liveness guard
            picker.pos = self.ball_target
            self._become_ready(picker)
            self.forced = True
            return self.phase

        if self.phase is PickupPhase.WALK_TO_BALL:
            picker.move_toward(self.ball_target, dt, self.WALK_INTENSITY)
            if picker.pos.distance_to(self.ball_target) <= self.PICKUP_RADIUS_M:
                self.phase = PickupPhase.PICKING_UP
                picker.crouched = True
        else:  # PICKING_UP
            picker.rest(dt)
            self._pickup_timer += dt
            if self._pickup_timer >= self.pickup_duration_s:
                self._become_ready(picker)
        return self.phase
