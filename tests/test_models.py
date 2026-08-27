from datetime import date
from pathlib import Path

import pytest

from runfuel.config import Settings, load_settings
from runfuel.models import Run, RunView, summarise_weeks


class TestSettings:
    def test_defaults_when_environment_is_empty(self, monkeypatch):
        monkeypatch.delenv("RUNFUEL_DB_PATH", raising=False)
        monkeypatch.delenv("RUNFUEL_WEIGHT_KG", raising=False)

        settings = load_settings()

        assert settings.db_path == Path("runfuel.db")
        assert settings.weight_kg == 70.0

    def test_reads_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("RUNFUEL_DB_PATH", "/tmp/other.db")
        monkeypatch.setenv("RUNFUEL_WEIGHT_KG", "82.5")

        settings = load_settings()

        assert settings.db_path == Path("/tmp/other.db")
        assert settings.weight_kg == 82.5


class TestRunView:
    def test_derives_pace_duration_and_calories(self):
        run = Run(
            id=1,
            run_date=date(2026, 8, 27),
            distance_km=10.0,
            duration_seconds=50 * 60,
        )

        view = RunView.from_run(run, weight_kg=70.0)

        assert view.id == 1
        assert view.run_date == date(2026, 8, 27)
        assert view.distance_km == 10.0
        assert view.duration_seconds == 50 * 60
        assert view.duration == "50:00"
        assert view.pace == "5:00 /km"
        assert round(view.calories, 3) == 643.125

    def test_settings_carry_a_usable_weight(self):
        settings = Settings(db_path=Path("runfuel.db"), weight_kg=70.0)
        run = Run(id=2, run_date=date(2026, 8, 27), distance_km=5.0, duration_seconds=1500)

        view = RunView.from_run(run, weight_kg=settings.weight_kg)

        # 5 km / 25:00 -> 12.0 km/h -> MET 10.5; 10.5 * 3.5 * 70 / 200 * 25 = 321.5625
        assert round(view.calories, 4) == 321.5625


def _view(run_date: date, distance_km: float, duration_seconds: int, felt=None) -> RunView:
    return RunView.from_run(
        Run(
            id=None,
            run_date=run_date,
            distance_km=distance_km,
            duration_seconds=duration_seconds,
            felt=felt,
        ),
        weight_kg=70.0,
    )


class TestRunViewFelt:
    def test_carries_a_rating_through(self):
        assert _view(date(2026, 8, 27), 10.0, 3000, felt=4).felt == 4

    def test_carries_an_absent_rating_through(self):
        assert _view(date(2026, 8, 27), 10.0, 3000).felt is None


class TestSummariseWeeks:
    def test_no_runs_summarises_to_nothing(self):
        assert summarise_weeks([]) == []

    def test_groups_runs_into_the_week_that_contains_them(self):
        weeks = summarise_weeks(
            [_view(date(2026, 8, 27), 10.0, 3000), _view(date(2026, 8, 24), 5.0, 1800)]
        )

        assert len(weeks) == 1
        assert weeks[0].week_start == date(2026, 8, 24)
        assert weeks[0].count == 2

    def test_sums_distance_and_calories_across_the_week(self):
        weeks = summarise_weeks(
            [_view(date(2026, 8, 27), 10.0, 3000), _view(date(2026, 8, 24), 5.0, 1800)]
        )

        assert weeks[0].distance_km == pytest.approx(15.0)
        # 643.125 (12.0 km/h, MET 10.5) + 360.15 (10.0 km/h, MET 9.8)
        assert weeks[0].calories == pytest.approx(1003.275)

    def test_average_pace_comes_from_totals_not_a_mean_of_paces(self):
        # Per-run paces are 5:00 and 6:00; their mean would be 5:30.
        # Total time over total distance is 4800 / 15 = 320 s/km = 5:20.
        weeks = summarise_weeks(
            [_view(date(2026, 8, 27), 10.0, 3000), _view(date(2026, 8, 24), 5.0, 1800)]
        )

        assert weeks[0].pace == "5:20 /km"

    def test_separate_weeks_stay_separate_and_run_newest_first(self):
        weeks = summarise_weeks(
            [_view(date(2026, 8, 27), 10.0, 3000), _view(date(2026, 8, 18), 5.0, 1800)]
        )

        assert [week.week_start for week in weeks] == [
            date(2026, 8, 24),
            date(2026, 8, 17),
        ]

    def test_a_week_spanning_a_year_boundary_groups_together(self):
        weeks = summarise_weeks(
            [_view(date(2026, 1, 1), 10.0, 3000), _view(date(2025, 12, 29), 5.0, 1800)]
        )

        assert len(weeks) == 1
        assert weeks[0].week_start == date(2025, 12, 29)
