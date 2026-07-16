import json
import os
import tempfile
import unittest

import rain


class RainCreditTest(unittest.TestCase):
    def test_disabled_source_never_credits(self):
        self.assertFalse(rain.should_credit_rain("disabled", "manual"))
        self.assertEqual(0.0, rain.credit_amount_for_source("disabled", "manual", 10.0))

    def test_matching_source_credits_full_amount(self):
        self.assertTrue(rain.should_credit_rain("openmeteo", "openmeteo"))
        self.assertEqual(
            12.5,
            rain.credit_amount_for_source("openmeteo", "openmeteo", 12.5),
        )

    def test_non_matching_source_does_not_credit(self):
        self.assertEqual(
            0.0,
            rain.credit_amount_for_source("hardware", "openmeteo", 12.5),
        )

    def test_hybrid_source_uses_default_or_explicit_factor(self):
        self.assertEqual(
            0.0,
            rain.credit_amount_for_source("hybrid", "hardware", 10.0),
        )
        self.assertEqual(
            10.0,
            rain.credit_amount_for_source("hybrid", "openmeteo", 10.0),
        )
        self.assertEqual(
            2.5,
            rain.credit_amount_for_source("hybrid", "hardware", 10.0, 0.25),
        )


class RainStateTest(unittest.TestCase):
    def test_missing_or_empty_state_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "missing.json")
            self.assertEqual(
                {"last_hour": None, "remainder": 0.0},
                rain.load_state(missing_path),
            )

            empty_path = os.path.join(tmpdir, "empty.json")
            open(empty_path, "w").close()
            self.assertEqual(
                {"last_hour": None, "remainder": 0.0},
                rain.load_state(empty_path),
            )

    def test_load_state_accepts_json_and_legacy_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "state.json")
            with open(json_path, "w") as handle:
                json.dump({"last_hour": "2026-07-16T05:00", "remainder": "0.75"}, handle)
            self.assertEqual(
                {"last_hour": "2026-07-16T05:00", "remainder": 0.75},
                rain.load_state(json_path),
            )

            legacy_path = os.path.join(tmpdir, "legacy.txt")
            with open(legacy_path, "w") as handle:
                handle.write("2026-07-16T04:00\n")
            self.assertEqual(
                {"last_hour": "2026-07-16T04:00", "remainder": 0.0},
                rain.load_state(legacy_path),
            )


if __name__ == "__main__":
    unittest.main()
