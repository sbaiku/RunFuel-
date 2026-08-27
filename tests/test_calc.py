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

    @pytest.mark.parametrize("distance", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_distance_raises(self, distance):
        with pytest.raises(ValueError):
            calc.validate_run(distance, 600)
        with pytest.raises(ValueError):
            calc.pace_seconds_per_km(distance, 600)
        with pytest.raises(ValueError):
            calc.speed_kmh(distance, 600)

    def test_non_finite_duration_raises(self):
        with pytest.raises(ValueError):
            calc.validate_run(5.0, float("inf"))
        with pytest.raises(ValueError):
            calc.validate_run(5.0, float("nan"))


class TestMetBands:
    @pytest.mark.parametrize(
        "speed, expected_met",
        [
            (6.39, 6.0),
            (6.4, 8.3),
            (7.99, 8.3),
            (8.0, 9.0),
            (9.69, 9.0),
            (9.7, 9.8),
            (11.29, 9.8),
            (11.3, 10.5),
            (12.89, 10.5),
            (12.9, 11.0),
            (14.49, 11.0),
            (14.5, 11.8),
            (16.09, 11.8),
            (16.1, 12.3),
            (17.69, 12.3),
            (17.7, 14.5),
            (19.29, 14.5),
            (19.3, 16.0),
            (25.0, 16.0),
        ],
    )
    def test_band_boundaries_are_lower_inclusive(self, speed, expected_met):
        assert calc.met_for_speed(speed) == expected_met

    def test_walking_pace_falls_into_the_lowest_band(self):
        assert calc.met_for_speed(4.0) == 6.0

    @pytest.mark.parametrize("speed", [0.0, -1.0])
    def test_non_positive_speed_raises(self, speed):
        with pytest.raises(ValueError):
            calc.met_for_speed(speed)


class TestCalories:
    def test_reference_ten_km_in_fifty_minutes(self):
        # 12.0 km/h -> MET 10.5; 10.5 * 3.5 * 70 / 200 * 50 = 643.125
        assert calc.calories_burned(10.0, 50 * 60, 70.0) == pytest.approx(643.125)

    def test_reference_ten_km_in_forty_minutes(self):
        # 15.0 km/h -> MET 11.8; 11.8 * 3.5 * 70 / 200 * 40 = 578.2
        assert calc.calories_burned(10.0, 40 * 60, 70.0) == pytest.approx(578.2)

    def test_doubling_weight_doubles_calories(self):
        light = calc.calories_burned(10.0, 50 * 60, 60.0)
        heavy = calc.calories_burned(10.0, 50 * 60, 120.0)
        assert heavy == pytest.approx(2 * light)

    def test_scales_linearly_with_duration_inside_one_band(self):
        # Both runs sit at 12.0 km/h, so MET is identical and only time differs.
        short = calc.calories_burned(10.0, 50 * 60, 70.0)
        long = calc.calories_burned(20.0, 100 * 60, 70.0)
        assert long == pytest.approx(2 * short)

    @pytest.mark.parametrize("weight", [0.0, -70.0])
    def test_non_positive_weight_raises(self, weight):
        with pytest.raises(ValueError):
            calc.calories_burned(10.0, 50 * 60, weight)

    @pytest.mark.parametrize("weight", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_weight_raises(self, weight):
        with pytest.raises(ValueError):
            calc.calories_burned(10.0, 50 * 60, weight)

    def test_non_positive_distance_raises(self):
        with pytest.raises(ValueError):
            calc.calories_burned(0.0, 50 * 60, 70.0)

    def test_non_positive_duration_raises(self):
        with pytest.raises(ValueError):
            calc.calories_burned(10.0, 0, 70.0)
