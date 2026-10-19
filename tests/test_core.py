import math
import random
import unittest

from service.agents.player import build_team
from service.core.types import Team, Vec2
from service.court import BoundaryReferee, FaultCode, HandPickupTransition, PickupPhase, ServeRequest
from service.engine import ClockState, MatchClock, resolve_duration
from service.physics import GyroscopicEngine


class ClockTests(unittest.TestCase):
    def test_cap_and_validation(self):
        self.assertEqual(resolve_duration(None).effective, 15.0)
        r = resolve_duration(60)
        self.assertEqual((r.effective, r.clamped), (15.0, True))
        self.assertEqual(resolve_duration(15).clamped, False)
        for bad in (0, -1, float("nan"), float("inf"), True, "5"):
            with self.assertRaises(ValueError):
                resolve_duration(bad)

    def test_pause_does_not_consume_time(self):
        c = MatchClock(1)
        c.tick(5.0)  # not started: paused
        self.assertEqual(c.remaining_s, 60.0)
        c.resume()
        c.tick(10.0)
        c.pause()
        c.tick(30.0)
        self.assertAlmostEqual(c.remaining_s, 50.0)
        self.assertAlmostEqual(c.paused_elapsed_s, 35.0)

    def test_expiry_and_overtime(self):
        c = MatchClock(0.05)  # 3 s
        c.resume()
        self.assertTrue(any(c.tick(0.5) for _ in range(6)))
        self.assertEqual(c.state, ClockState.EXPIRED)
        c.begin_overtime(ball_live=True)
        c.tick(2.0)
        self.assertAlmostEqual(c.overtime_s, 2.0)
        self.assertEqual(c.remaining_s, 0.0)


class RefereeTests(unittest.TestCase):
    def setUp(self):
        self.ref = BoundaryReferee()

    def _req(self, **kw):
        base = dict(team=Team.A, server_id="A1", server_position=Vec2(0.5, 34),
                    launch_position=Vec2(0.9, 34), launch_z=0.0, heading=Vec2(1, 0),
                    speed=9.0, lean_rad=0.05, crouched=True)
        base.update(kw)
        return ServeRequest(**base)

    def test_serve_ok_and_z_fault(self):
        self.assertTrue(self.ref.validate_serve(self._req(), Team.A).ok)
        v = self.ref.validate_serve(self._req(launch_z=0.3), Team.A)
        self.assertIn(FaultCode.SERVE_NOT_AT_GROUND_LEVEL, v.faults)
        v = self.ref.validate_serve(self._req(crouched=False), Team.A)
        self.assertIn(FaultCode.SERVER_NOT_CROUCHED, v.faults)

    def test_serve_allowed_anywhere_in_own_half_but_not_the_other(self):
        for pos in (Vec2(0.5, 5), Vec2(26, 34), Vec2(52.0, 60)):
            req = self._req(server_position=pos, launch_position=pos + Vec2(0.4, 0))
            self.assertTrue(self.ref.validate_serve(req, Team.A).ok, msg=str(pos))
        far = self._req(server_position=Vec2(70, 34), launch_position=Vec2(70.4, 34))
        self.assertIn(FaultCode.SERVER_OUTSIDE_OWN_HALF, self.ref.validate_serve(far, Team.A).faults)

    def test_ball_must_be_struck_on_own_side(self):
        class P:
            pid, team, pos, reach = "a", Team.A, Vec2(52.0, 30), 1.3
        ok = self.ref.validate_strike(P(), 51.5, 30, True)
        self.assertTrue(ok.ok)
        over = self.ref.validate_strike(P(), 53.0, 30, True)  # within reach but over the line
        self.assertIn(FaultCode.STRIKE_BALL_ON_OPPONENT_SIDE, over.faults)

    def test_midline_clamp(self):
        class P:
            pid, team, pos, reach = "x", Team.A, Vec2(60, 10), 1.3
        p = P()
        viol = self.ref.enforce_zones([p])
        self.assertEqual(len(viol), 1)
        self.assertEqual(p.pos.x, 52.5)
        class Q(P):
            team, pos = Team.B, Vec2(10, 10)

        q = Q()
        self.ref.enforce_zones([q])
        self.assertEqual(q.pos.x, 52.5)

    def test_side_of(self):
        self.assertEqual(self.ref.side_of(10), Team.A)
        self.assertEqual(self.ref.side_of(90), Team.B)
        self.assertEqual(self.ref.side_of(52.5, Team.B), Team.B)


class PhysicsTests(unittest.TestCase):
    def roll(self, lean, v=12.0, noise=False):
        e = GyroscopicEngine(seed=1)
        b = e.launch(Vec2(0, 34), Vec2(1, 0), v, math.radians(lean))
        headings = []
        while e.step(b, 1 / 120, noise=noise).name == "ROLLING":
            headings.append(math.atan2(b.hy, b.hx))
        return b, headings

    def test_ball_always_ends_flat_at_90(self):
        b, _ = self.roll(3)
        self.assertTrue(b.is_flat)
        self.assertAlmostEqual(b.tilt_deg, 90.0)
        self.assertEqual(b.speed, 0.0)

    def test_curve_direction_follows_lean_and_is_progressive(self):
        bl, hl = self.roll(+8)
        br, hr = self.roll(-8)
        self.assertGreater(bl.y, br.y)  # leaning left curves further left
        # progressive: second half of the roll turns more than the first half
        mid = len(hl) // 2
        self.assertGreater(abs(hl[-1] - hl[mid]), abs(hl[mid] - hl[0]))

    def test_faster_launch_travels_farther(self):
        self.assertGreater(self.roll(3, 14)[0].distance, self.roll(3, 8)[0].distance)

    def test_determinism(self):
        a, _ = self.roll(4, noise=True)
        b, _ = self.roll(4, noise=True)
        self.assertEqual((a.x, a.y), (b.x, b.y))


class PickupTests(unittest.TestCase):
    def test_pickup_then_serve_from_where_the_ball_was_picked_up(self):
        ref = BoundaryReferee()
        p = build_team(Team.A, random.Random(1))[0]
        tr = HandPickupTransition(Team.A, p.pid, Vec2(20, 20), ref)
        seen = {tr.phase}
        for _ in range(120 * 60):
            seen.add(tr.advance(p, 1 / 120))
            if tr.is_ready:
                break
        self.assertEqual(seen, set(PickupPhase))
        self.assertLess(p.pos.distance_to(Vec2(20, 20)), 1.0)  # serves from the pickup spot, no carry
        self.assertEqual(tr.serve_spot, p.pos)
        self.assertTrue(p.crouched)

    def test_serve_spot_is_kept_back_from_the_midline(self):
        ref = BoundaryReferee()
        p = build_team(Team.A, random.Random(1))[0]
        tr = HandPickupTransition(Team.A, p.pid, Vec2(52.5, 30), ref)  # ball died on the line
        for _ in range(120 * 60):
            tr.advance(p, 1 / 120)
            if tr.is_ready:
                break
        self.assertLessEqual(tr.serve_spot.x, 52.5 - ref.rules.serve_line_margin_m)


if __name__ == "__main__":
    unittest.main()
