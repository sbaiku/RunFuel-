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


class TestSpeed:
    def test_ten_km_in_fifty_minutes_is_twelve_kmh(self):
        assert calc.speed_kmh(10.0, 50 * 60) == pytest.approx(12.0)

    def test_five_km_in_thirty_minutes_is_ten_kmh(self):
        assert calc.speed_kmh(5.0, 30 * 60) == pytest.approx(10.0)


class TestPace:
    def test_ten_km_in_fifty_minutes_is_three_hundred_seconds_per_km(self):
        assert calc.pace_seconds_per_km(10.0, 50 * 60) == pytest.approx(300.0)

    def test_formats_whole_minutes(self):
        assert calc.format_pace(300.0) == "5:00 /km"

    def test_formats_with_padded_seconds(self):
        assert calc.format_pace(330.0) == "5:30 /km"

    def test_rounds_and_carries_into_the_next_minute(self):
        # 359.6 must render as 6:00, never as 5:60.
        assert calc.format_pace(359.6) == "6:00 /km"

    def test_handles_paces_over_an_hour_per_km(self):
        assert calc.format_pace(3661.0) == "61:01 /km"


class TestGuards:
    @pytest.mark.parametrize("distance", [0.0, -1.0])
    def test_non_positive_distance_raises(self, distance):
        with pytest.raises(ValueError):
            calc.pace_seconds_per_km(distance, 600)
        with pytest.raises(ValueError):
            calc.speed_kmh(distance, 600)

    @pytest.mark.parametrize("duration", [0, -60])
    def test_non_positive_duration_raises(self, duration):
        with pytest.raises(ValueError):
            calc.pace_seconds_per_km(5.0, duration)
        with pytest.raises(ValueError):
            calc.speed_kmh(5.0, duration)

    def test_non_positive_pace_cannot_be_formatted(self):
        with pytest.raises(ValueError):
            calc.format_pace(0.0)
