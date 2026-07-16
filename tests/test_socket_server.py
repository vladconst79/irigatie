import contextlib
import io
import unittest

from socket_server import parse_socket_command


class ParseSocketCommandTest(unittest.TestCase):
    def parse_quietly(self, message):
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                return parse_socket_command(message)

    def test_commands_with_positive_integer_parameter(self):
        self.assertEqual(("START", 12), self.parse_quietly("start 12"))
        self.assertEqual(("EXEC", 3), self.parse_quietly("EXEC 3"))
        self.assertEqual(("TEST", 4), self.parse_quietly(" TEST 4\n"))

    def test_commands_without_parameter(self):
        for command in ("STOP", "SHUTDOWN", "RELOAD_SCHEDULES", "STATUS"):
            self.assertEqual((command, None), self.parse_quietly(command.lower()))

    def test_rejects_invalid_commands(self):
        invalid_messages = [
            "",
            "START",
            "START 0",
            "START -1",
            "START abc",
            "START 1 extra",
            "STOP 1",
            "UNKNOWN",
            "STATUS now",
            "START 1\x00",
        ]
        for message in invalid_messages:
            self.assertEqual((None, None), self.parse_quietly(message), message)


if __name__ == "__main__":
    unittest.main()
