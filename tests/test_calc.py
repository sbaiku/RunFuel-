import pytest

from runfuel import calc


class TestParseDuration:
    def test_parses_mm_ss(self):
        assert calc.parse_duration("45:30") == 45 * 60 + 30

    def test_parses_hh_mm_ss(self):
        assert calc.parse_duration("1:05:30") == 3600 + 5 * 60 + 30

    def test_allows_minutes_over_sixty_in_mm_ss(self):
        assert calc.parse_duration("90:00") == 90 * 60

    def test_strips_surrounding_whitespace(self):
        assert calc.parse_duration("  45:30  ") == 45 * 60 + 30

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "4530",
            "45",
            "45:",
            ":30",
            "abc:def",
            "1:2:3:4",
            "45:61",
            "1:60:00",
            "-5:00",
            "0:00",
        ],
    )
    def test_rejects_malformed_input(self, text):
        with pytest.raises(ValueError):
            calc.parse_duration(text)


class TestFormatDuration:
    def test_formats_under_an_hour(self):
        assert calc.format_duration(45 * 60 + 30) == "45:30"

    def test_formats_over_an_hour(self):
        assert calc.format_duration(3600 + 5 * 60 + 30) == "1:05:30"

    def test_pads_seconds(self):
        assert calc.format_duration(65) == "1:05"

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            calc.format_duration(-1)
