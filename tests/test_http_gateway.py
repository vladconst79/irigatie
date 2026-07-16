import io
import importlib.util
import os
import sys
import types
import unittest


def load_gateway_module():
    if "pymysql" not in sys.modules:
        fake_pymysql = types.ModuleType("pymysql")
        fake_pymysql.cursors = types.SimpleNamespace(DictCursor=object)
        sys.modules["pymysql"] = fake_pymysql

    module_name = "irigatie_http_gateway_test"
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "irigatie-http-gateway.py",
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gateway = load_gateway_module()


class FakeHeaders(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


class FakeGatewayConfig(object):
    auth_token = "secret-token"
    trusted_proxies = set(["127.0.0.1"])


class FakeServer(object):
    gateway_config = FakeGatewayConfig()


class GatewayHandlerTestCase(unittest.TestCase):
    def make_handler(self, headers=None, body=b""):
        handler = object.__new__(gateway.GatewayHandler)
        handler.headers = FakeHeaders(headers or {})
        handler.rfile = io.BytesIO(body)
        handler.server = FakeServer()
        handler.responses = []

        def write_json(status_code, payload):
            handler.responses.append((status_code, payload))

        handler.write_json = write_json
        return handler


class GatewayHelperTest(GatewayHandlerTestCase):
    def test_active_runtime_helpers_require_active_state(self):
        daemon_status = {"daemon_state": "running", "current_program": 4}
        runtime_status = {"state": "idle", "program_id": 5}
        self.assertTrue(gateway.active_runtime_state(daemon_status, runtime_status))
        self.assertEqual(4, gateway.current_runtime_program(daemon_status, runtime_status))

        daemon_status = {"daemon_state": "idle", "current_program": 4}
        runtime_status = {"state": "idle", "program_id": 5}
        self.assertFalse(gateway.active_runtime_state(daemon_status, runtime_status))
        self.assertIsNone(gateway.current_runtime_program(daemon_status, runtime_status))

    def test_match_id_path_accepts_positive_integer_only(self):
        handler = self.make_handler()
        self.assertEqual(12, handler.match_id_path("/api/schedules/12", "/api/schedules"))
        self.assertEqual(
            12,
            handler.match_id_path("/api/schedules/12/execute", "/api/schedules", "/execute"),
        )
        self.assertIsNone(handler.match_id_path("/api/schedules/0", "/api/schedules"))
        self.assertIsNone(handler.match_id_path("/api/schedules/abc", "/api/schedules"))
        self.assertIsNone(handler.match_id_path("/api/schedules/1/extra", "/api/schedules"))

    def test_trusted_proxy_parser_rejects_invalid_ip(self):
        self.assertEqual(
            set(["127.0.0.1", "::1"]),
            gateway.GatewayConfig.parse_trusted_proxies("127.0.0.1, ::1"),
        )
        with self.assertRaises(ValueError):
            gateway.GatewayConfig.parse_trusted_proxies("127.0.0.1, nope")


class GatewayJsonBodyTest(GatewayHandlerTestCase):
    def test_read_json_body_accepts_json_object(self):
        handler = self.make_handler(
            {
                "Content-Length": "17",
                "Content-Type": "application/json",
            },
            b'{"program_id": 3}',
        )

        self.assertEqual({"program_id": 3}, handler.read_json_body())
        self.assertEqual([], handler.responses)

    def test_read_json_body_allows_empty_when_requested(self):
        handler = self.make_handler({"Content-Length": "0"}, b"")

        self.assertEqual({}, handler.read_json_body(allow_empty=True))
        self.assertEqual([], handler.responses)

    def test_read_json_body_rejects_bad_shapes(self):
        cases = [
            ({}, b"", 400, "missing Content-Length"),
            ({"Content-Length": "bad"}, b"", 400, "invalid Content-Length"),
            ({"Content-Length": str(gateway.MAX_BODY_BYTES + 1)}, b"", 413, "request body too large"),
            ({"Content-Length": "2", "Content-Type": "text/plain"}, b"{}", 415, "Content-Type must be application/json"),
            ({"Content-Length": "1", "Content-Type": "application/json"}, b"{", 400, "invalid JSON body"),
            ({"Content-Length": "2", "Content-Type": "application/json"}, b"[]", 400, "JSON body must be an object"),
        ]
        for headers, body, expected_status, expected_error in cases:
            handler = self.make_handler(headers, body)
            self.assertIsNone(handler.read_json_body())
            self.assertEqual(expected_status, handler.responses[0][0])
            self.assertEqual(expected_error, handler.responses[0][1]["error"])


class GatewayAuthTest(GatewayHandlerTestCase):
    def test_require_auth_accepts_bearer_or_token_header(self):
        bearer_handler = self.make_handler({"Authorization": "Bearer secret-token"})
        self.assertTrue(bearer_handler.require_auth())

        token_handler = self.make_handler({"X-Irigatie-Token": "secret-token"})
        self.assertTrue(token_handler.require_auth())

    def test_require_auth_rejects_missing_or_wrong_token(self):
        handler = self.make_handler({"Authorization": "Bearer wrong"})

        self.assertFalse(handler.require_auth())
        self.assertEqual(401, handler.responses[0][0])
        self.assertEqual("unauthorized", handler.responses[0][1]["error"])


if __name__ == "__main__":
    unittest.main()
