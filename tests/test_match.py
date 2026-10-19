import unittest

from service.agents.policies import ServeIntent
from service.core.config import MatchConfig
from service.core.types import Team, Vec2
from service.engine import MatchEndReason, MatchPhase, ServiceMatch
from service.engine.events import PointScored, ServeFault


class BadServe:
    def decide(self, server):
        return ServeIntent(Vec2(1, 0), 9.0, 0.05, launch_z=0.4)


class LazyServe:
    def decide(self, server):
        return ServeIntent(Vec2(1, 0), 3.5, 0.05)  # far too soft to reach the midline from mid-half


class MatchTests(unittest.TestCase):
    def test_default_serve_always_crosses_midline(self):
        crossed = 0
        for seed in range(1, 25):
            m = ServiceMatch(MatchConfig(duration_minutes=1, seed=seed))
            m.start()
            while m.phase is not MatchPhase.LIVE:
                m.step()
            b = m.ball
            side = m.server_team
            while m.phase is MatchPhase.LIVE:
                m.step()
                on_far_side = (b.x > 52.5) if side is Team.A else (b.x < 52.5)
                # reached by the receiver's stick (just short of the line) or crossed
                if m._strikes_since_serve > 0 or on_far_side:
                    crossed += 1
                    break
        self.assertEqual(crossed, 24)

    def test_lazy_serve_is_point_against_server_no_redo(self):
        from service.engine.events import PointReason
        m = ServiceMatch(MatchConfig(duration_minutes=1, seed=3), serve_policy=LazyServe())
        m.start()
        pts = []
        for _ in range(120 * 60):
            pts += [e for e in m.step() if isinstance(e, PointScored)]
            if pts:
                break
        self.assertEqual(pts[0].reason, PointReason.LAZY_SERVE)
        self.assertIs(pts[0].conceded_by, Team.A)  # opening server
        self.assertIs(pts[0].scorer, Team.B)

    def test_full_match_invariants(self):
        m = ServiceMatch(MatchConfig(duration_minutes=2, seed=5))
        m.start()
        pts = []
        while m.phase is not MatchPhase.FINISHED:
            before = m.clock.remaining_s
            phase = m.phase
            for e in m.step():
                if isinstance(e, PointScored):
                    pts.append(e)
            if phase is MatchPhase.HAND_PICKUP:
                self.assertGreaterEqual(m.clock.remaining_s, before)  # no ticking in pickup
            for p in m._all:  # nobody crosses the midline
                if p.team is Team.A:
                    self.assertLessEqual(p.pos.x, 52.5)
                else:
                    self.assertGreaterEqual(p.pos.x, 52.5)
        r = m.result
        self.assertAlmostEqual(r.live_time_s, 120.0, delta=0.05)
        self.assertEqual(r.score_a + r.score_b, len(pts))
        self.assertTrue(r.paused_time_s > 0)

    def test_conceding_side_serves_next(self):
        m = ServiceMatch(MatchConfig(duration_minutes=3, seed=2))
        m.start()
        last_conceder = None
        while m.phase is not MatchPhase.FINISHED:
            for e in m.step():
                if isinstance(e, PointScored):
                    last_conceder = e.conceded_by
                    if m.phase is MatchPhase.HAND_PICKUP:
                        self.assertIs(m.server_team, last_conceder)
                        self.assertIs(m._pickup.team, last_conceder)
                    self.assertIs(e.scorer, e.conceded_by.opponent)

    def test_determinism(self):
        a = ServiceMatch(MatchConfig(duration_minutes=1, seed=9)).run()
        b = ServiceMatch(MatchConfig(duration_minutes=1, seed=9)).run()
        self.assertEqual((a.score_a, a.score_b, a.sim_time_s), (b.score_a, b.score_b, b.sim_time_s))

    def test_duration_clamped_to_15(self):
        m = ServiceMatch(MatchConfig(duration_minutes=99))
        self.assertEqual(m.clock.total_s, 900.0)
        self.assertTrue(m.clock.resolution.clamped)
        with self.assertRaises(ValueError):
            ServiceMatch(MatchConfig(duration_minutes=0))

    def test_serve_faults_award_point(self):
        m = ServiceMatch(MatchConfig(duration_minutes=1, seed=1, max_serve_faults=2),
                         serve_policy=BadServe())
        m.start()
        events = []
        for _ in range(120 * 60):
            events += m.step()
            if any(isinstance(e, PointScored) for e in events):
                break
        faults = [e for e in events if isinstance(e, ServeFault)]
        self.assertGreaterEqual(len(faults), 2)
        pt = next(e for e in events if isinstance(e, PointScored))
        self.assertIs(pt.scorer, Team.B)  # A (server) faulted out

    def test_sudden_death_next_point_wins(self):
        found = False
        for seed in range(1, 40):
            r = ServiceMatch(MatchConfig(duration_minutes=0.5, seed=seed)).run()
            if r.overtime_s > 0:
                found = True
                self.assertEqual(r.reason, MatchEndReason.SUDDEN_DEATH_POINT)
                self.assertNotEqual(r.score_a, r.score_b)
                self.assertAlmostEqual(r.live_time_s, 30.0, delta=0.05)
                break
        self.assertTrue(found, "no tied expiry found in 40 seeds")


if __name__ == "__main__":
    unittest.main()
