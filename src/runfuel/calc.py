"""Pure running calculations.

This module must not import anything from the rest of the package. It takes
numbers and returns numbers so that the interesting logic stays testable
without a database, a request, or a template.
"""

import math
from datetime import date, timedelta


def parse_duration(text: str) -> int:
    """Parse ``MM:SS`` or ``HH:MM:SS`` into a positive number of seconds."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"duration must be MM:SS or HH:MM:SS, got {text!r}")

    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        raise ValueError(f"duration must contain only digits, got {text!r}") from None

    if any(number < 0 for number in numbers):
        raise ValueError(f"duration must not be negative, got {text!r}")

    if len(numbers) == 2:
        hours, minutes, seconds = 0, numbers[0], numbers[1]
    else:
        hours, minutes, seconds = numbers
        if minutes >= 60:
            raise ValueError(f"minutes must be under 60 in HH:MM:SS, got {text!r}")

    if seconds >= 60:
        raise ValueError(f"seconds must be under 60, got {text!r}")

    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        raise ValueError("duration must be greater than zero")
    return total


def format_duration(seconds: int) -> str:
    """Render seconds as ``M:SS``, or ``H:MM:SS`` once it passes an hour."""
    if seconds < 0:
        raise ValueError("duration must not be negative")

    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def validate_run(distance_km: float, duration_s: int) -> None:
    if not math.isfinite(distance_km) or distance_km <= 0:
        raise ValueError(f"distance must be a finite number greater than zero, got {distance_km}")
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError(f"duration must be greater than zero, got {duration_s}")


def speed_kmh(distance_km: float, duration_s: int) -> float:
    """Average speed in kilometres per hour."""
    validate_run(distance_km, duration_s)
    return distance_km / (duration_s / 3600)


def pace_seconds_per_km(distance_km: float, duration_s: int) -> float:
    """Average pace in seconds per kilometre."""
    validate_run(distance_km, duration_s)
    return duration_s / distance_km


def format_pace(seconds_per_km: float) -> str:
    """Render a pace as ``M:SS /km``, rounding seconds and carrying the minute."""
    if seconds_per_km <= 0:
        raise ValueError(f"pace must be greater than zero, got {seconds_per_km}")

    minutes, seconds = divmod(round(seconds_per_km), 60)
    return f"{minutes}:{seconds:02d} /km"


# ACSM Compendium running entries, as (inclusive lower bound in km/h, MET).
# Ordered fastest-first so the first match wins.
_MET_BANDS: tuple[tuple[float, float], ...] = (
    (19.3, 16.0),
    (17.7, 14.5),
    (16.1, 12.3),
    (14.5, 11.8),
    (12.9, 11.0),
    (11.3, 10.5),
    (9.7, 9.8),
    (8.0, 9.0),
    (6.4, 8.3),
)
_MET_BELOW_LOWEST_BAND = 6.0


def met_for_speed(speed_kmh: float) -> float:
    """Metabolic equivalent for a running speed, via a banded lookup.

    Lower bounds are inclusive and upper bounds exclusive, so 6.4 km/h is the
    first speed to score 8.3 rather than 6.0.
    """
    if speed_kmh <= 0:
        raise ValueError(f"speed must be greater than zero, got {speed_kmh}")

    for lower_bound, met in _MET_BANDS:
        if speed_kmh >= lower_bound:
            return met
    return _MET_BELOW_LOWEST_BAND


def calories_burned(distance_km: float, duration_s: int, weight_kg: float) -> float:
    """Estimated kilocalories burned.

    Note that this is deliberately not monotonic in speed: burn scales as
    ``MET(speed) / speed`` and the banded table is not monotonic in that ratio.
    """
    if not math.isfinite(weight_kg) or weight_kg <= 0:
        raise ValueError(f"weight must be greater than zero, got {weight_kg}")

    met = met_for_speed(speed_kmh(distance_km, duration_s))
    duration_minutes = duration_s / 60
    return met * 3.5 * weight_kg / 200 * duration_minutes


FELT_MIN = 1
FELT_MAX = 5


def parse_felt(text: str) -> int | None:
    """Parse a "how it felt" rating, where blank means the runner skipped it."""
    stripped = text.strip()
    if not stripped:
        return None

    try:
        rating = int(stripped)
    except ValueError:
        raise ValueError(
            f"felt must be a whole number from {FELT_MIN} to {FELT_MAX}, got {text!r}"
        ) from None

    if not FELT_MIN <= rating <= FELT_MAX:
        raise ValueError(
            f"felt must be from {FELT_MIN} to {FELT_MAX}, got {rating}"
        )
    return rating


def week_start(run_date: date) -> date:
    """The Monday of the ISO week containing ``run_date``."""
    return run_date - timedelta(days=run_date.weekday())
