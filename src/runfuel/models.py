"""Domain objects: what is stored, and what gets rendered."""

from dataclasses import dataclass
from datetime import date

from runfuel import calc


@dataclass(frozen=True)
class Run:
    """One logged run, exactly as it is stored."""

    id: int | None
    run_date: date
    distance_km: float
    duration_seconds: int


@dataclass(frozen=True)
class RunView:
    """A run plus its derived values, ready for a template.

    Derived values are computed here rather than stored, so changing the weight
    setting or the formula never leaves stale numbers in the database.
    """

    id: int | None
    run_date: date
    distance_km: float
    duration_seconds: int
    duration: str
    pace: str
    calories: float

    @classmethod
    def from_run(cls, run: Run, weight_kg: float) -> "RunView":
        return cls(
            id=run.id,
            run_date=run.run_date,
            distance_km=run.distance_km,
            duration_seconds=run.duration_seconds,
            duration=calc.format_duration(run.duration_seconds),
            pace=calc.format_pace(
                calc.pace_seconds_per_km(run.distance_km, run.duration_seconds)
            ),
            calories=calc.calories_burned(
                run.distance_km, run.duration_seconds, weight_kg
            ),
        )
