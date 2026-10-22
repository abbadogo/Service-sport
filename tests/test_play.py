import json
import threading
import unittest
import urllib.error
import urllib.request

from service.api import server
from service.api.errors import ApiError
from service.api.play import MAX_CATCHUP_S, PlaySession, SessionStore
from service.core.config import MatchConfig
from service.core.types import Team
from service.engine.human import HumanInput
from service.engine.state_machine import ServiceMatch


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def new_match(**config) -> ServiceMatch:
    return ServiceMatch(MatchConfig(seed=1, **config), human_team=Team.A)


class SessionTests(unittest.TestCase):
    def test_time_passing_advances_the_match(self):
        s = PlaySession(new_match(), Team.A, now=0.0)
        out = s.advance(HumanInput(), now=0.1)
        self.assertEqual(out["ticks"], 12)  # 0.1 s at 120 Hz
        self.assertEqual(len(out["frame"]), len(s.start_payload()["frame"]))
        self.assertFalse(out["finished"])

    def test_no_time_passing_means_no_ticks_and_fractions_are_carried_over(self):
        s = PlaySession(new_match(), Team.A, now=0.0)
        self.assertEqual(s.advance(HumanInput(), now=0.0)["ticks"], 0)
        total = sum(s.advance(HumanInput(), now=0.01 * i)["ticks"] for i in range(1, 11))
        self.assertEqual(total, 12)  # ten 10 ms steps add up to 0.1 s, none of it lost

    def test_a_long_gap_is_capped(self):
        s = PlaySession(new_match(), Team.A, now=0.0)
        self.assertEqual(s.advance(HumanInput(), now=60.0)["ticks"], int(MAX_CATCHUP_S * 120))

    def test_clock_going_backwards_is_harmless(self):
        s = PlaySession(new_match(), Team.A, now=5.0)
        self.assertEqual(s.advance(HumanInput(), now=1.0)["ticks"], 0)

    def test_a_match_runs_to_its_end_and_keeps_answering(self):
        s = PlaySession(new_match(max_sim_seconds=1.0), Team.A, now=0.0)
        out = {}
        for i in range(1, 30):
            out = s.advance(HumanInput(), now=i * 0.25)
            if out["finished"]:
                break
        self.assertTrue(out["finished"])
        self.assertEqual(out["result"]["reason"], "ABORTED")
        again = s.advance(HumanInput(), now=100.0)
        self.assertTrue(again["finished"])


class StoreTests(unittest.TestCase):
    def test_limit_expiry_and_delete(self):
        clock = FakeClock()
        store = SessionStore(clock=clock, max_sessions=2, ttl_s=10.0)
        a, _ = store.create(new_match(), Team.A)
        b, _ = store.create(new_match(), Team.A)
        with self.assertRaises(ApiError) as ctx:
            store.create(new_match(), Team.A)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (503, "busy"))
        store.delete(a)
        self.assertEqual(len(store), 1)
        with self.assertRaises(ApiError) as ctx:
            store.get(a)
        self.assertEqual(ctx.exception.status, 404)
        clock.now = 11.0  # idle past the time limit
        with self.assertRaises(ApiError):
            store.get(b)
        self.assertEqual(len(store), 0)
        store.create(new_match(), Team.A)  # room again

    def test_activity_keeps_a_session_alive(self):
        clock = FakeClock()
        store = SessionStore(clock=clock, ttl_s=10.0)
        sid, session = store.create(new_match(), Team.A)
        for t in (8.0, 16.0, 24.0):
            clock.now = t
            store.get(sid)
            session.advance(HumanInput(), now=t)
        self.assertEqual(len(store), 1)


class PlayHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._saved_cap = server.MAX_SIM_SECONDS
        cls._saved_store = server.STORE
        server.MAX_SIM_SECONDS = 20.0
        cls.httpd = server.make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.MAX_SIM_SECONDS = cls._saved_cap
        server.STORE = cls._saved_store

    def setUp(self) -> None:
        server.STORE = SessionStore(max_sessions=3)  # a fresh store for every test

    def call(self, method: str, path: str, body: object | None = None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def start(self, **extra):
        status, body = self.call("POST", "/api/play", {"minutes": 1, "seed": 2, **extra})
        self.assertEqual(status, 200, msg=body)
        return body

    def test_start_step_and_end(self):
        body = self.start()
        sid = body["session"]
        self.assertEqual(body["side"], "A")
        self.assertEqual(len(body["players"]), 12)
        status, step = self.call("POST", f"/api/play/{sid}/step",
                                 {"move": [1, 0], "aim": [1, 0], "charge": True})
        self.assertEqual(status, 200)
        self.assertEqual(len(step["frame"]), len(body["frame"]))
        self.assertEqual(self.call("DELETE", f"/api/play/{sid}")[0], 200)
        self.assertEqual(self.call("POST", f"/api/play/{sid}/step", {})[0], 404)

    def test_playing_as_team_b(self):
        self.assertEqual(self.start(side="B")["side"], "B")

    def test_empty_step_body_is_allowed(self):
        sid = self.start()["session"]
        self.assertEqual(self.call("POST", f"/api/play/{sid}/step", {})[0], 200)

    def test_bad_input_is_rejected(self):
        sid = self.start()["session"]
        for payload in ({"move": [2, 0]}, {"move": [0]}, {"move": "x"}, {"aim": [0, float("nan")]},
                        {"charge": "yes"}, {"surprise": 1}, [1, 2]):
            status, body = self.call("POST", f"/api/play/{sid}/step", payload)
            self.assertEqual(status, 400, msg=str(payload))
            self.assertIn(body["error"]["code"], {"invalid_input", "invalid_request"})

    def test_bad_start_requests_and_routes(self):
        code = self.call("POST", "/api/play", {"minutes": 0})[1]["error"]["code"]
        self.assertEqual(code, "invalid_minutes")
        code = self.call("POST", "/api/play", {"side": "C"})[1]["error"]["code"]
        self.assertEqual(code, "invalid_side")
        self.assertEqual(self.call("POST", "/api/play/short/step", {})[0], 404)
        self.assertEqual(self.call("POST", "/api/play/abcdefgh12/step", {})[0], 404)
        self.assertEqual(self.call("GET", "/api/play")[0], 405)
        sid = self.start()["session"]
        self.assertEqual(self.call("GET", f"/api/play/{sid}/step")[0], 405)
        self.assertEqual(self.call("POST", f"/api/play/{sid}/other", {})[0], 404)
        self.assertEqual(self.call("DELETE", f"/api/play/{sid}")[0], 200)

    def test_too_many_live_matches(self):
        for _ in range(3):
            self.start()
        status, body = self.call("POST", "/api/play", {"minutes": 1})
        self.assertEqual((status, body["error"]["code"]), (503, "busy"))


if __name__ == "__main__":
    unittest.main()
