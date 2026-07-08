#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import configparser
import hmac
import json
import os
import socket
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer

import db


DEFAULT_CONFIG = "/home/pi/irigatie/irigatie.conf"
DEFAULT_SOCKET_PATH = "/run/irigatie/control.sock"
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_BIND_PORT = 8080
DEFAULT_AUTH_TOKEN = "change-this-token"
MAX_BODY_BYTES = 4096


class GatewayConfig:
    def __init__(self, config_path):
        parser = configparser.ConfigParser()
        parser.read(config_path)

        section = "HTTP Gateway"
        self.socket_path = parser.get(
            section,
            "SOCKET_PATH",
            fallback=parser.get(
                "Control Socket", "SOCKET_PATH", fallback=DEFAULT_SOCKET_PATH),
        )
        self.bind_host = parser.get(
            section, "BIND_HOST", fallback=DEFAULT_BIND_HOST)
        self.bind_port = parser.getint(
            section, "BIND_PORT", fallback=DEFAULT_BIND_PORT)
        self.auth_token = os.environ.get(
            "IRIGATIE_GATEWAY_TOKEN",
            parser.get(section, "AUTH_TOKEN", fallback=DEFAULT_AUTH_TOKEN),
        )
        self.db_server = parser.get("SQL", "DB_SERVER")
        self.db_host = self.db_server
        self.db_port = parser.getint("SQL", "DB_PORT", fallback=3306)
        self.db_user = parser.get("SQL", "DB_USER")
        self.db_pass = parser.get("SQL", "DB_PASS")
        self.db_name = parser.get("SQL", "DB_NAME")

        if not self.auth_token or self.auth_token == DEFAULT_AUTH_TOKEN:
            raise ValueError(
                "HTTP Gateway AUTH_TOKEN must be set in irigatie.conf "
                "or IRIGATIE_GATEWAY_TOKEN"
            )


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "IrigatieHTTPGateway/1.0"

    def do_GET(self):
        if not self.require_auth():
            return

        if self.path == "/status":
            self.write_daemon_status()
            return

        if self.path == "/api/snapshot":
            self.write_app_snapshot()
            return

        self.write_json(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self):
        if not self.require_auth():
            return

        if self.path == "/commands/start":
            program_id = self.read_program_id()
            if program_id is None:
                return
            self.forward_command("START %d" % program_id)
            return

        if self.path == "/commands/exec":
            program_id = self.read_program_id()
            if program_id is None:
                return
            self.forward_command("EXEC %d" % program_id)
            return

        if self.path == "/api/manual/execute":
            program_id = self.read_program_id()
            if program_id is None:
                return
            self.forward_command("EXEC %d" % program_id)
            return

        if self.path == "/api/schedules/start":
            program_id = self.read_program_id()
            if program_id is None:
                return
            self.forward_command("START %d" % program_id)
            return

        if self.path == "/commands/stop":
            body = self.read_json_body(allow_empty=True)
            if body is None:
                return
            if body != {}:
                self.write_json(400, {
                    "ok": False,
                    "error": "STOP does not accept request fields",
                })
                return
            self.forward_command("STOP")
            return

        if self.path == "/reload-schedules":
            body = self.read_json_body(allow_empty=True)
            if body is None:
                return
            if body != {}:
                self.write_json(400, {
                    "ok": False,
                    "error": "reload-schedules does not accept request fields",
                })
                return
            self.forward_command("RELOAD_SCHEDULES")
            return

        self.write_json(404, {"ok": False, "error": "unknown endpoint"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.write_common_headers()
        self.end_headers()

    def require_auth(self):
        expected = self.server.gateway_config.auth_token
        auth_header = self.headers.get("Authorization", "")
        bearer_prefix = "Bearer "
        supplied = self.headers.get("X-Irigatie-Token", "")

        if auth_header.startswith(bearer_prefix):
            supplied = auth_header[len(bearer_prefix):]

        if hmac.compare_digest(supplied, expected):
            return True

        self.write_json(401, {"ok": False, "error": "unauthorized"})
        return False

    def read_program_id(self):
        body = self.read_json_body()
        if body is None:
            return None

        if set(body.keys()) != {"program_id"}:
            self.write_json(400, {
                "ok": False,
                "error": "request body must contain only program_id",
            })
            return None

        program_id = body["program_id"]
        if isinstance(program_id, bool) or not isinstance(program_id, int):
            self.write_json(400, {
                "ok": False,
                "error": "program_id must be an integer",
            })
            return None

        if program_id <= 0:
            self.write_json(400, {
                "ok": False,
                "error": "program_id must be greater than zero",
            })
            return None

        return program_id

    def read_json_body(self, allow_empty=False):
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            if allow_empty:
                return {}
            self.write_json(400, {
                "ok": False,
                "error": "missing Content-Length",
            })
            return None

        try:
            length = int(content_length)
        except ValueError:
            self.write_json(400, {
                "ok": False,
                "error": "invalid Content-Length",
            })
            return None

        if length < 0 or length > MAX_BODY_BYTES:
            self.write_json(413, {
                "ok": False,
                "error": "request body too large",
            })
            return None

        raw_body = self.rfile.read(length)
        if len(raw_body) == 0 and allow_empty:
            return {}

        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self.write_json(415, {
                "ok": False,
                "error": "Content-Type must be application/json",
            })
            return None

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.write_json(400, {
                "ok": False,
                "error": "invalid JSON body",
            })
            return None

        if not isinstance(body, dict):
            self.write_json(400, {
                "ok": False,
                "error": "JSON body must be an object",
            })
            return None

        return body

    def forward_command(self, command):
        socket_path = self.server.gateway_config.socket_path
        if not os.path.exists(socket_path):
            self.write_json(503, {
                "ok": False,
                "error": "irrigation socket does not exist",
            })
            return

        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                client.connect(socket_path)
                client.send(command.encode("utf-8"))
            finally:
                client.close()
        except OSError as exc:
            self.write_json(503, {
                "ok": False,
                "error": "failed to send command to irrigation socket",
                "detail": str(exc),
            })
            return

        self.write_json(202, {
            "ok": True,
            "accepted": True,
            "command": command,
        })

    def write_daemon_status(self):
        gateway_status = {
            "state": "running",
            "socket_path": self.server.gateway_config.socket_path,
            "socket_exists": os.path.exists(
                self.server.gateway_config.socket_path),
            "daemon_status_supported": True,
        }

        try:
            daemon_status = self.request_daemon_status()
        except OSError as exc:
            self.write_json(503, {
                "ok": False,
                "gateway": gateway_status,
                "daemon": {
                    "ok": False,
                    "error": "failed to query irrigation daemon",
                    "detail": str(exc),
                },
            })
            return
        except ValueError as exc:
            self.write_json(503, {
                "ok": False,
                "gateway": gateway_status,
                "daemon": {
                    "ok": False,
                    "error": "invalid status response from irrigation daemon",
                    "detail": str(exc),
                },
            })
            return

        self.write_json(200, {
            "ok": bool(daemon_status.get("ok")),
            "gateway": gateway_status,
            "daemon": daemon_status,
        })

    def write_app_snapshot(self):
        try:
            daemon_status = self.request_daemon_status()
        except (OSError, ValueError):
            daemon_status = {}

        try:
            payload = self.build_app_snapshot(daemon_status)
        except Exception as exc:
            print("app snapshot database error: %r" % exc)
            payload = self.build_degraded_app_snapshot(daemon_status)

        self.write_json(200, payload)

    def build_app_snapshot(self, daemon_status):
        database = db.IrrigationDatabase(self.server.gateway_config).connect()
        try:
            snapshot_data = database.get_app_snapshot_data()
        finally:
            database.close()

        runtime_status = daemon_status.get("runtime") or {}
        queue_status = daemon_status.get("queue") or {}
        relay_zones = (daemon_status.get("relay_state") or {}).get("zones") or {}
        zones = snapshot_data["zones"]
        zones = self.apply_relay_state(zones, relay_zones)
        runtime = snapshot_data["runtime"]

        if daemon_status:
            runtime.update({
                "state": daemon_status.get("daemon_state") or runtime_status.get("state"),
                "program_id": daemon_status.get("current_program") or runtime_status.get("program_id"),
                "zone_id": daemon_status.get("current_zone") or runtime_status.get("traseu_id"),
                "remaining_seconds": daemon_status.get("remaining_seconds") or 0,
                "heartbeat_at": runtime_status.get("heartbeat_at") or runtime.get("heartbeat_at"),
                "message": runtime_status.get("message") or runtime.get("message"),
            })

        return {
            "ok": True,
            "database": {"ok": True, "name": self.server.gateway_config.db_name},
            "gateway": {
                "online": bool(daemon_status.get("ok")),
                "socket_path": self.server.gateway_config.socket_path,
            },
            "queue": {
                "pending": queue_status.get("pending_watering_commands", 0),
                "max": queue_status.get("max_pending_watering_commands", 4),
            },
            "runtime": runtime,
            "last_rain": snapshot_data["last_rain"],
            "zones": zones,
            "schedules": snapshot_data["schedules"],
            "manual_programs": snapshot_data["manual_programs"],
        }

    def build_degraded_app_snapshot(self, daemon_status):
        runtime_status = daemon_status.get("runtime") or {}
        queue_status = daemon_status.get("queue") or {}

        return {
            "ok": False,
            "database": {
                "ok": False,
                "name": self.server.gateway_config.db_name,
                "error": "database unavailable",
            },
            "gateway": {
                "online": bool(daemon_status.get("ok")),
                "socket_path": self.server.gateway_config.socket_path,
            },
            "queue": {
                "pending": queue_status.get("pending_watering_commands", 0),
                "max": queue_status.get("max_pending_watering_commands", 4),
            },
            "runtime": {
                "state": daemon_status.get("daemon_state") or runtime_status.get("state") or "unknown",
                "source": runtime_status.get("source"),
                "command": runtime_status.get("command"),
                "program_id": daemon_status.get("current_program") or runtime_status.get("program_id"),
                "zone_id": daemon_status.get("current_zone") or runtime_status.get("traseu_id"),
                "remaining_seconds": daemon_status.get("remaining_seconds") or 0,
                "heartbeat_at": runtime_status.get("heartbeat_at"),
                "message": runtime_status.get("message") or "database unavailable",
            },
            "last_rain": {
                "source": "N/A",
                "event_time": "N/A",
                "amount_mm": 0,
                "raw_value": None,
            },
            "zones": [],
            "schedules": [],
            "manual_programs": [],
        }

    def apply_relay_state(self, zones, relay_zones):
        updated = []
        for zone in zones:
            relay = relay_zones.get(str(zone["id"])) or {}
            zone = dict(zone)
            zone["relay_active"] = bool(relay.get("active"))
            zone["relay_value"] = relay.get("value")
            updated.append(zone)
        return updated

    def request_daemon_status(self):
        socket_path = self.server.gateway_config.socket_path
        if not os.path.exists(socket_path):
            raise OSError("irrigation socket does not exist")

        client_path = "/tmp/irigatie-http-status-%s-%s.sock" % (
            os.getpid(), id(self))
        if os.path.exists(client_path):
            os.remove(client_path)

        client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            client.bind(client_path)
            client.settimeout(5)
            client.sendto("STATUS".encode("utf-8"), socket_path)
            response = client.recv(65535)
        finally:
            client.close()
            if os.path.exists(client_path):
                os.remove(client_path)

        return json.loads(response.decode("utf-8"))

    def write_json(self, status_code, payload):
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status_code)
        self.write_common_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_common_headers(self):
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, X-Irigatie-Token")
        self.send_header("Cache-Control", "no-store")

    def log_message(self, fmt, *args):
        if self.path == "/api/snapshot":
            return
        print("%s - %s" % (self.address_string(), fmt % args))


class GatewayServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, gateway_config):
        super().__init__(server_address, handler_class)
        self.gateway_config = gateway_config


def parse_args():
    parser = argparse.ArgumentParser(
        description="HTTP gateway for irigatie-control.py Unix socket commands")
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG,
        help="path to irigatie.conf")
    return parser.parse_args()


def main():
    args = parse_args()
    gateway_config = GatewayConfig(args.config)
    server_address = (gateway_config.bind_host, gateway_config.bind_port)
    httpd = GatewayServer(server_address, GatewayHandler, gateway_config)
    print("Irigatie HTTP gateway listening on %s:%d" % server_address)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
