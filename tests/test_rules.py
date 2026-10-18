"""Rule-level tests: configuration validation, out-of-bounds scoring, serves, regressions."""
import math
import random
import unittest

from service.agents.player import build_team
from service.agents.policies import DefaultServePolicy, long_hit_speed
from service.core.config import MatchConfig, PhysicsConfig, StaminaConfig, StrikeConfig
from service.core.types import Team, Vec2
from service.court import BoundaryReferee, ServeRequest
from service.engine import ClockState, MatchPhase, ServiceMatch
from service.engine.events import PointReason, PointScored, StrikeMade, StrikeMishit, TeamRotated
from service.physics import GyroscopicEngine


class ConfigValidationTests(unittest.TestCase):
    def test_match_config_rejects_bad_values(self):
        for kw in ({"tick_hz": 5}, {"max_serve_faults": 0}, {"pickup_timeout_s": 0},
                   {"max_sim_seconds": 0}, {"max_sim_seconds": float("inf")}):
            with self.assertRaises(ValueError, msg=str(kw)):
                MatchConfig(**kw)

    def test_physics_config_rejects_bad_values(self):
        for kw in ({"radius_m": 0}, {"gravity": -1}, {"v_collapse": 5.0, "v_stable": 3.0},
                   {"taper_angle_deg": 60}, {"taper_handedness": 0}, {"flat_threshold_deg": 120}):
            with self.assertRaises(ValueError, msg=str(kw)):
                PhysicsConfig(**kw)

    def test_other_configs_reject_bad_values(self):
        with self.assertRaises(ValueError):
            StaminaConfig(fresh_threshold=0)
        with self.assertRaises(ValueError):
            StrikeConfig(charge_time_s=0)
        with self.assertRaises(ValueError):
            StrikeConfig(min_speed=10, max_speed=5)


class OutOfBoundsRuleTests(unittest.TestCase):
    """A ball leaving the pitch scores against the side it left on (same as a flat slap)."""

    def _live_match(self) -> ServiceMatch:
        m = ServiceMatch(MatchConfig(seed=1))
        m.start()
        for _ in range(120 * 120):
            if m.phase is MatchPhase.LIVE:
                return m
            m.step()
        self.fail("match never went live")

    def _exit_at(self, x: float, y: float):
        m = self._live_match()
        m.ball.x, m.ball.y = x, y
        events = m.step()
        pts = [e for e in events if isinstance(e, PointScored)]
        self.assertEqual(len(pts), 1)
        return m, pts[0]

    def test_exit_on_each_side(self):
        cases = [((30.0, 68.5), Team.A), ((80.0, -0.5), Team.B),
                 ((-0.5, 34.0), Team.A), ((105.5, 34.0), Team.B)]
        for (x, y), side in cases:
            m, pt = self._exit_at(x, y)
            self.assertIs(pt.reason, PointReason.OUT_OF_BOUNDS)
            self.assertIs(pt.conceded_by, side, msg=f"exit at {(x, y)}")
            self.assertIs(pt.scorer, side.opponent)
            self.assertIs(m.server_team, side)          # the conceding side serves next
            self.assertIs(m.phase, MatchPhase.HAND_PICKUP)
            self.assertIs(m.clock.state, ClockState.PAUSED)

    def test_referee_bounds(self):
        ref = BoundaryReferee()
        self.assertFalse(ref.ball_out_of_bounds(0.0, 0.0))
        self.assertFalse(ref.ball_out_of_bounds(105.0, 68.0))
        self.assertTrue(ref.ball_out_of_bounds(105.01, 10.0))
        self.assertTrue(ref.ball_out_of_bounds(50.0, -0.01))


class ServeFromAnywhereTests(unittest.TestCase):
    """Teams may serve from anywhere in their own half; the default serve must still
    be legal and always cross the midline."""

    def test_default_serve_is_legal_and_crosses_from_any_spot(self):
        ref = BoundaryReferee()
        rng = random.Random(11)
        for team in Team:
            policy = DefaultServePolicy(random.Random(3))
            server = build_team(team, random.Random(1))[0]
            zone = ref.serve_zone(team)
            for i in range(150):
                server.pos = Vec2(rng.uniform(zone.x_min, zone.x_max), rng.uniform(0.0, 68.0))
                intent = policy.decide(server)
                h = intent.heading.normalized()
                launch = server.pos + h * 0.4
                req = ServeRequest(team, server.pid, server.pos, launch, 0.0, h,
                                   intent.speed, intent.lean_rad, True)
                self.assertTrue(ref.validate_serve(req, team).ok, msg=f"{team} {server.pos}")
                eng = GyroscopicEngine(seed=i)
                ball = eng.launch(launch, h, intent.speed, intent.lean_rad)
                crossed = False
                while eng.step(ball, 1 / 60).name == "ROLLING":
                    if (ball.x > 52.5) if team is Team.A else (ball.x < 52.5):
                        crossed = True
                        break
                    if ref.ball_out_of_bounds(ball.x, ball.y):
                        break
                self.assertTrue(crossed, msg=f"{team} from {server.pos} at {intent.speed:.1f} m/s")


class MishitRuleTests(unittest.TestCase):
    def test_probability_rises_with_fatigue_and_ball_speed_and_is_capped(self):
        c = StrikeConfig()
        self.assertLess(c.mishit_probability(5.0, 1.0), c.mishit_probability(5.0, 0.4))
        self.assertLess(c.mishit_probability(6.0, 1.0), c.mishit_probability(12.0, 1.0))
        self.assertEqual(c.mishit_probability(100.0, 0.0), c.mishit_max)
        self.assertGreaterEqual(c.mishit_probability(0.0, 1.0), 0.0)

    def test_a_mishit_is_a_weak_strike(self):
        cfg = StrikeConfig()
        m = ServiceMatch(MatchConfig(seed=6))
        m._rng.random = lambda: 0.0  # force every swing to mishit
        m.start()
        mishits = []
        for _ in range(120 * 60):
            for e in m.step():
                if isinstance(e, StrikeMishit):
                    mishits.append(e)
            if mishits:
                break
        self.assertTrue(mishits, "no swing happened in 60 s")
        self.assertGreaterEqual(mishits[0].speed, cfg.mishit_min_speed)
        self.assertLessEqual(mishits[0].speed, cfg.mishit_max_speed)


class RotationTests(unittest.TestCase):
    def _point_by_exit(self, **config) -> tuple[ServiceMatch, list]:
        m = ServiceMatch(MatchConfig(seed=1, **config))
        m.start()
        for _ in range(120 * 120):
            if m.phase is MatchPhase.LIVE:
                break
            m.step()
        before = {p.pid: p.slot for p in m._all}
        m.ball.x, m.ball.y = 30.0, 68.5  # leaves on Team A's side: A concedes
        events = m.step()
        self.assertIs(m.server_team, Team.A)
        return m, [before, events]

    def test_conceding_team_rotates_one_slot_and_keeps_identities(self):
        m, (before, events) = self._point_by_exit()
        rotated = [e for e in events if isinstance(e, TeamRotated)]
        self.assertEqual([e.team for e in rotated], [Team.A])
        for p in m.squads[Team.A]:
            self.assertEqual(p.slot, (before[p.pid] + 1) % 6)
        for p in m.squads[Team.B]:
            self.assertEqual(p.slot, before[p.pid])  # the other team does not rotate
        self.assertEqual(sorted(p.slot for p in m.squads[Team.A]), list(range(6)))
        self.assertEqual(sorted(p.pid for p in m.squads[Team.A]), [f"A{i}" for i in range(1, 7)])

    def test_rotation_can_be_switched_off(self):
        m, (before, events) = self._point_by_exit(rotate_after_point=False)
        self.assertFalse([e for e in events if isinstance(e, TeamRotated)])
        self.assertEqual({p.pid: p.slot for p in m._all}, before)

    def test_players_walk_to_their_new_positions_during_pickup(self):
        m, _ = self._point_by_exit()
        picker = m._pickup.picker_id
        for _ in range(120 * 25):
            m.step()
            if m.phase is not MatchPhase.HAND_PICKUP:
                break
        for p in m.squads[Team.A]:
            if p.pid != picker:
                from service.agents.formation import home_position
                self.assertLess(p.pos.distance_to(home_position(Team.A, p.slot)), 1.5, msg=p.pid)


class LongHitTests(unittest.TestCase):
    def test_long_hit_dies_short_of_the_far_baseline_from_anywhere(self):
        rng = random.Random(2)
        for team in Team:
            for i in range(120):
                x = rng.uniform(5, 50) if team is Team.A else rng.uniform(55, 100)
                heading = Vec2(team.forward_sign, 0).rotated(rng.uniform(-0.3, 0.3))
                speed = long_hit_speed(team, x, heading, 10.0)
                eng = GyroscopicEngine(seed=i)
                ball = eng.launch(Vec2(x, 34.0), heading, speed, math.radians(rng.uniform(1, 3)))
                while eng.step(ball, 1 / 60).name == "ROLLING":
                    pass
                short = (105 - ball.x) if team is Team.A else ball.x
                self.assertGreater(short, 2.0, msg=f"{team} from {x:.1f}: went too far")
                self.assertLess(short, 22.0, msg=f"{team} from {x:.1f}: not deep enough")

    def test_full_bar_strike_is_a_long_hit_and_costs_extra_stamina(self):
        m = ServiceMatch(MatchConfig(seed=5))
        m.strike_policy.choose_charge_target = lambda striker, ball: 1.0
        m._rng.random = lambda: 0.99  # never a mishit
        m.start()
        strike = None
        for _ in range(120 * 120):
            for e in m.step():
                if isinstance(e, StrikeMade) and strike is None:
                    strike = e
            if strike:
                break
        self.assertIsNotNone(strike)
        self.assertTrue(strike.long_hit)
        self.assertGreaterEqual(strike.power, m.strike_cfg.long_hit_level)

    def test_ordinary_strikes_are_not_long_hits(self):
        m = ServiceMatch(MatchConfig(seed=5))
        m.strike_policy.choose_charge_target = lambda striker, ball: 0.5
        m._rng.random = lambda: 0.99
        m.start()
        strike = None
        for _ in range(120 * 120):
            for e in m.step():
                if isinstance(e, StrikeMade) and strike is None:
                    strike = e
            if strike:
                break
        self.assertIsNotNone(strike)
        self.assertFalse(strike.long_hit)


class RegressionTests(unittest.TestCase):
    def test_strike_counter_survives_ticks_after_a_strike(self):
        """Defect: the strikes-since-serve counter was reset every live tick, which
        mislabelled ordinary flat slaps as lazy serves."""
        m = ServiceMatch(MatchConfig(seed=4))
        m.start()
        struck = False
        for _ in range(120 * 300):
            events = m.step()
            if any(isinstance(e, StrikeMade) for e in events):
                struck = True
                break
        self.assertTrue(struck, "no strike happened")
        for _ in range(5):
            m.step()
        self.assertGreaterEqual(m._strikes_since_serve, 1)


if __name__ == "__main__":
    unittest.main()
