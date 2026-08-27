from datetime import date
from pathlib import Path

from runfuel.config import Settings, load_settings
from runfuel.models import Run, RunView


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

        assert view.pace == "5:00 /km"
