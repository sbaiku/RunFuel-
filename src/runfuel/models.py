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
    felt: int | None = None


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
    felt: int | None

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
            felt=run.felt,
        )


@dataclass(frozen=True)
class WeekSummary:
    """One ISO week of running, aggregated.

    ``pace`` comes from the week's totals rather than from a mean of the
    individual paces, so a short run cannot weigh as heavily as a long one.
    """

    week_start: date
    count: int
    distance_km: float
    duration_seconds: int
    pace: str
    calories: float

    @classmethod
    def from_views(cls, week_start: date, views: list[RunView]) -> "WeekSummary":
        distance_km = sum(view.distance_km for view in views)
        duration_seconds = sum(view.duration_seconds for view in views)
        return cls(
            week_start=week_start,
            count=len(views),
            distance_km=distance_km,
            duration_seconds=duration_seconds,
            pace=calc.format_pace(
                calc.pace_seconds_per_km(distance_km, duration_seconds)
            ),
            calories=sum(view.calories for view in views),
        )


def summarise_weeks(views: list[RunView]) -> list[WeekSummary]:
    """Group runs into ISO weeks, newest week first."""
    by_week: dict[date, list[RunView]] = {}
    for view in views:
        by_week.setdefault(calc.week_start(view.run_date), []).append(view)

    return [
        WeekSummary.from_views(week, by_week[week])
        for week in sorted(by_week, reverse=True)
    ]
