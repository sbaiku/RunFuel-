# RunFuel MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI running log that records date/distance/duration to SQLite and renders every run with derived pace and estimated calories.

**Architecture:** Four layers with one hard boundary. `calc.py` is pure (floats in, floats out, imports nothing from the package) and holds all tested logic. `db.py` owns SQL via stdlib `sqlite3` and speaks in `Run` objects. `app.py` owns HTTP and Jinja2 and calls the other two. `config.py` reads the environment. An app-factory (`create_app(settings)`) makes the whole stack testable against a throwaway database.

**Tech Stack:** Python 3.13, uv, hatchling, FastAPI, Jinja2, stdlib `sqlite3`, pytest, httpx.

**Spec:** `docs/superpowers/specs/2026-08-27-runfuel-design.md`

## Global Constraints

- Python pin: `.python-version` contains `3.13`; `requires-python = ">=3.11"` in `pyproject.toml`. (3.13 rather than the host's 3.14 for wheel availability; uv fetches it automatically.)
- Every command runs through uv: `uv run pytest`, `uv sync`, `uv add`. Never call bare `pip` or `python`.
- `src/` layout. The package is `src/runfuel/`; imports are `from runfuel import ...`, never relative-to-cwd.
- **`src/runfuel/calc.py` must not import anything from `runfuel`.** It is pure. This is the boundary the whole test strategy rests on.
- Pace and calories are **derived on read, never stored**. No `pace` or `calories` column.
- MET band table is copied verbatim from the spec; lower bound inclusive, upper exclusive.
- `kcal = MET * 3.5 * weight_kg / 200 * duration_minutes`
- Default weight is `70.0` kg from `RUNFUEL_WEIGHT_KG`. Default DB path is `runfuel.db` from `RUNFUEL_DB_PATH`.
- Mutating routes return **303** redirects (POST-redirect-GET).
- Bad distance or duration -> `ValueError` in `calc.py` -> **400** with a re-rendered form. Malformed date -> FastAPI's own **422**.
- No ORM. No migrations. No auth.
- Tests must never touch a developer's real `runfuel.db`.
- Do not assert calorie monotonicity in speed — the banded model is deliberately not monotonic in `MET(speed)/speed`.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`
- Create: `src/runfuel/__init__.py`
- Test: `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installed `runfuel` package importable in tests; `uv run pytest` as the project's test command.

- [ ] **Step 1: Write the failing test**

Create `tests/test_package.py`:

```python
def test_package_imports():
    import runfuel

    assert runfuel.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runfuel'` (or uv errors that no project exists yet).

- [ ] **Step 3: Create the project files**

`.python-version`:

```
3.13
```

`pyproject.toml`:

```toml
[project]
name = "runfuel"
version = "0.1.0"
description = "A personal running log with pace and calorie estimates."
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "httpx2>=2.12",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/runfuel"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore`:

```
__pycache__/
*.py[cod]
.venv/
*.db
.pytest_cache/
dist/
.superpowers/
```

`src/runfuel/__init__.py`:

```python
"""RunFuel — a personal running log."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Sync dependencies**

Run: `uv sync`
Expected: uv downloads Python 3.13 if needed, creates `.venv`, installs FastAPI/Jinja2/pytest/httpx and the `runfuel` package in editable mode.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version .gitignore src/runfuel/__init__.py tests/test_package.py uv.lock
git commit -m "chore: scaffold runfuel package with uv and pytest"
```

---

### Task 2: Duration parsing and formatting

**Files:**
- Create: `src/runfuel/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `parse_duration(text: str) -> int`, `format_duration(seconds: int) -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_calc.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calc.py -v`
Expected: FAIL — `ImportError: cannot import name 'calc' from 'runfuel'`

- [ ] **Step 3: Write minimal implementation**

Create `src/runfuel/calc.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calc.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add src/runfuel/calc.py tests/test_calc.py
git commit -m "feat: parse and format run durations"
```

---

### Task 3: Speed and pace

**Files:**
- Modify: `src/runfuel/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: `runfuel.calc` from Task 2.
- Produces: `speed_kmh(distance_km: float, duration_s: int) -> float`, `pace_seconds_per_km(distance_km: float, duration_s: int) -> float`, `format_pace(seconds_per_km: float) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calc.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calc.py -v`
Expected: FAIL — `AttributeError: module 'runfuel.calc' has no attribute 'speed_kmh'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/runfuel/calc.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calc.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runfuel/calc.py tests/test_calc.py
git commit -m "feat: compute and format speed and pace"
```

---

### Task 4: MET bands and calorie burn

**Files:**
- Modify: `src/runfuel/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: `speed_kmh` from Task 3.
- Produces: `met_for_speed(speed_kmh: float) -> float`, `calories_burned(distance_km: float, duration_s: int, weight_kg: float) -> float`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calc.py`:

```python
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

    def test_non_positive_speed_raises(self):
        with pytest.raises(ValueError):
            calc.met_for_speed(0.0)


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

    def test_non_positive_distance_raises(self):
        with pytest.raises(ValueError):
            calc.calories_burned(0.0, 50 * 60, 70.0)

    def test_non_positive_duration_raises(self):
        with pytest.raises(ValueError):
            calc.calories_burned(10.0, 0, 70.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calc.py -v`
Expected: FAIL — `AttributeError: module 'runfuel.calc' has no attribute 'met_for_speed'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/runfuel/calc.py`:

```python
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
    if weight_kg <= 0:
        raise ValueError(f"weight must be greater than zero, got {weight_kg}")

    met = met_for_speed(speed_kmh(distance_km, duration_s))
    duration_minutes = duration_s / 60
    return met * 3.5 * weight_kg / 200 * duration_minutes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calc.py -v`
Expected: PASS — the full `calc` suite, roughly 55 tests.

- [ ] **Step 5: Commit**

```bash
git add src/runfuel/calc.py tests/test_calc.py
git commit -m "feat: estimate calorie burn from banded MET lookup"
```

---

### Task 5: Configuration and models

**Files:**
- Create: `src/runfuel/config.py`, `src/runfuel/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `runfuel.calc` from Tasks 2–4.
- Produces: `Settings(db_path: Path, weight_kg: float)`, `load_settings() -> Settings`, `Run(id, run_date, distance_km, duration_seconds)`, `RunView.from_run(run: Run, weight_kg: float) -> RunView` with fields `id`, `run_date`, `distance_km`, `duration_seconds`, `duration`, `pace`, `calories`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runfuel.config'`

- [ ] **Step 3: Write minimal implementation**

Create `src/runfuel/config.py`:

```python
"""Environment-backed settings."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = "runfuel.db"
DEFAULT_WEIGHT_KG = 70.0


@dataclass(frozen=True)
class Settings:
    db_path: Path
    weight_kg: float


def load_settings() -> Settings:
    """Build settings from the environment, falling back to defaults."""
    return Settings(
        db_path=Path(os.environ.get("RUNFUEL_DB_PATH", DEFAULT_DB_PATH)),
        weight_kg=float(os.environ.get("RUNFUEL_WEIGHT_KG", DEFAULT_WEIGHT_KG)),
    )
```

Create `src/runfuel/models.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/runfuel/config.py src/runfuel/models.py tests/test_models.py
git commit -m "feat: add settings and run view models"
```

---

### Task 6: SQLite schema and repository

**Files:**
- Create: `src/runfuel/schema.sql`, `src/runfuel/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `Run` from Task 5.
- Produces: `connect(db_path: Path) -> sqlite3.Connection`, `init_db(conn) -> None`, `add_run(conn, run_date: date, distance_km: float, duration_seconds: int) -> int`, `list_runs(conn) -> list[Run]`, `delete_run(conn, run_id: int) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_db.py`:

```python
import sqlite3
import threading
from datetime import date

import pytest

from runfuel import db
from runfuel.models import Run


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.init_db(connection)
    yield connection
    connection.close()


class TestAddAndList:
    def test_add_returns_the_new_id(self, conn):
        run_id = db.add_run(conn, date(2026, 8, 27), 10.0, 3000)

        assert isinstance(run_id, int)
        assert run_id > 0

    def test_round_trips_a_run(self, conn):
        db.add_run(conn, date(2026, 8, 27), 10.0, 3000)

        runs = db.list_runs(conn)

        assert len(runs) == 1
        assert runs[0] == Run(
            id=runs[0].id,
            run_date=date(2026, 8, 27),
            distance_km=10.0,
            duration_seconds=3000,
        )

    def test_lists_newest_first(self, conn):
        db.add_run(conn, date(2026, 8, 1), 5.0, 1500)
        db.add_run(conn, date(2026, 8, 27), 10.0, 3000)
        db.add_run(conn, date(2026, 8, 15), 7.0, 2100)

        dates = [run.run_date for run in db.list_runs(conn)]

        assert dates == [date(2026, 8, 27), date(2026, 8, 15), date(2026, 8, 1)]

    def test_empty_database_lists_nothing(self, conn):
        assert db.list_runs(conn) == []


class TestDelete:
    def test_removes_the_row(self, conn):
        run_id = db.add_run(conn, date(2026, 8, 27), 10.0, 3000)

        assert db.delete_run(conn, run_id) is True
        assert db.list_runs(conn) == []

    def test_reports_false_for_unknown_id(self, conn):
        assert db.delete_run(conn, 999) is False


class TestConstraints:
    def test_rejects_non_positive_distance(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            db.add_run(conn, date(2026, 8, 27), 0.0, 3000)

    def test_rejects_non_positive_duration(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            db.add_run(conn, date(2026, 8, 27), 10.0, 0)


class TestThreadHandoff:
    def test_connection_survives_use_from_another_thread(self, conn):
        """FastAPI hands the connection between threadpool threads."""
        db.add_run(conn, date(2026, 8, 27), 10.0, 3000)
        result = {}

        def read_from_another_thread():
            try:
                result["runs"] = db.list_runs(conn)
            except Exception as exc:  # noqa: BLE001 - recorded for the assert
                result["error"] = exc

        worker = threading.Thread(target=read_from_another_thread)
        worker.start()
        worker.join()

        assert "error" not in result, result.get("error")
        assert len(result["runs"]) == 1


class TestInitIsIdempotent:
    def test_can_be_called_twice(self, tmp_path):
        connection = db.connect(tmp_path / "twice.db")
        db.init_db(connection)
        db.init_db(connection)
        assert db.list_runs(connection) == []
        connection.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runfuel.db'`

- [ ] **Step 3: Write minimal implementation**

Create `src/runfuel/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         TEXT    NOT NULL,
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

Create `src/runfuel/db.py`:

```python
"""SQLite persistence.

This module knows SQL and nothing about HTTP. It speaks in ``Run`` objects so
that callers never handle raw rows.
"""

import sqlite3
from datetime import date
from importlib import resources
from pathlib import Path

from runfuel.models import Run


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with row access by column name.

    ``check_same_thread=False`` is required, not incidental: FastAPI runs a
    sync dependency and a sync endpoint on different threadpool threads, so a
    connection opened in ``get_connection`` is used — and closed — from another
    thread. Each request still gets its own connection and closes it, so no
    connection is ever shared between concurrent requests.
    """
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    """Create the schema if it is not already there. Safe to call repeatedly."""
    schema = resources.files("runfuel").joinpath("schema.sql").read_text()
    connection.executescript(schema)
    connection.commit()


def add_run(
    connection: sqlite3.Connection,
    run_date: date,
    distance_km: float,
    duration_seconds: int,
) -> int:
    """Insert one run and return its new id."""
    cursor = connection.execute(
        "INSERT INTO runs (run_date, distance_km, duration_seconds)"
        " VALUES (?, ?, ?)",
        (run_date.isoformat(), distance_km, duration_seconds),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_runs(connection: sqlite3.Connection) -> list[Run]:
    """Every run, newest first."""
    rows = connection.execute(
        "SELECT id, run_date, distance_km, duration_seconds"
        " FROM runs ORDER BY run_date DESC, id DESC"
    ).fetchall()
    return [
        Run(
            id=row["id"],
            run_date=date.fromisoformat(row["run_date"]),
            distance_km=row["distance_km"],
            duration_seconds=row["duration_seconds"],
        )
        for row in rows
    ]


def delete_run(connection: sqlite3.Connection, run_id: int) -> bool:
    """Delete one run. Returns whether a row was actually removed."""
    cursor = connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    connection.commit()
    return cursor.rowcount > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/runfuel/schema.sql src/runfuel/db.py tests/test_db.py
git commit -m "feat: add sqlite schema and run repository"
```

---

### Task 7: FastAPI routes and templates

**Files:**
- Create: `src/runfuel/app.py`, `src/runfuel/templates/base.html`, `src/runfuel/templates/index.html`
- Create: `tests/conftest.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: `load_settings`/`Settings` (Task 5), `RunView.from_run` (Task 5), `connect`/`init_db`/`add_run`/`list_runs`/`delete_run` (Task 6), `calc.parse_duration`/`format_duration` (Tasks 2–4).
- Produces: `create_app(settings: Settings) -> FastAPI` and a module-level `app` for `uvicorn runfuel.app:app`.

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from runfuel import db
from runfuel.app import create_app
from runfuel.config import Settings


@pytest.fixture()
def settings(tmp_path):
    """Point the app at a throwaway database, never a developer's real one."""
    return Settings(db_path=tmp_path / "test.db", weight_kg=70.0)


@pytest.fixture()
def client(settings):
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def conn(client, settings):
    """Depends on `client` so the app has created the schema first."""
    connection = db.connect(settings.db_path)
    yield connection
    connection.close()
```

Create `tests/test_routes.py`:

```python
from runfuel import db


class TestIndex:
    def test_empty_state_renders(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "No runs logged yet" in response.text


class TestLoggingARun:
    def test_valid_run_redirects_and_persists(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        runs = db.list_runs(conn)
        assert len(runs) == 1
        assert runs[0].distance_km == 10.0
        assert runs[0].duration_seconds == 3000

    def test_logged_run_appears_with_derived_values(self, client):
        client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
        )

        body = client.get("/").text

        assert "5:00 /km" in body
        assert "643" in body

    def test_malformed_duration_returns_400_and_writes_nothing(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "nonsense"},
        )

        assert response.status_code == 400
        assert "error" in response.text.lower()
        assert db.list_runs(conn) == []

    def test_zero_distance_returns_400_and_writes_nothing(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "0", "duration": "50:00"},
        )

        assert response.status_code == 400
        assert db.list_runs(conn) == []

    def test_submitted_values_survive_the_error_rerender(self, client):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "0", "duration": "50:00"},
        )

        assert response.status_code == 400
        # 0.0 is falsy: the form must still echo it back, not blank the field.
        assert 'value="0.0"' in response.text
        assert 'value="50:00"' in response.text

    def test_malformed_date_is_rejected_by_validation(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "not-a-date", "distance_km": "10", "duration": "50:00"},
        )

        assert response.status_code == 422
        assert db.list_runs(conn) == []


class TestDeletingARun:
    def test_delete_removes_the_run(self, client, conn):
        client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
        )
        run_id = db.list_runs(conn)[0].id

        response = client.post(f"/runs/{run_id}/delete", follow_redirects=False)

        assert response.status_code == 303
        assert db.list_runs(conn) == []


class TestTotals:
    def test_totals_sum_across_runs(self, client):
        client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
        )
        client.post(
            "/runs",
            data={"run_date": "2026-08-26", "distance_km": "5", "duration": "25:00"},
        )

        body = client.get("/").text

        assert "15.0" in body  # total distance
        assert "1:15:00" in body  # total duration
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runfuel.app'`

- [ ] **Step 3: Write minimal implementation**

Create `src/runfuel/app.py`:

```python
"""HTTP layer: routes, forms, and rendering.

Holds no calculation logic of its own — it calls ``calc`` and ``db``.
"""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from runfuel import calc, db
from runfuel.config import Settings, load_settings
from runfuel.models import RunView

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _totals(views: list[RunView]) -> dict:
    total_seconds = sum(view.duration_seconds for view in views)
    return {
        "count": len(views),
        "distance_km": round(sum(view.distance_km for view in views), 2),
        "duration": calc.format_duration(total_seconds),
        "calories": round(sum(view.calories for view in views)),
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application against a given configuration.

    Taking settings as an argument is what lets tests point the whole stack at
    a temporary database.
    """
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Create the schema on startup rather than at import time: the
        # module-level create_app() below must not touch the filesystem just
        # because something imported runfuel.app. init_db is idempotent.
        connection = db.connect(settings.db_path)
        db.init_db(connection)
        connection.close()
        yield

    app = FastAPI(title="RunFuel", lifespan=lifespan)

    def get_connection():
        connection = db.connect(settings.db_path)
        try:
            yield connection
        finally:
            connection.close()

    def _render(request: Request, connection, *, error: str | None = None,
                form: dict | None = None, status_code: int = 200):
        views = [
            RunView.from_run(run, settings.weight_kg)
            for run in db.list_runs(connection)
        ]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "runs": views,
                "totals": _totals(views),
                "error": error,
                "form": form or {},
                "today": date.today().isoformat(),
                "weight_kg": settings.weight_kg,
            },
            status_code=status_code,
        )

    @app.get("/")
    def index(request: Request, connection=Depends(get_connection)):
        return _render(request, connection)

    @app.post("/runs")
    def create_run(
        request: Request,
        run_date: date = Form(...),
        distance_km: float = Form(...),
        duration: str = Form(...),
        connection=Depends(get_connection),
    ):
        try:
            duration_seconds = calc.parse_duration(duration)
            # Validate distance through the same pure guard the calculations use.
            calc.pace_seconds_per_km(distance_km, duration_seconds)
        except ValueError as exc:
            return _render(
                request,
                connection,
                error=str(exc),
                form={
                    "run_date": run_date.isoformat(),
                    "distance_km": distance_km,
                    "duration": duration,
                },
                status_code=400,
            )

        db.add_run(connection, run_date, distance_km, duration_seconds)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/runs/{run_id}/delete")
    def remove_run(run_id: int, connection=Depends(get_connection)):
        db.delete_run(connection, run_id)
        return RedirectResponse(url="/", status_code=303)

    return app


app = create_app()
```

Create `src/runfuel/templates/base.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}RunFuel{% endblock %}</title>
    <style>
      :root { color-scheme: light dark; }
      body {
        font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        max-width: 60rem;
        margin: 2rem auto;
        padding: 0 1rem;
        line-height: 1.5;
      }
      h1 { margin-bottom: 0.25rem; }
      .subtitle { opacity: 0.7; margin-top: 0; }
      form.log { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; margin: 1.5rem 0; }
      label { display: flex; flex-direction: column; font-size: 0.85rem; gap: 0.25rem; }
      input { padding: 0.4rem; font-size: 1rem; }
      button { padding: 0.45rem 0.9rem; font-size: 1rem; cursor: pointer; }
      table { border-collapse: collapse; width: 100%; }
      th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid rgba(128,128,128,0.3); }
      tfoot td { font-weight: 600; }
      .numeric { text-align: right; font-variant-numeric: tabular-nums; }
      .error { padding: 0.75rem 1rem; border-left: 4px solid crimson; background: rgba(220,20,60,0.08); }
      .empty { opacity: 0.7; font-style: italic; }
    </style>
  </head>
  <body>
    {% block content %}{% endblock %}
  </body>
</html>
```

Create `src/runfuel/templates/index.html`:

```html
{% extends "base.html" %}

{% block content %}
<h1>RunFuel</h1>
<p class="subtitle">Calories estimated at {{ weight_kg }} kg.</p>

{% if error %}
<p class="error"><strong>Error:</strong> {{ error }}</p>
{% endif %}

<form class="log" method="post" action="/runs">
  <label>
    Date
    <input type="date" name="run_date" value="{{ form.get('run_date') or today }}" required />
  </label>
  <label>
    Distance (km)
    <input type="number" name="distance_km" step="0.01" min="0.01"
           value="{{ form.get('distance_km', '') }}" required />
  </label>
  <label>
    Duration (MM:SS)
    <input type="text" name="duration" placeholder="50:00"
           value="{{ form.get('duration', '') }}" required />
  </label>
  <button type="submit">Log run</button>
</form>

{% if runs %}
<table>
  <thead>
    <tr>
      <th>Date</th>
      <th class="numeric">Distance</th>
      <th class="numeric">Duration</th>
      <th class="numeric">Pace</th>
      <th class="numeric">Calories</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    {% for run in runs %}
    <tr>
      <td>{{ run.run_date.isoformat() }}</td>
      <td class="numeric">{{ "%.2f"|format(run.distance_km) }} km</td>
      <td class="numeric">{{ run.duration }}</td>
      <td class="numeric">{{ run.pace }}</td>
      <td class="numeric">{{ run.calories|round|int }}</td>
      <td>
        <form method="post" action="/runs/{{ run.id }}/delete">
          <button type="submit">Delete</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </tbody>
  <tfoot>
    <tr>
      <td>{{ totals.count }} run{{ '' if totals.count == 1 else 's' }}</td>
      <td class="numeric">{{ totals.distance_km }} km</td>
      <td class="numeric">{{ totals.duration }}</td>
      <td class="numeric">&mdash;</td>
      <td class="numeric">{{ totals.calories }}</td>
      <td></td>
    </tr>
  </tfoot>
</table>
{% else %}
<p class="empty">No runs logged yet. Add your first one above.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_routes.py -v`
Expected: PASS (9 tests)

If `test_totals_sum_across_runs` fails on the `"15.0"` assertion, check that `_totals` rounds to 2 decimals — `round(15.0, 2)` renders as `15.0`, which is what the assertion expects.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS — every test from Tasks 1–7.

- [ ] **Step 6: Commit**

```bash
git add src/runfuel/app.py src/runfuel/templates tests/conftest.py tests/test_routes.py
git commit -m "feat: add FastAPI routes and Jinja2 templates"
```

---

### Task 8: README and manual smoke run

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `create_app`/`app` from Task 7.
- Produces: nothing code-facing; documents how to run the app.

- [ ] **Step 1: Start the server against a scratch database**

```bash
RUNFUEL_DB_PATH=/tmp/runfuel-smoke.db uv run uvicorn runfuel.app:app --port 8765 &
```

Wait for it to accept connections, then confirm the empty state:

```bash
curl -s http://127.0.0.1:8765/ | grep -c "No runs logged yet"
```

Expected: `1`.

- [ ] **Step 2: Log a run over HTTP**

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' -X POST http://127.0.0.1:8765/runs -d "run_date=2026-08-27" -d "distance_km=10" -d "duration=50:00"
```

Expected: `303 http://127.0.0.1:8765/` — the POST-redirect-GET response, not a 200.

- [ ] **Step 3: Confirm the derived values render**

```bash
curl -s http://127.0.0.1:8765/ | grep -oE '5:00 /km|643|10\.00 km|1 run'
```

Expected: all four present — the pace, the calorie estimate, the distance, and the totals count.

- [ ] **Step 4: Confirm re-fetching does not double-log, then delete**

Fetch `/` twice more and count the delete buttons — each row has exactly one:

```bash
curl -s http://127.0.0.1:8765/ > /dev/null; curl -s http://127.0.0.1:8765/ | grep -c "Delete"
```

Expected: `1` — re-fetching after the redirect re-issues GET, never the POST.

Then delete the run and confirm the empty state returns:

```bash
curl -s -X POST http://127.0.0.1:8765/runs/1/delete -o /dev/null -w '%{http_code}\n'; curl -s http://127.0.0.1:8765/ | grep -c "No runs logged yet"
```

Expected: `303` then `1`. Stop the server (`kill %1`) and remove `/tmp/runfuel-smoke.db`.

- [ ] **Step 5: Write the README**

Replace `README.md` with:

````markdown
# RunFuel

A personal running log. Record a run's date, distance, and duration; RunFuel
derives your pace and estimates calories burned.

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn runfuel.app:app --reload
```

Then open http://127.0.0.1:8000.

## Test

```bash
uv run pytest
```

Run a single test file or a single test:

```bash
uv run pytest tests/test_calc.py -v
uv run pytest tests/test_calc.py::TestCalories::test_reference_ten_km_in_fifty_minutes -v
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RUNFUEL_DB_PATH` | `runfuel.db` | SQLite file location |
| `RUNFUEL_WEIGHT_KG` | `70.0` | Body weight used for calorie estimates |

## How calories are estimated

Speed determines a MET value from a banded lookup based on the ACSM Compendium
running entries, then:

```
kcal = MET * 3.5 * weight_kg / 200 * duration_minutes
```

Because the table is banded, burn is not monotonic in speed — running the same
distance faster can yield a lower estimate. That is a known property of the
model, not a bug.

## Design

See `docs/superpowers/specs/2026-08-27-runfuel-design.md`.
````

- [ ] **Step 6: Confirm the suite is still green**

Run: `uv run pytest`
Expected: PASS, all tests.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: document setup, running, and the calorie model"
```
