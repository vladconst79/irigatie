import unittest

import generate_systemd_schedules as schedules


class ParseFieldTest(unittest.TestCase):
    def test_star_means_unrestricted(self):
        self.assertIsNone(schedules.parse_field("*", 0, 59, "minute"))

    def test_single_values_ranges_and_lists_are_sorted(self):
        self.assertEqual(
            [1, 3, 4, 9],
            schedules.parse_field("9,1,3-4", 1, 12, "month"),
        )

    def test_step_requires_allowed_field(self):
        self.assertEqual(
            [1, 11, 21, 31],
            schedules.parse_field("*/10", 1, 31, "day-of-month", allow_step=True),
        )
        with self.assertRaises(schedules.ScheduleError):
            schedules.parse_field("*/10", 0, 59, "minute")

    def test_invalid_values_raise_schedule_error(self):
        invalid_values = ["", "60", "5-3", "1,,2", "abc", "*/0"]
        for value in invalid_values:
            with self.assertRaises(schedules.ScheduleError, msg=value):
                schedules.parse_field(value, 0, 59, "minute", allow_step=True)


class CalendarLinesTest(unittest.TestCase):
    def test_dom_schedule_generates_calendar_lines(self):
        row = {
            "id": 7,
            "m": "0",
            "h": "5",
            "dom": "1,15",
            "mon": "6",
            "dow": "*",
        }

        self.assertEqual(
            ["*-06-01 05:00:00", "*-06-15 05:00:00"],
            schedules.calendar_lines(row),
        )

    def test_dow_schedule_generates_calendar_lines(self):
        row = {
            "id": 8,
            "m": "30",
            "h": "6",
            "dom": "*",
            "mon": "1",
            "dow": "1,3",
        }

        self.assertEqual(
            ["Mon *-01-* 06:30:00", "Wed *-01-* 06:30:00"],
            schedules.calendar_lines(row),
        )

    def test_restricting_dom_and_dow_is_rejected(self):
        row = {
            "id": 9,
            "m": "0",
            "h": "5",
            "dom": "1",
            "mon": "*",
            "dow": "1",
        }

        with self.assertRaises(schedules.ScheduleError):
            schedules.calendar_lines(row)


if __name__ == "__main__":
    unittest.main()
