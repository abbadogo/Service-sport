"""Match lifecycle orchestration.

Phases:  PREMATCH -> HAND_PICKUP -> LIVE -> (flat slap) -> HAND_PICKUP -> ... -> FINISHED

* HAND_PICKUP: clock paused. The conceding team fetches the slipper and
  serves from where they picked it up; the other players return to formation.
* LIVE: clock running. Cursor players chase, sticks strike, physics steps; a
  flat slap (or a ball leaving the pitch) concedes a point to the side it died on.
* Turn delegation: the conceding side always serves next.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from service.agents.chase_controller import CursorSelection, TeamChaseController
from service.agents.player import Player, build_team
from service.agents.policies import (
    DefaultServePolicy,
    DefaultStrikePolicy,
    ServePolicy,
    StrikePolicy,
    long_hit_speed,
)
from service.core.config import MatchConfig, PhysicsConfig, StaminaConfig, StrikeConfig
from service.core.types import PITCH_LENGTH_M, PITCH_WIDTH_M, TEAM_SIZE, Team, Vec2, clamp
from service.court.boundary_referee import BoundaryReferee, HandPickupTransition, ServeRequest
from service.engine.events import (
    CursorChanged,
    MatchEnded,
    MatchEndReason,
    MatchEvent,
    MatchMode,
    MatchPhase,
    PhaseChanged,
    PointReason,
    PointScored,
    ServeFault,
    ServeLaunched,
    StrikeMade,
    StrikeMishit,
    SuddenDeathStarted,
    SwingMissed,
    TeamRotated,
    ZoneCorrection,
)
from service.engine.human import HumanInput
from service.engine.match_clock import MatchClock, PauseReason
from service.physics.forecast import BallForecaster
from service.physics.gyroscopic_engine import GyroscopicEngine, StepStatus, StrikeImpulse, TireBall

_PITCH_BOUNDS = (0.0, PITCH_LENGTH_M, 0.0, PITCH_WIDTH_M)


@dataclass(slots=True)
class Score:
    a: int = 0
    b: int = 0

    def get(self, team: Team) -> int:
        return self.a if team is Team.A else self.b

    def add(self, team: Team) -> None:
        if team is Team.A:
            self.a += 1
        else:
            self.b += 1


@dataclass(frozen=True, slots=True)
class MatchResult:
    winner: Team | None
    reason: MatchEndReason
    score_a: int
    score_b: int
    sim_time_s: float
    live_time_s: float
    paused_time_s: float
    overtime_s: float
    duration_clamped: bool
    events: tuple[MatchEvent, ...] = field(repr=False, default=())


class ServiceMatch:
    SERVE_COOLDOWN_S = 0.8
    STRIKE_COOLDOWN_S = 0.5
    SERVE_RELEASE_OFFSET_M = 0.4

    def __init__(self, config: MatchConfig | None = None,
                 physics_config: PhysicsConfig | None = None,
                 stamina_config: StaminaConfig | None = None,
                 strike_config: StrikeConfig | None = None,
                 referee: BoundaryReferee | None = None,
                 serve_policy: ServePolicy | None = None,
                 strike_policy: StrikePolicy | None = None,
                 selection: CursorSelection = CursorSelection.NEAREST_DISTANCE,
                 human_team: Team | None = None) -> None:
        self.config = config or MatchConfig()
        self.human_team = human_team  # that team's nearest player is driven by HumanInput
        seed = self.config.seed
        self._dt = self.config.dt
        self.referee = referee or BoundaryReferee()
        self.clock = MatchClock(self.config.duration_minutes)  # validates / clamps
        self.engine = GyroscopicEngine(physics_config, seed=seed * 7919 + 1)
        self.stamina_cfg = stamina_config or StaminaConfig()
        self.strike_cfg = strike_config or StrikeConfig()
        self.serve_policy: ServePolicy = serve_policy or DefaultServePolicy(random.Random(seed * 7919 + 2))
        self.strike_policy: StrikePolicy = strike_policy or DefaultStrikePolicy(
            random.Random(seed * 7919 + 3), self.strike_cfg, self.engine)

        roster_rng = random.Random(seed * 7919 + 4)
        self.squads: dict[Team, list[Player]] = {
            t: build_team(t, roster_rng, self.stamina_cfg) for t in Team}
        self.players: dict[str, Player] = {p.pid: p for s in self.squads.values() for p in s}
        self._all: list[Player] = list(self.players.values())
        for p in self._all:
            p.power_bar.rate = 1.0 / self.strike_cfg.charge_time_s

        self.forecaster = BallForecaster(self.engine, bounds=_PITCH_BOUNDS)
        self.controllers: dict[Team, TeamChaseController] = {
            t: TeamChaseController(t, self.referee, self.forecaster, selection,
                               rng=random.Random(seed * 7919 + 5 + i))
            for i, t in enumerate(Team)}

        self.phase = MatchPhase.PREMATCH
        self.mode = MatchMode.REGULATION
        self.score = Score()
        self.ball: TireBall | None = None
        self.server_team: Team = self.config.opening_server
        self.sim_time = 0.0
        self.event_log: list[MatchEvent] = []
        self.result: MatchResult | None = None

        self._pickup: HandPickupTransition | None = None
        self._serve_faults = 0
        self._last_striker: Team | None = None
        self._crossed = True
        self._strikes_since_serve = 0
        self._last_side: Team = Team.A
        self._out: list[MatchEvent] = []
        self._rng = random.Random(seed * 7919 + 6)  # mishits

    # ============================================================ public API
    def start(self) -> None:
        if self.phase is not MatchPhase.PREMATCH:
            raise RuntimeError("match already started")
        team = self.config.opening_server
        spot = self.referee.default_serve_spot(team)
        self._begin_pickup(team, spot, already_holding=True)

    def step(self, human: HumanInput | None = None) -> list[MatchEvent]:
        """Advance one fixed tick. Returns the events emitted during it."""
        if self.phase is MatchPhase.PREMATCH:
            raise RuntimeError("call start() first")
        if self.phase is MatchPhase.FINISHED:
            return []
        self._out = []
        dt = self._dt
        self.sim_time += dt
        for p in self._all:
            p.tick_timers(dt)
        if self.phase is MatchPhase.HAND_PICKUP:
            self._step_pickup(dt)
        else:
            self._step_live(dt, human)
        if self.phase is not MatchPhase.FINISHED and self.sim_time >= self.config.max_sim_seconds:
            self._finish(None, MatchEndReason.ABORTED)
        return self._out

    def run(self) -> MatchResult:
        if self.phase is MatchPhase.PREMATCH:
            self.start()
        while self.phase is not MatchPhase.FINISHED:
            self.step()
        assert self.result is not None
        return self.result

    def snapshot(self) -> dict:
        b = self.ball
        return {
            "phase": self.phase.name, "mode": self.mode.name,
            "clock": self.clock.display, "score": (self.score.a, self.score.b),
            "server": self.server_team.value,
            "cursors": {t.value: self.controllers[t].cursor_id for t in Team},
            "ball": None if b is None else {
                "x": round(b.x, 2), "y": round(b.y, 2), "speed": round(b.speed, 2),
                "tilt_deg": round(b.tilt_deg, 1), "flat": b.is_flat},
        }

    # =============================================================== helpers
    def _emit(self, cls: type[MatchEvent], **kw: Any) -> MatchEvent:
        ev = cls(sim_time=self.sim_time, clock=self.clock.display, **kw)
        self._out.append(ev)
        self.event_log.append(ev)
        return ev

    def _set_phase(self, new: MatchPhase) -> None:
        old, self.phase = self.phase, new
        self._emit(PhaseChanged, old=old, new=new)

    def _enforce_zones(self) -> None:
        for v in self.referee.enforce_zones(self._all):
            self._emit(ZoneCorrection, player_id=v.pid)

    def _can_strike(self, team: Team) -> bool:
        if not self.config.require_crossing_between_team_strikes:
            return True
        return self._last_striker is not team or self._crossed

    # ================================================================ pickup
    def _begin_pickup(self, team: Team, ball_pos: Vec2, already_holding: bool = False) -> None:
        target = self.referee.zone(team).clamp(ball_pos)
        picker = min(self.squads[team], key=lambda p: p.pos.distance_to(target))
        self._pickup = HandPickupTransition(
            team, picker.pid, ball_pos, self.referee,
            timeout_s=self.config.pickup_timeout_s,
            serve_spot=picker.pos if already_holding else None)
        if self.config.rotate_after_point and not already_holding:
            self._rotate(team)
        self.server_team = team
        self._serve_faults = 0
        for c in self.controllers.values():
            c.reset()
        self.clock.pause(PauseReason.HAND_PICKUP)
        self._set_phase(MatchPhase.HAND_PICKUP)

    def _rotate(self, team: Team) -> None:
        """Volleyball-style: every player moves to the next position slot. Identities
        stay the same; the dead-ball movement walks everyone to their new spot."""
        for p in self.squads[team]:
            p.slot = (p.slot + 1) % TEAM_SIZE
        self._emit(TeamRotated, team=team)

    def _step_pickup(self, dt: float) -> None:
        tr = self._pickup
        assert tr is not None
        picker = self.players[tr.picker_id]
        self.clock.tick(dt)  # paused: only diagnostics accumulate
        tr.advance(picker, dt)
        for team, ctl in self.controllers.items():
            ex = frozenset({picker.pid}) if team is tr.team else frozenset()
            ctl.update_dead_ball(self.squads[team], dt, ex)
        self._enforce_zones()
        if tr.is_ready:
            self._attempt_serve()

    def _attempt_serve(self) -> None:
        tr = self._pickup
        assert tr is not None
        team = tr.team
        server = self.players[tr.picker_id]
        intent = self.serve_policy.decide(server)
        h = intent.heading.normalized()
        launch_pos = server.pos + h * self.SERVE_RELEASE_OFFSET_M
        req = ServeRequest(team, server.pid, server.pos, launch_pos, intent.launch_z,
                           h, intent.speed, intent.lean_rad, intent.crouched and server.crouched)
        verdict = self.referee.validate_serve(req, self.server_team)
        if not verdict.ok:
            self._serve_faults += 1
            self._emit(ServeFault, team=team, server_id=server.pid,
                       faults=tuple(f.name for f in verdict.faults),
                       fault_count=self._serve_faults)
            if self._serve_faults >= self.config.max_serve_faults:
                self._award_point(team.opponent, team, PointReason.SERVE_FAULTS, server.pos, server.pid)
                if self.phase is MatchPhase.FINISHED:
                    return
                self._pickup = HandPickupTransition(
                    team, server.pid, server.pos, self.referee,
                    timeout_s=self.config.pickup_timeout_s, serve_spot=server.pos)
                self._serve_faults = 0
            return

        self.ball = self.engine.launch(launch_pos, h, intent.speed, intent.lean_rad, intent.launch_z)
        server.crouched = False
        server.strike_cooldown = self.SERVE_COOLDOWN_S
        self._last_striker, self._crossed, self._last_side = team, False, team
        self._strikes_since_serve = 0
        for p in self._all:
            p.power_bar.cancel()
        self._pickup = None
        for c in self.controllers.values():
            c.reset()
        self.forecaster.invalidate()
        self.clock.resume()
        self._emit(ServeLaunched, team=team, server_id=server.pid, speed=intent.speed,
                   lean_deg=math.degrees(intent.lean_rad))
        self._set_phase(MatchPhase.LIVE)

    # ================================================================== live
    def _step_live(self, dt: float, human: HumanInput | None = None) -> None:
        ball = self.ball
        assert ball is not None
        expired = self.clock.tick(dt)

        for team, ctl in self.controllers.items():
            if team is self.human_team:
                before = ctl.cursor_id
                squad = self.squads[team]
                move = Vec2(human.move_x, human.move_y) if human else Vec2(0.0, 0.0)
                ctl.update_human(squad, ball, dt, move, lock=any(p.power_bar.charging for p in squad))
                if ctl.cursor_id != before:
                    self._emit(CursorChanged, team=team, player_id=ctl.cursor_id)
            elif ctl.update_live(self.squads[team], ball, self.sim_time, dt, self._can_strike(team)):
                self._emit(CursorChanged, team=team, player_id=ctl.cursor_id)
        self._enforce_zones()
        self._update_charging(ball, dt)
        if self.human_team is not None:
            self._human_swing(human, ball, dt)
        self._resolve_strikes(ball)

        status = self.engine.step(ball, dt)
        side = self.referee.side_of(ball.x, self._last_side)
        if self._last_striker is not None and side is self._last_striker.opponent:
            self._crossed = True
        self._last_side = side

        if status is StepStatus.FLAT_SLAP:
            self._dead_ball(side, PointReason.FLAT_SLAP, ball)
        elif self.referee.ball_out_of_bounds(ball.x, ball.y):
            if self.config.out_of_bounds_concedes:
                ball.out_of_play = True
                self._dead_ball(side, PointReason.OUT_OF_BOUNDS, ball)
            else:
                self._reflect(ball)

        if expired and self.phase is MatchPhase.LIVE:
            self._resolve_expiry(ball_live=True)

    @staticmethod
    def _reflect(ball: TireBall) -> None:
        if ball.x < 0.0 or ball.x > PITCH_LENGTH_M:
            ball.x = min(max(ball.x, 0.0), PITCH_LENGTH_M)
            ball.hx = -ball.hx
        if ball.y < 0.0 or ball.y > PITCH_WIDTH_M:
            ball.y = min(max(ball.y, 0.0), PITCH_WIDTH_M)
            ball.hy = -ball.hy
        ball.speed *= 0.7
        ball.revision += 1

    def _update_charging(self, ball: TireBall, dt: float) -> None:
        """Players who can strike hold their power bar while the ball is in wind-up range."""
        rng_m = self.strike_cfg.windup_range_m
        for p in self._all:
            if p.team is self.human_team:
                continue
            eligible = p.strike_cooldown <= 0.0 and self._can_strike(p.team)
            if eligible and math.hypot(p.pos.x - ball.x, p.pos.y - ball.y) <= rng_m:
                if not p.power_bar.charging:
                    p.power_bar.press(self.strike_policy.choose_charge_target(p, ball))
                p.power_bar.update(dt)
            elif p.power_bar.charging:
                p.power_bar.cancel()

    def _resolve_strikes(self, ball: TireBall) -> None:
        cands: list[tuple[float, Player]] = []
        for p in self._all:
            if p.team is self.human_team or p.strike_cooldown > 0.0 or not self._can_strike(p.team):
                continue
            d = math.hypot(p.pos.x - ball.x, p.pos.y - ball.y)
            if d <= p.reach:
                cands.append((d, p))
        cands.sort(key=lambda c: c[0])
        for _, p in cands:
            if not self.referee.validate_strike(p, ball.x, ball.y, ball.is_live).ok:
                continue
            level = p.power_bar.release(self.strike_cfg.min_level)
            impulse = self.strike_policy.decide(p, ball, self.squads[p.team.opponent], level)
            self._execute_strike(p, ball, impulse, level)
            break  # at most one strike per tick

    def _human_swing(self, human: HumanInput | None, ball: TireBall, dt: float) -> None:
        """Hold the button to charge the power bar; releasing it swings."""
        assert self.human_team is not None
        cid = self.controllers[self.human_team].cursor_id
        p = self.players.get(cid) if cid else None
        if p is None:
            return
        bar = p.power_bar
        held = human is not None and human.charge
        if held and p.strike_cooldown <= 0.0 and self._can_strike(p.team):
            if not bar.charging:
                bar.press(1.0)
            bar.update(dt)
        elif bar.charging:
            self._swing(p, ball, bar.release(self.strike_cfg.min_level), human)

    def _swing(self, p: Player, ball: TireBall, level: float, human: HumanInput | None) -> None:
        if not self.referee.validate_strike(p, ball.x, ball.y, ball.is_live).ok:
            p.strike_cooldown = self.STRIKE_COOLDOWN_S  # swung at nothing
            self._emit(SwingMissed, team=p.team, player_id=p.pid)
            return
        aim = Vec2(human.aim_x, human.aim_y) if human else Vec2(0.0, 0.0)
        sign = p.team.forward_sign
        if aim.length_sq() < 1e-6:
            aim = Vec2(sign, 0.0)
        forward = sign * max(aim.x * sign, 0.3 * aim.length())  # never strike backwards
        quality = clamp(0.65 + 0.35 * p.speed_factor, 0.0, 1.0)
        err = self._rng.gauss(0.0, self.strike_cfg.aim_error_for(level) + 0.04 * (1.0 - quality))
        impulse = StrikeImpulse(Vec2(forward, aim.y).normalized().rotated(err),
                                self.strike_cfg.speed_for(level) * p.strength,
                                DefaultStrikePolicy.RECOVER_MAX_RAD * quality, 0.0)
        self._execute_strike(p, ball, impulse, level)

    def _execute_strike(self, p: Player, ball: TireBall, impulse: StrikeImpulse, level: float) -> None:
        """Apply a strike: the mishit and long-hit rules, bookkeeping and events (AI and human alike)."""
        c = self.strike_cfg
        mishit = self._rng.random() < c.mishit_probability(ball.speed, p.speed_factor)
        long_hit = not mishit and level >= c.long_hit_level
        if long_hit:  # aimed to die deep in the opponent's end, short of the baseline
            impulse = StrikeImpulse(
                impulse.direction.rotated(self._rng.gauss(0.0, c.long_hit_aim_error_rad)),
                long_hit_speed(p.team, ball.x, impulse.direction, c.long_hit_depth_m),
                impulse.tilt_recovery, impulse.lean_kick)
            p.spend_stamina(c.long_hit_stamina_cost)
        if mishit:  # a weak dribble in the wrong direction
            impulse = StrikeImpulse(
                impulse.direction.rotated(self._rng.gauss(0.0, c.mishit_aim_error_rad)),
                self._rng.uniform(c.mishit_min_speed, c.mishit_max_speed), 0.0, 0.0)
        before = ball.tilt_deg
        self.engine.apply_strike(ball, impulse)
        p.strike_cooldown = self.STRIKE_COOLDOWN_S
        p.spend_stamina(self.stamina_cfg.strike_cost)
        p.strikes += 1
        self._strikes_since_serve += 1
        self._last_striker, self._crossed = p.team, False
        if mishit:
            self._emit(StrikeMishit, team=p.team, player_id=p.pid, speed=impulse.speed)
        self._emit(StrikeMade, team=p.team, player_id=p.pid, speed=impulse.speed,
                   tilt_before_deg=before, tilt_after_deg=ball.tilt_deg, power=level, long_hit=long_hit)

    # ============================================================== scoring
    def _dead_ball(self, side: Team, reason: PointReason, ball: TireBall) -> None:
        conceding = side  # the side the ball died on concedes...
        if (reason is PointReason.FLAT_SLAP and self._strikes_since_serve == 0
                and side is self.server_team):
            reason = PointReason.LAZY_SERVE  # serve never crossed: server's fault
        chaser = self.controllers[conceding].cursor_id
        self._award_point(conceding.opponent, conceding, reason, ball.position, chaser)
        if self.phase is MatchPhase.FINISHED:
            return
        if self.clock.state.name == "EXPIRED" and not self.clock.in_overtime:
            self._resolve_expiry(ball_live=False)
            if self.phase is MatchPhase.FINISHED:
                return
        self._begin_pickup(conceding, ball.position)  # ...and serves next

    def _award_point(self, scorer: Team, conceded_by: Team, reason: PointReason,
                     pos: Vec2, chaser_id: str | None) -> None:
        self.score.add(scorer)
        stamina = self.players[chaser_id].stamina if chaser_id else None
        self._emit(PointScored, scorer=scorer, conceded_by=conceded_by, reason=reason,
                   position=pos, score_a=self.score.a, score_b=self.score.b,
                   chaser_id=chaser_id, chaser_stamina=stamina)
        self.clock.pause(PauseReason.HAND_PICKUP)  # freeze the timer immediately
        if self.mode is MatchMode.SUDDEN_DEATH:
            self._finish(scorer, MatchEndReason.SUDDEN_DEATH_POINT)

    def _resolve_expiry(self, ball_live: bool) -> None:
        if self.score.a != self.score.b:
            winner = Team.A if self.score.a > self.score.b else Team.B
            self._finish(winner, MatchEndReason.CLOCK_EXPIRED)
            return
        self.clock.begin_overtime(ball_live)
        self.mode = MatchMode.SUDDEN_DEATH
        self._emit(SuddenDeathStarted, score_a=self.score.a, score_b=self.score.b)

    def _finish(self, winner: Team | None, reason: MatchEndReason) -> None:
        self.clock.pause(PauseReason.OTHER)
        self._emit(MatchEnded, winner=winner, reason=reason,
                   score_a=self.score.a, score_b=self.score.b)
        self._set_phase(MatchPhase.FINISHED)
        self.result = MatchResult(
            winner, reason, self.score.a, self.score.b, self.sim_time,
            self.clock.live_elapsed_s, self.clock.paused_elapsed_s, self.clock.overtime_s,
            self.clock.resolution.clamped, tuple(self.event_log))
