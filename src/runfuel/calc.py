"""Pure running calculations.

This module must not import anything from the rest of the package. It takes
numbers and returns numbers so that the interesting logic stays testable
without a database, a request, or a template.
"""


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


def _validate_run(distance_km: float, duration_s: int) -> None:
    if distance_km <= 0:
        raise ValueError(f"distance must be greater than zero, got {distance_km}")
    if duration_s <= 0:
        raise ValueError(f"duration must be greater than zero, got {duration_s}")


def speed_kmh(distance_km: float, duration_s: int) -> float:
    """Average speed in kilometres per hour."""
    _validate_run(distance_km, duration_s)
    return distance_km / (duration_s / 3600)


def pace_seconds_per_km(distance_km: float, duration_s: int) -> float:
    """Average pace in seconds per kilometre."""
    _validate_run(distance_km, duration_s)
    return duration_s / distance_km


def format_pace(seconds_per_km: float) -> str:
    """Render a pace as ``M:SS /km``, rounding seconds and carrying the minute."""
    if seconds_per_km <= 0:
        raise ValueError("pace must be greater than zero")

    minutes, seconds = divmod(round(seconds_per_km), 60)
    return f"{minutes}:{seconds:02d} /km"
