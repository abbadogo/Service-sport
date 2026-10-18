import unittest
from service.agents.power_bar import PowerBar
from service.core.config import MatchConfig, StrikeConfig
from service.core.types import Team, Vec2
from service.engine import MatchPhase, ServiceMatch
from service.engine.events import StrikeMade
from service.physics import TireBall


class PowerBarTests(unittest.TestCase):
    def test_long_press_fills_to_full(self):
        b = PowerBar(rate=1.0); b.press(1.0)
        for _ in range(60): b.update(1 / 60)
        self.assertAlmostEqual(b.release(), 1.0, places=2)
        self.assertFalse(b.charging)

    def test_short_press_is_partial_and_target_caps_level(self):
        b = PowerBar(rate=1.0); b.press(1.0); b.update(0.4)
        self.assertAlmostEqual(b.release(), 0.4)
        b.press(0.6)
        for _ in range(200): b.update(0.01)
        self.assertAlmostEqual(b.release(), 0.6)

    def test_release_without_press_uses_min_level(self):
        self.assertEqual(PowerBar().release(min_level=0.25), 0.25)


class StrikeTests(unittest.TestCase):
    def test_speed_and_error_scale_with_level(self):
        c = StrikeConfig()
        self.assertEqual(c.speed_for(0.0), c.min_speed)
        self.assertEqual(c.speed_for(1.0), c.max_speed)
        self.assertLess(c.speed_for(0.3), c.speed_for(0.7))
        self.assertLess(c.aim_error_for(0.2), c.aim_error_for(0.9))

    def test_match_strikes_use_varied_power(self):
        m = ServiceMatch(MatchConfig(duration_minutes=1, seed=4)); m.start()
        levels = []
        while m.phase is not MatchPhase.FINISHED:
            levels += [e.power for e in m.step() if isinstance(e, StrikeMade)]
        self.assertGreater(len(levels), 5)
        self.assertTrue(all(0.0 <= l <= 1.0 for l in levels))
        self.assertGreater(max(levels) - min(levels), 0.2)


class CursorTests(unittest.TestCase):
    def test_cursor_hands_off_to_nearest(self):
        m = ServiceMatch(MatchConfig(seed=3))
        ctl = m.controllers[Team.A]; squad = m.squads[Team.A]
        ball = TireBall(30.0, 34.0, 1.0, 0.0, 5.0, 0.05)
        for i, p in enumerate(squad):
            p.pos = Vec2(5.0, 6.0 + 10 * i)      # all far away
        squad[4].pos = Vec2(29.0, 34.0)           # clearly nearest
        ctl.cursor_id = squad[0].pid             # stale far cursor
        for _ in range(5):
            chosen = ctl._select_cursor(squad, ball, [])
            self.assertIs(chosen, squad[4])
            ctl.cursor_id = chosen.pid

    def test_near_equals_are_randomised(self):
        m = ServiceMatch(MatchConfig(seed=8))
        ctl = m.controllers[Team.A]; squad = m.squads[Team.A]
        ball = TireBall(30.0, 34.0, 1.0, 0.0, 5.0, 0.05)
        for i, p in enumerate(squad): p.pos = Vec2(5.0, 6.0 + 10 * i)
        squad[1].pos, squad[2].pos = Vec2(28.5, 34.0), Vec2(28.9, 33.0)
        seen = set()
        for _ in range(60):
            ctl._hold_left = 0.0
            c = ctl._select_cursor(squad, ball, []); ctl.cursor_id = c.pid; seen.add(c.pid)
        self.assertEqual(seen, {squad[1].pid, squad[2].pid})


if __name__ == "__main__":
    unittest.main()
