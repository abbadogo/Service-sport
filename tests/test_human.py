import unittest

from service.core.config import MatchConfig
from service.core.types import Team, Vec2
from service.engine import MatchPhase, ServiceMatch
from service.engine.events import StrikeMade, SwingMissed
from service.engine.human import HumanInput
from service.physics import TireBall


def live_match(**kw) -> ServiceMatch:
    m = ServiceMatch(MatchConfig(seed=1), human_team=Team.A, **kw)
    m.start()
    for _ in range(120 * 120):
        if m.phase is MatchPhase.LIVE:
            return m
        m.step()
    raise AssertionError("match never went live")


def set_up_rally(m: ServiceMatch) -> str:
    """Put one Team A player at (20, 34) and a slow live ball beside them; return that player's id."""
    squad = m.squads[Team.A]
    for i, p in enumerate(squad):
        p.pos = Vec2(5.0, 6.0 + 10.0 * i)
    squad[2].pos = Vec2(20.0, 34.0)
    m.ball = TireBall(20.1, 34.0, 0.0, 1.0, 2.0, 0.02)  # rolling slowly across the player's front
    m._last_striker, m._crossed = Team.B, True  # Team A is allowed to strike
    m._rng.random = lambda: 0.99  # never a mishit
    m.controllers[Team.A].cursor_id = squad[2].pid
    return squad[2].pid


class HumanInputTests(unittest.TestCase):
    def test_accepts_valid_and_rejects_invalid(self):
        HumanInput(1.0, -1.0, 0.5, 0.0, True)
        for kw in ({"move_x": 1.5}, {"aim_y": -2}, {"move_x": float("nan")}, {"move_y": "1"},
                   {"move_x": True}, {"charge": 1}):
            with self.assertRaises(ValueError, msg=str(kw)):
                HumanInput(**kw)


class HumanControlTests(unittest.TestCase):
    def test_hold_then_release_strikes_with_the_bar_level(self):
        m = live_match()
        pid = set_up_rally(m)
        for _ in range(60):  # hold for half a second: the bar fills to about 50%
            m.step(HumanInput(charge=True))
        self.assertAlmostEqual(m.players[pid].power_bar.level, 0.5, delta=0.03)
        events = m.step(HumanInput(aim_x=1.0, charge=False))
        strikes = [e for e in events if isinstance(e, StrikeMade)]
        self.assertEqual(len(strikes), 1)
        self.assertEqual(strikes[0].player_id, pid)
        self.assertAlmostEqual(strikes[0].power, 0.5, delta=0.03)
        self.assertFalse(strikes[0].long_hit)
        self.assertFalse(m.players[pid].power_bar.charging)

    def test_a_longer_hold_hits_harder_and_a_full_bar_is_a_long_hit(self):
        speeds = {}
        for hold in (30, 120):
            m = live_match()
            pid = set_up_rally(m)
            for _ in range(hold):
                m.step(HumanInput(charge=True))
                m.ball.x, m.ball.y, m.ball.speed = 20.1, 34.0, 2.0  # keep the ball in reach
            events = m.step(HumanInput(aim_x=1.0))
            strike = next(e for e in events if isinstance(e, StrikeMade))
            speeds[hold] = (strike.speed, strike.long_hit, strike.player_id == pid)
        self.assertLess(speeds[30][0], speeds[120][0])
        self.assertFalse(speeds[30][1])
        self.assertTrue(speeds[120][1])

    def test_swinging_with_the_ball_out_of_reach_misses(self):
        m = live_match()
        set_up_rally(m)
        for _ in range(30):
            m.step(HumanInput(charge=True))
            m.ball.x, m.ball.y, m.ball.speed = 30.0, 34.0, 2.0  # ball is 10 m away
        events = m.step(HumanInput(charge=False))
        self.assertTrue([e for e in events if isinstance(e, SwingMissed)])
        self.assertFalse([e for e in events if isinstance(e, StrikeMade)])

    def test_the_computer_never_strikes_for_the_human_team(self):
        m = live_match()
        set_up_rally(m)
        for _ in range(60):
            m.ball.x, m.ball.y, m.ball.speed = 20.1, 34.0, 2.0
            events = m.step(HumanInput())  # nobody pressing anything
            self.assertFalse([e for e in events if isinstance(e, StrikeMade) and e.team is Team.A])

    def test_the_controlled_player_moves_but_never_crosses_the_midline_or_the_pitch(self):
        m = live_match()
        pid = set_up_rally(m)
        player = m.players[pid]
        start = player.pos
        for _ in range(120 * 12):  # run toward the midline for 12 s
            m.ball.x, m.ball.y, m.ball.speed = player.pos.x + 0.1, player.pos.y, 2.0
            m.step(HumanInput(move_x=1.0, aim_x=1.0))
            self.assertLessEqual(player.pos.x, 52.5)
        self.assertGreater(player.pos.x, start.x + 5)
        for _ in range(120 * 20):  # and back toward the baseline
            m.ball.x, m.ball.y, m.ball.speed = player.pos.x + 0.1, player.pos.y, 2.0
            m.step(HumanInput(move_x=-1.0, aim_x=1.0))
            self.assertGreaterEqual(player.pos.x, 0.0)

    def test_control_passes_to_the_nearest_player_to_the_ball(self):
        m = live_match()
        squad = m.squads[Team.A]
        for i, p in enumerate(squad):
            p.pos = Vec2(5.0, 6.0 + 10.0 * i)
        m.ball = TireBall(40.0, 20.0, 0.0, 1.0, 3.0, 0.02)
        m.controllers[Team.A].cursor_id = squad[0].pid  # a far-away player is selected
        m.controllers[Team.A]._hold_left = 0.0
        squad[4].pos = Vec2(39.0, 20.0)  # clearly nearest
        for _ in range(3):
            m.ball.x, m.ball.y, m.ball.speed = 40.0, 20.0, 3.0
            m.step(HumanInput())
        self.assertEqual(m.controllers[Team.A].cursor_id, squad[4].pid)


if __name__ == "__main__":
    unittest.main()
