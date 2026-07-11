"""
tests/test_format_number.py
"""

from services.crypto import format_number


class TestFormatNumber:
    def test_billions(self):
        assert format_number(2_500_000_000) == "$2.50B"

    def test_millions(self):
        assert format_number(3_200_000) == "$3.20M"

    def test_thousands(self):
        assert format_number(45_000) == "$45.0K"

    def test_small_number(self):
        assert format_number(42) == "$42.0000"

    def test_invalid_input_returns_na(self):
        assert format_number("not a number") == "N/A"

    def test_none_returns_na(self):
        assert format_number(None) == "N/A"
