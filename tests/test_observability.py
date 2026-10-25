import json
import logging
import threading
import unittest
import urllib.error
import urllib.request

from service.api import server
from service.api.logging_setup import JsonFormatter
from service.api.metrics import Metrics
from service.api.play import SessionStore


class MetricsTests(unittest.TestCase):
    def test_counts_responses_latency_and_internal_errors(self):
        m = Metrics()
        m.observe_request(200, 10.0)
        m.observe_request(404, 30.0)
        m.observe_request(500, 20.0)
        m.count("matches_run")
        snap = m.snapshot(active_sessions=3)
        self.assertEqual(snap["requests_total"], 3)
        self.assertEqual(snap["responses"], {"2xx": 1, "4xx": 1, "5xx": 1})
        self.assertEqual(snap["latency_ms"], {"avg": 20.0, "max": 30.0})
        self.assertEqual((snap["matches_run"], snap["internal_errors"]), (1, 1))
        self.assertEqual(snap["live_sessions"]["active"], 3)

    def test_an_empty_snapshot_has_no_division_by_zero(self):
        snap = Metrics().snapshot(active_sessions=0)
        self.assertEqual((snap["requests_total"], snap["latency_ms"]["avg"]), (0, 0.0))


class RouteTests(unittest.TestCase):
    def test_known_routes_session_ids_and_junk(self):
        self.assertEqual(server.route_of("/api/health?x=1"), "/api/health")
        self.assertEqual(server.route_of("/api/metrics"), "/api/metrics")
        self.assertEqual(server.route_of("/api/play/abcdefgh12345/step"), "/api/play/{id}/step")
        self.assertEqual(server.route_of("/api/play/abcdefgh12345"), "/api/play/{id}")
        self.assertEqual(server.route_of("/etc/passwd\nforged log line"), "unknown")
        self.assertEqual(server.route_of("/api/play/short"), "unknown")


class JsonFormatterTests(unittest.TestCase):
    def test_one_json_object_with_the_extra_fields(self):
        rec = logging.LogRecord("service.api", logging.INFO, __file__, 1, "request %s", ("x",), None)
        rec.rid, rec.status, rec.ms = "abc123", 200, 1.5
        out = json.loads(JsonFormatter().format(rec))
        self.assertEqual((out["msg"], out["level"], out["rid"], out["status"], out["ms"]),
                         ("request x", "INFO", "abc123", 200, 1.5))
        self.assertNotIn("route", out)
        self.assertTrue(out["ts"].endswith("Z"))


class ServerObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = server.make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self) -> None:
        server.STORE = SessionStore(max_sessions=3)

    def get(self, path: str, method: str = "GET", body: bytes | None = None):
        req = urllib.request.Request(self.base + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, dict(resp.headers), json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), json.loads(err.read())

    def test_metrics_endpoint_has_the_expected_keys_and_health_still_works(self):
        self.assertEqual(self.get("/api/health")[0], 200)
        status, _, body = self.get("/api/metrics")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"uptime_s", "requests_total", "responses", "latency_ms",
                                     "matches_run", "live_sessions", "internal_errors"})
        self.assertEqual(self.get("/api/metrics", method="POST", body=b"{}")[0], 405)

    def test_counters_move_when_things_happen(self):
        before = self.get("/api/metrics")[2]
        self.get("/api/nope")  # a 404
        self.get("/api/play", method="POST", body=json.dumps({"minutes": 1}).encode())
        after = self.get("/api/metrics")[2]
        self.assertGreaterEqual(after["requests_total"] - before["requests_total"], 3)
        self.assertEqual(after["responses"]["4xx"] - before["responses"]["4xx"], 1)
        self.assertEqual(after["live_sessions"]["started"] - before["live_sessions"]["started"], 1)
        self.assertEqual(after["live_sessions"]["active"], 1)

    def test_every_response_carries_a_request_id_and_errors_repeat_it(self):
        status, headers, _ = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertRegex(headers["X-Request-Id"], r"^[0-9a-f]{12}$")
        status, headers, body = self.get("/api/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["request_id"], headers["X-Request-Id"])

    def test_requests_are_logged_with_fields_but_never_with_a_session_id(self):
        with self.assertLogs("service.api", level="INFO") as logs:
            self.get("/api/health")
            _, _, start = self.get("/api/play", method="POST", body=json.dumps({"minutes": 1}).encode())
            self.get(f"/api/play/{start['session']}/step", method="POST", body=b"{}")
        text = "\n".join(logs.output)
        self.assertIn("route=/api/health status=200", text)
        self.assertIn("route=/api/play/{id}/step status=200", text)
        self.assertNotIn(start["session"], text)  # the session id is a secret


if __name__ == "__main__":
    unittest.main()
