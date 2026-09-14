"""
Unit tests for the minimalist ISO-8601 duration parser.
"""

import unittest
from examples.iso8601_duration import parse_iso8601_duration, MAX_DURATION_LENGTH


class TestISO8601DurationParser(unittest.TestCase):
    """Test suite for ISO-8601 duration parsing logic."""

    def test_parse_seconds_only(self) -> None:
        self.assertEqual(parse_iso8601_duration("PT3S"), 3)
        self.assertEqual(parse_iso8601_duration("PT45S"), 45)

    def test_parse_minutes_and_seconds(self) -> None:
        self.assertEqual(parse_iso8601_duration("PT2M30S"), 150)

    def test_parse_hours_minutes_seconds(self) -> None:
        self.assertEqual(parse_iso8601_duration("PT1H2M3S"), 3723)

    def test_parse_days_and_time(self) -> None:
        self.assertEqual(parse_iso8601_duration("P1DT1H"), 90000)

    def test_parse_weeks(self) -> None:
        self.assertEqual(parse_iso8601_duration("P2W"), 1209600)

    def test_parse_months_and_years(self) -> None:
        expected = (365 + 30 + 1) * 86400
        self.assertEqual(parse_iso8601_duration("P1Y1M1D"), expected)

    def test_invalid_type(self) -> None:
        with self.assertRaises(TypeError):
            parse_iso8601_duration(123)  # type: ignore

    def test_empty_string(self) -> None:
        with self.assertRaises(ValueError):
            parse_iso8601_duration("")

    def test_exceeds_max_length(self) -> None:
        long_str = "P" + "9" * (MAX_DURATION_LENGTH + 1) + "S"
        with self.assertRaises(ValueError):
            parse_iso8601_duration(long_str)

    def test_invalid_formats(self) -> None:
        invalid_strings = [
            "P",
            "PT",
            "1H2M3S",
            "PT1H2X3S",
            "P-1D",
            "PT1.5S",
            "random",
        ]
        for invalid in invalid_strings:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_iso8601_duration(invalid)


if __name__ == "__main__":
    unittest.main()
