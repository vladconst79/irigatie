#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import configparser
import datetime as dt
import decimal
import hmac
import json
import os
import socket
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer

import pymysql


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
        self.db_host = parser.get("SQL", "DB_SERVER")
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
        conn = self.db_connect()
        try:
            zones = self.fetch_zones(conn)
            schedules = self.fetch_schedules(conn)
            manual_programs = self.fetch_manual_programs(conn, zones)
            runtime = self.fetch_runtime(conn)
            last_rain = self.fetch_last_rain(conn)
        finally:
            conn.close()

        runtime_status = daemon_status.get("runtime") or {}
        queue_status = daemon_status.get("queue") or {}
        relay_zones = (daemon_status.get("relay_state") or {}).get("zones") or {}
        zones = self.apply_relay_state(zones, relay_zones)

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
            "last_rain": last_rain,
            "zones": zones,
            "schedules": schedules,
            "manual_programs": manual_programs,
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

    def db_connect(self):
        config = self.server.gateway_config
        return pymysql.connect(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_pass,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
        )

    def fetch_zones(self, conn):
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, denumire AS name, tip AS type, activ AS enabled "
                "FROM trasee ORDER BY id;"
            )
            return [normalize_row(row) for row in cursor.fetchall()]

    def fetch_schedules(self, conn):
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, traseu_id AS zone_id, mon AS month, "
                "dom AS day_of_month, dow AS day_of_week, h AS hour, "
                "m AS minute, durata AS duration_minutes, "
                "max_ploaie AS max_rain_mm, ploaie AS current_rain_mm "
                "FROM programari ORDER BY mon, dom, dow, "
                "CAST(SUBSTRING_INDEX(h, ',', 1) AS UNSIGNED), "
                "CAST(SUBSTRING_INDEX(m, ',', 1) AS UNSIGNED), id;"
            )
            return [normalize_row(row) for row in cursor.fetchall()]

    def fetch_manual_programs(self, conn, zones):
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM progman ORDER BY id;")
            programs = []
            for row in cursor.fetchall():
                durations = {}
                for zone in zones:
                    zone_id = int(zone["id"])
                    durations[str(zone_id)] = int(row.get("durata_t%d" % zone_id) or 0)
                programs.append({
                    "id": int(row["id"]),
                    "name": row.get("denumire") or "Manual %s" % row["id"],
                    "zone_durations": durations,
                })
            return programs

    def fetch_runtime(self, conn):
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM runtime_state WHERE id = 1;")
            row = cursor.fetchone()
        if not row:
            return {
                "state": "unknown",
                "source": None,
                "command": None,
                "program_id": None,
                "zone_id": None,
                "remaining_seconds": 0,
                "heartbeat_at": None,
                "message": "runtime_state row missing",
            }

        row = normalize_row(row)
        remaining = 0
        expected_end = row.get("expected_end_at")
        if isinstance(expected_end, str):
            end = parse_db_datetime(expected_end)
            if end is not None:
                remaining = max(0, int((end - dt.datetime.now()).total_seconds()))

        return {
            "state": row.get("state") or "unknown",
            "source": row.get("source"),
            "command": row.get("command"),
            "program_id": row.get("program_id"),
            "zone_id": row.get("traseu_id"),
            "remaining_seconds": remaining,
            "heartbeat_at": row.get("heartbeat_at"),
            "message": row.get("message"),
        }

    def fetch_last_rain(self, conn):
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT source, event_time, amount_mm, raw_value "
                "FROM rain_events ORDER BY event_time DESC, id DESC LIMIT 1;"
            )
            row = cursor.fetchone()
        if not row:
            return {"source": "N/A", "event_time": "N/A", "amount_mm": 0}
        return normalize_row(row)

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
        print("%s - %s" % (self.address_string(), fmt % args))


class GatewayServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, gateway_config):
        super().__init__(server_address, handler_class)
        self.gateway_config = gateway_config


def normalize_row(row):
    normalized = {}
    for key, value in row.items():
        if isinstance(value, dt.datetime):
            normalized[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, decimal.Decimal):
            normalized[key] = float(value)
        else:
            normalized[key] = value
    return normalized


def parse_db_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(value[:19], fmt)
        except ValueError:
            pass
    return None


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
