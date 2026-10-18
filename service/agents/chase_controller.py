"""Per-team cursor AI.

Each side always has at most one *cursor* player: the teammate closest to the
ball. The cursor is free to roam anywhere in their own half to intercept the
ball before it falls flat; everyone else holds a foosball-style lane. If the
cursor is exhausted or too slow, nothing rescues them: the ball goes flat on
their side and the team concedes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

from service.agents.formation import guard_position, home_position
from service.agents.player import Player
from service.court.boundary_referee import BoundaryReferee, Zone
from service.core.types import MIDLINE_X_M, Team, Vec2
from service.physics.forecast import BallForecaster
from service.physics.gyroscopic_engine import TireBall


class CursorSelection(Enum):
    NEAREST_DISTANCE = auto()  # default: closeness to the ball
    FASTEST_ARRIVAL = auto()   # fatigue-aware alternative


@dataclass(frozen=True, slots=True)
class InterceptPlan:
    target: Vec2
    eta_s: float          # time the player needs to get within reach
    slack_s: float        # ball time-to-target minus eta (>= 0 means reachable)
    reachable: bool
    intensity: float


class TeamChaseController:
    GUARD_INTENSITY = 0.55
    DEAD_BALL_INTENSITY = 0.6
    ZONE_MARGIN_M = 1.0
    MIN_STRIKE_DEPTH_M = 8.0  # prefer to meet the ball this far inside our half (room to wind up)

    def __init__(self, team: Team, referee: BoundaryReferee, forecaster: BallForecaster,
                 selection: CursorSelection = CursorSelection.NEAREST_DISTANCE,
                 switch_margin_m: float = 1.5, hold_time_s: float = 0.3,
                 rng: random.Random | None = None, pick_margin_m: float = 2.0) -> None:
        self.team = team
        self._zone: Zone = referee.zone(team)
        self._forecaster = forecaster
        self.selection = selection
        self._margin = switch_margin_m
        self._rng = rng or random.Random(0)
        self._pick_margin = pick_margin_m
        self._hold = hold_time_s
        self._hold_left = 0.0
        self.cursor_id: str | None = None
        self.last_plan: InterceptPlan | None = None

    def reset(self) -> None:
        self.cursor_id = None
        self._hold_left = 0.0
        self.last_plan = None

    # ----------------------------------------------------------- live play
    def update_live(self, players: Sequence[Player], ball: TireBall, now: float,
                    dt: float, can_strike: bool) -> bool:
        """Move every player for one tick. Returns True if the cursor changed."""
        zone = self._zone
        traj = self._forecaster.get(ball, now)
        age = now - traj.computed_at
        in_zone = [(p.t - age, Vec2(p.x, p.y)) for p in traj.points
                   if p.t >= age and zone.contains(Vec2(p.x, p.y), self.ZONE_MARGIN_M)]
        engaged = can_strike and ball.is_live and (
            zone.contains(ball.position, self.ZONE_MARGIN_M) or bool(in_zone))

        prev = self.cursor_id
        self._hold_left = max(0.0, self._hold_left - dt)
        if not engaged:
            self.cursor_id, self.last_plan = None, None
            for p in players:
                p.move_toward(guard_position(self.team, p.slot, ball.y), dt, self.GUARD_INTENSITY)
            return prev is not None

        cursor = self._select_cursor(players, ball, in_zone)
        self.cursor_id = cursor.pid
        plan = self._plan(cursor, in_zone, ball)
        self.last_plan = plan
        for p in players:
            if p is cursor:
                p.move_toward(plan.target, dt, plan.intensity)
            else:
                p.move_toward(guard_position(self.team, p.slot, ball.y), dt, self.GUARD_INTENSITY)
        return cursor.pid != prev

    def _select_cursor(self, players: Sequence[Player], ball: TireBall,
                       in_zone: list[tuple[float, Vec2]]) -> Player:
        """Automatic hand-off. The cursor always moves to whoever is nearest;
        when several players are about equally close, one is picked at random."""
        ref = self._zone.clamp(ball.position)
        cur = next((p for p in players if p.pid == self.cursor_id), None)
        if self.selection is CursorSelection.FASTEST_ARRIVAL:
            def key(p: Player) -> float:
                plan = self._plan(p, in_zone, ball)
                return plan.eta_s + (0.0 if plan.reachable else 1000.0)
            best = min(players, key=key)
            if cur is None or (best is not cur and self._hold_left <= 0.0 and key(best) < key(cur) - 0.1):
                self._hold_left = self._hold
                return best
            return cur
        dist = {p.pid: p.pos.distance_to(ref) for p in players}
        best = min(players, key=lambda p: dist[p.pid])
        near = [p for p in players if dist[p.pid] <= dist[best.pid] + self._pick_margin]
        if cur is None or cur not in near:
            # No cursor yet, or the current one has fallen clearly behind: hand off now.
            self._hold_left = self._hold
            return self._rng.choice(near) if cur is None else best
        if self._hold_left <= 0.0 and len(near) > 1 and self._rng.random() < 0.5:
            self._hold_left = self._hold
            return self._rng.choice(near)  # random hand-off among near-equals
        return cur

    def _plan(self, p: Player, in_zone: list[tuple[float, Vec2]], ball: TireBall) -> InterceptPlan:
        speed = max(p.current_max_speed, 1e-6)
        best: InterceptPlan | None = None
        earliest: InterceptPlan | None = None
        for t_rel, pt in in_zone:
            eta = max(0.0, p.pos.distance_to(pt) - 0.8 * p.reach) / speed
            slack = t_rel - eta
            if slack >= 0.0:
                lazy = eta <= 0.6 * max(t_rel, 1e-3)
                plan = InterceptPlan(pt, eta, slack, True, 0.65 if lazy else 1.0)
                if abs(pt.x - MIDLINE_X_M) >= self.MIN_STRIKE_DEPTH_M:
                    return plan  # reachable and deep enough to wind up
                if earliest is None:
                    earliest = plan
                continue
            if best is None or slack > best.slack_s:
                best = InterceptPlan(pt, eta, slack, False, 1.0)
        if earliest is not None:
            return earliest  # ball never gets deep enough: take it as early as we can
        if best is not None:
            return best
        target = self._zone.clamp(ball.position)
        return InterceptPlan(target, p.pos.distance_to(target) / speed, 0.0, False, 1.0)

    # ------------------------------------------------------------ dead ball
    def update_dead_ball(self, players: Sequence[Player], dt: float, exclude: frozenset[str]) -> None:
        self.cursor_id, self.last_plan = None, None
        for p in players:
            if p.pid in exclude:
                continue
            p.move_toward(home_position(self.team, p.slot), dt, self.DEAD_BALL_INTENSITY)
