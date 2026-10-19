import json
import threading
import unittest
import urllib.error
import urllib.request

from service.api import server
from service.api.settings import SPECS, SettingsError, build_configs, default_for, validate_overrides


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._saved_cap = server.MAX_SIM_SECONDS
        server.MAX_SIM_SECONDS = 25.0  # keep test matches short
        cls.httpd = server.make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.MAX_SIM_SECONDS = cls._saved_cap

    def call(self, method: str, path: str, body: object | None = None, raw: bytes | None = None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())


class EndpointTests(ApiTestCase):
    def test_health(self):
        status, body = self.call("GET", "/api/health")
        self.assertEqual((status, body["status"]), (200, "ok"))

    def test_settings_lists_every_spec_with_defaults(self):
        status, body = self.call("GET", "/api/settings")
        self.assertEqual(status, 200)
        self.assertEqual([s["key"] for s in body["settings"]], [s.key for s in SPECS])
        for s in body["settings"]:
            self.assertGreaterEqual(s["default"], s["minimum"])
            self.assertLessEqual(s["default"], s["maximum"])

    def test_unknown_route_and_wrong_method(self):
        self.assertEqual(self.call("GET", "/api/nope")[0], 404)
        status, body = self.call("GET", "/api/matches")
        self.assertEqual((status, body["error"]["code"]), (405, "method_not_allowed"))
        self.assertEqual(self.call("POST", "/api/health", {})[0], 405)


class MatchEndpointTests(ApiTestCase):
    def test_valid_match_returns_a_replay(self):
        status, body = self.call("POST", "/api/matches", {"minutes": 0.2, "seed": 3})
        self.assertEqual(status, 200)
        head = body["schema"]["head"]
        stride = len(body["schema"]["player_fields"])
        for frame in body["frames"]:
            self.assertEqual(len(frame), len(head) + stride * len(body["players"]))
        self.assertEqual(len(body["players"]), 12)
        self.assertEqual(body["duration"], {"requested": 0.2, "effective": 0.2, "clamped": False})
        self.assertIn(body["result"]["reason"], {"CLOCK_EXPIRED", "SUDDEN_DEATH_POINT", "ABORTED"})

    def test_over_cap_minutes_are_clamped_and_reported(self):
        status, body = self.call("POST", "/api/matches", {"minutes": 99})
        self.assertEqual(status, 200)
        self.assertEqual(body["duration"]["effective"], 15.0)
        self.assertTrue(body["duration"]["clamped"])

    def test_settings_change_the_match(self):
        a = self.call("POST", "/api/matches", {"minutes": 0.2, "seed": 3})[1]
        b = self.call("POST", "/api/matches", {"minutes": 0.2, "seed": 3,
                                                "settings": {"grass_friction": 0.12}})[1]
        self.assertNotEqual(a["frames"][-1], b["frames"][-1])

    def test_rotation_toggle_changes_the_match_log(self):
        on = self.call("POST", "/api/matches", {"minutes": 0.3, "seed": 9, "settings": {"rotation": 1}})[1]
        off = self.call("POST", "/api/matches", {"minutes": 0.3, "seed": 9, "settings": {"rotation": 0}})[1]
        def kinds(r):
            return [e["kind"] for e in r["events"]]

        self.assertIn("point", kinds(on))
        self.assertIn("rotate", kinds(on))
        self.assertNotIn("rotate", kinds(off))

    def test_same_request_is_reproducible(self):
        req = {"minutes": 0.1, "seed": 9}
        self.assertEqual(self.call("POST", "/api/matches", req)[1], self.call("POST", "/api/matches", req)[1])

    def test_rejects_bad_requests(self):
        cases = [
            ({"minutes": 0}, "invalid_minutes"), ({"minutes": -2}, "invalid_minutes"),
            ({"minutes": "5"}, "invalid_minutes"), ({"minutes": True}, "invalid_minutes"),
            ({"seed": -1}, "invalid_seed"), ({"seed": 1.5}, "invalid_seed"),
            ({"seed": 2**40}, "invalid_seed"),
            ({"opening_server": "C"}, "invalid_opening_server"),
            ({"settings": []}, "invalid_settings"), ({"settings": {"nope": 1}}, "invalid_settings"),
            ({"settings": {"mishit_base": 5}}, "invalid_settings"),
            ({"settings": {"mishit_base": "x"}}, "invalid_settings"),
            ({"surprise": 1}, "invalid_request"),
        ]
        for payload, code in cases:
            status, body = self.call("POST", "/api/matches", payload)
            self.assertEqual((status, body["error"]["code"]), (400, code), msg=str(payload))

    def test_settings_at_their_limits_are_accepted(self):
        low = {s.key: s.minimum for s in SPECS}
        status, _ = self.call("POST", "/api/matches", {"minutes": 0.05, "settings": low})
        self.assertEqual(status, 200)

    def test_rejects_non_object_and_invalid_json_and_oversize(self):
        def code(*a, **k):
            return self.call("POST", "/api/matches", *a, **k)[1]["error"]["code"]

        self.assertEqual(code([1, 2]), "invalid_request")
        self.assertEqual(code(raw=b"{not json"), "invalid_json")
        status, body = self.call("POST", "/api/matches", raw=b" " * (server.MAX_BODY_BYTES + 1))
        self.assertEqual((status, body["error"]["code"]), (413, "too_large"))

    def test_unexpected_failure_is_generic_500(self):
        original = server.run_match
        server.run_match = lambda req: (_ for _ in ()).throw(RuntimeError("secret internal detail"))
        try:
            with self.assertLogs("service.api", level="ERROR"):
                status, body = self.call("POST", "/api/matches", {"minutes": 0.1})
        finally:
            server.run_match = original
        self.assertEqual((status, body["error"]["code"]), (500, "internal_error"))
        self.assertNotIn("secret", json.dumps(body))


class SettingsTests(unittest.TestCase):
    def test_defaults_build_default_configs(self):
        physics, strike, stamina = build_configs({})
        friction = next(s for s in SPECS if s.key == "grass_friction")
        self.assertEqual(physics.rolling_resistance, default_for(friction))
        self.assertEqual(strike.mishit_base, 0.06)
        self.assertEqual(stamina.sprint_drain_per_s, 0.05)

    def test_validation(self):
        for bad in ({"nope": 1}, {"mishit_base": float("nan")}, {"mishit_base": -0.1},
                    {"grass_friction": None}, {"charge_time": True}):
            with self.assertRaises(SettingsError, msg=str(bad)):
                validate_overrides(bad)


if __name__ == "__main__":
    unittest.main()
