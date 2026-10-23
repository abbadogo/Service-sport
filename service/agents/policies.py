"""Pluggable decision policies (serve + strike). Swap for scripted/ML agents."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Protocol, Sequence

from service.agents.player import Player
from service.core.config import StrikeConfig
from service.core.types import (
    MIDLINE_X_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Team,
    Vec2,
    clamp,
)
from service.physics.gyroscopic_engine import GyroscopicEngine, StrikeImpulse, TireBall


@dataclass(frozen=True, slots=True)
class ServeIntent:
    heading: Vec2
    speed: float
    lean_rad: float
    launch_z: float = 0.0
    crouched: bool = True


class ServePolicy(Protocol):
    def decide(self, server: Player) -> ServeIntent:
        ...


class StrikePolicy(Protocol):
    def choose_charge_target(self, striker: Player, ball: TireBall) -> float:
        ...

    def decide(self, striker: Player, ball: TireBall, opponents: Sequence[Player],
               level: float) -> StrikeImpulse:
        ...


def long_hit_speed(team: Team, ball_x: float, direction: Vec2, depth_m: float) -> float:
    """Speed that makes the disc die about ``depth_m`` short of the opponent's baseline.
    Uses the flat-pitch roll rule of thumb (distance is about 7.9 * v - 10 m)."""
    room = (PITCH_LENGTH_M - ball_x - depth_m) if team is Team.A else (ball_x - depth_m)
    forward = max(direction.normalized().x * team.forward_sign, 0.4)
    dist = max(room, 15.0) / forward
    return clamp((dist * 1.05 + 10.0) / 7.9, 5.5, 16.0)


def _depth_x(team: Team, frac: float) -> float:
    """X at ``frac`` (0..1) of the way into the opponent half from the midline."""
    half = MIDLINE_X_M
    return MIDLINE_X_M + half * frac if team is Team.A else MIDLINE_X_M - half * frac


class DefaultServePolicy:
    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def decide(self, server: Player) -> ServeIntent:
        r = self._rng
        x_t = _depth_x(server.team, r.uniform(0.1, 0.5))
        # Keep the aim inside a ~48 degree cone so the serve stays legal and still reaches the midline.
        max_dy = abs(x_t - server.pos.x) * 1.1
        y_t = clamp(r.uniform(22.0, 46.0), server.pos.y - max_dy, server.pos.y + max_dy)
        heading = (Vec2(x_t, y_t) - server.pos).normalized()
        # Rule: a serve must always cross the midline, from anywhere in the server's half.
        # Roll distance is roughly 7.9 * v - 10 m on the flat pitch. Cover the distance to the
        # midline plus 12-30 m of forward progress, lengthened for the angle and 10% for the curve.
        forward = max(heading.x * server.team.forward_sign, 0.5)
        progress = abs(MIDLINE_X_M - server.pos.x) * 1.10 + r.uniform(12.0, 30.0)
        speed = clamp((progress / forward + 10.0) / 7.9, 4.0, 15.0)
        lean = math.radians(r.uniform(1.0, 3.0)) * r.choice((-1.0, 1.0))
        return ServeIntent(heading, speed, lean)


class DefaultStrikePolicy:
    """AI striker: picks how long to hold the bar, aims at the emptiest lane.
    Strike speed comes straight off the power-bar level; harder = less accurate."""

    RECOVER_MAX_RAD = math.radians(30.0)

    def __init__(self, rng: random.Random, cfg: StrikeConfig | None = None,
                 engine: GyroscopicEngine | None = None, curve_skill: float = 0.0) -> None:
        self.curve_skill = curve_skill  # 0 = ignores the bevel curve, 1 = corrects it perfectly
        self._rng = rng
        self.cfg = cfg or StrikeConfig()
        self._engine = engine  # lets the striker correct for the bevel's curve

    # Empirical roll distance on the flat pitch: roughly 7.9 * v - 10 metres.
    ROLL_SLOPE, ROLL_OFFSET = 7.9, 10.0
    LONG_HIT_CHANCE = 0.12   # how often the AI goes for a long hit (a full bar)
    OVERPOWER = 1.10         # tolerance over the "just reaches the baseline" level

    def choose_charge_target(self, striker: Player, ball: TireBall) -> float:
        """How long to hold the bar. Ambition is random, but a sensible striker
        stops short of launching the ball over the far baseline."""
        r = self._rng
        ambition = r.triangular(0.4, 1.0, 0.8) * (0.8 + 0.2 * striker.speed_factor)
        if r.random() < self.LONG_HIT_CHANCE and striker.stamina > 0.3:
            return 1.0  # a long hit lands deep by design, so no baseline cap
        ambition = min(ambition, self.cfg.long_hit_level - 0.01)  # an ordinary strike
        x = 0.5 * (striker.pos.x + ball.x)
        room = (PITCH_LENGTH_M - x) if striker.team is Team.A else x  # metres to the far baseline
        v_safe = (room * 0.95 + self.ROLL_OFFSET) / self.ROLL_SLOPE
        span = self.cfg.max_speed - self.cfg.min_speed
        lv_safe = clamp((v_safe - self.cfg.min_speed) / span * self.OVERPOWER, 0.15, 1.0)
        return min(ambition, lv_safe)

    def decide(self, striker: Player, ball: TireBall, opponents: Sequence[Player],
               level: float) -> StrikeImpulse:
        r = self._rng
        team = striker.team
        x_t = _depth_x(team, r.uniform(0.25, 0.85))
        # Players know the bevel slices every ball to its left, so they aim a little to the right.
        lo, hi = (10.0, 44.0) if team is Team.A else (PITCH_WIDTH_M - 44.0, PITCH_WIDTH_M - 10.0)
        cands = [r.uniform(lo, hi) for _ in range(4)]
        y_t = max(cands, key=lambda y: min(abs(y - o.pos.y) for o in opponents))
        d = Vec2(x_t - ball.x, y_t - ball.y)

        quality = clamp(0.65 + 0.35 * striker.speed_factor, 0.0, 1.0)
        if d.x * team.forward_sign < 0.2 * d.length():  # never strike backwards
            d = Vec2(team.forward_sign * max(abs(d.x), 1.0), d.y)
        speed = self.cfg.speed_for(level) * striker.strength
        kick = math.radians(r.uniform(0.0, 2.5)) * r.choice((-1.0, 1.0))
        recover = self.RECOVER_MAX_RAD * quality
        target = Vec2(x_t, y_t)
        d = self.compensate_curve(ball, d.normalized(), speed, recover, kick, target)
        err = r.gauss(0.0, self.cfg.aim_error_for(level) + 0.04 * (1.0 - quality))
        return StrikeImpulse(d.rotated(err).normalized(), speed, recover, kick)

    def compensate_curve(self, ball: TireBall, d: Vec2, speed: float, recover: float,
                         kick: float, target: Vec2, skill: float | None = None) -> Vec2:
        """Aim off-line so the ball comes to rest in the chosen lane.

        The bevel bends every roll the same way and the bend tightens as the ball
        slows, so a straight shot ends at the touchline. We simulate the strike,
        compare where it would die with the lane we want, and rotate the aim."""
        eng = self._engine
        if eng is None:
            return d
        origin = ball.position
        for _ in range(3):
            sim = ball.copy()
            eng.apply_strike(sim, StrikeImpulse(d, speed, recover, kick))
            end = eng.predict(sim, 10.0, 1 / 20).points[-1]
            got = (Vec2(end.x, end.y) - origin).angle()
            want = (Vec2(end.x, target.y) - origin).angle()
            d = d.rotated((want - got) * (self.curve_skill if skill is None else skill))
        return d
