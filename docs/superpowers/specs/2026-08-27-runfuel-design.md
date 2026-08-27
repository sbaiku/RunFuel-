# RunFuel — Design

**Date:** 2026-08-27
**Status:** Approved for planning

## Purpose

A personal running log. Record a run (date, distance, duration); see every run in
a table with its derived pace and estimated calorie burn, plus running totals.
Single user, single machine, no auth.

## Scope

In scope:

- Log a run: date, distance (km), duration (`MM:SS` or `HH:MM:SS`)
- List all runs, newest first, with derived pace and calories
- Season totals: run count, total distance, total duration, total calories
- Delete a run

Explicitly out of scope: editing a run, authentication, a JSON API, multi-user
support, migrations, imperial units.

## Architecture

Layered, with one hard boundary: `calc.py` imports nothing else in the package.

```
RunFuel/
├── pyproject.toml            # uv-managed, hatchling backend, src layout
├── .python-version
├── .gitignore
├── README.md
├── src/
│   └── runfuel/
│       ├── __init__.py
│       ├── config.py         # Settings: RUNFUEL_DB_PATH, RUNFUEL_WEIGHT_KG
│       ├── calc.py           # PURE: parsing, pace, MET lookup, calories
│       ├── models.py         # Run dataclass + RunView (run + derived values)
│       ├── schema.sql        # CREATE TABLE runs (...)
│       ├── db.py             # connection, init_db, add_run, list_runs, delete_run
│       ├── app.py            # FastAPI routes + Jinja2 rendering
│       └── templates/
│           ├── base.html
│           └── index.html
└── tests/
    ├── conftest.py
    ├── test_calc.py
    └── test_routes.py
```

Responsibilities:

- `calc.py` — floats in, floats out. No FastAPI, no SQLite, no templates. This is
  where the tested logic lives.
- `db.py` — knows SQL, not HTTP. Functions take and return `Run` objects.
- `app.py` — knows HTTP, calls the other two. Holds no calculation logic.
- `config.py` — reads environment, supplies defaults.

The rationale for the boundary: pace and calorie correctness is the part worth
testing hard, and it should be testable without spinning up an app or a database.

## Persistence

Python stdlib `sqlite3` with a thin repository module. No ORM: the domain is one
table with five columns, and routes talk to repository functions rather than to
SQL, so introducing SQLAlchemy later stays a contained change.

```sql
CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         TEXT    NOT NULL,   -- ISO-8601 YYYY-MM-DD
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

Pace and calories are **derived, never stored** — they are a pure function of the
stored columns plus configured body weight, so storing them would invite drift if
weight or the formula changes.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RUNFUEL_DB_PATH` | `./runfuel.db` | SQLite file location |
| `RUNFUEL_WEIGHT_KG` | `70.0` | Body weight used for calorie estimates |

Body weight is app-level rather than per-run: it changes slowly, and re-entering
it on every log is friction for no accuracy gain at this scale.

## Calculation model

### Pace

`pace_seconds_per_km = duration_seconds / distance_km`, formatted `M:SS /km` with
the seconds rounded to the nearest whole second and carried (`359.6 s` renders as
`6:00 /km`, never `5:60 /km`).

### Calories

Banded MET lookup on speed, following the ACSM Compendium running entries. Lower
bound inclusive, upper bound exclusive:

| Speed (km/h) | MET |
|---|---|
| < 6.4 | 6.0 |
| 6.4 – 8.0 | 8.3 |
| 8.0 – 9.7 | 9.0 |
| 9.7 – 11.3 | 9.8 |
| 11.3 – 12.9 | 10.5 |
| 12.9 – 14.5 | 11.0 |
| 14.5 – 16.1 | 11.8 |
| 16.1 – 17.7 | 12.3 |
| 17.7 – 19.3 | 14.5 |
| >= 19.3 | 16.0 |

Then:

```
kcal = MET * 3.5 * weight_kg / 200 * duration_minutes
```

Worked reference: 10 km in 50:00 at 70 kg. Speed = 12.0 km/h, MET = 10.5,
duration = 50 min, so `10.5 * 3.5 * 70 / 200 * 50 = 643.125` kcal.

**Known property of this model:** calories at fixed distance are *not* monotonic
in speed, because burn scales as `MET(speed) / speed` and the step function is not
monotonic in that ratio. The same 10 km at 15.0 km/h yields 578.2 kcal, less than
at 12.0 km/h. This is an accepted artifact of a banded table, not a defect, and
the test suite must not assert monotonicity in speed.

## Public interface of `calc.py`

```python
parse_duration(text: str) -> int             # "45:30" | "1:05:30" -> seconds
format_duration(seconds: int) -> str
speed_kmh(distance_km: float, duration_s: int) -> float
pace_seconds_per_km(distance_km: float, duration_s: int) -> float
format_pace(seconds_per_km: float) -> str    # "5:00 /km"
met_for_speed(speed_kmh: float) -> float
calories_burned(distance_km: float, duration_s: int, weight_kg: float) -> float
```

## Routes and data flow

| Route | Behavior |
|---|---|
| `GET /` | `list_runs()` -> wrap each row in a `RunView` carrying derived pace and calories -> render `index.html` with the table and totals |

Totals are aggregated in `app.py` from the `RunView` list, not in SQL — calories
are derived rather than stored, so they cannot be summed by the database.
| `POST /runs` | `Form(...)` params -> `parse_duration` -> `add_run` -> 303 redirect to `/` |
| `POST /runs/{id}/delete` | `delete_run` -> 303 redirect to `/` |

Both mutating routes use POST-redirect-GET so that a browser refresh cannot
double-log or re-delete.

## Error handling

`run_date` is declared as `datetime.date` on the form parameter, so FastAPI
coerces and validates it and returns its own 422 for a malformed date; it is
stored as an ISO-8601 string. Duration is received as `str` because its format is
domain-specific, and is validated by `calc.parse_duration`.

`calc.py` raises `ValueError` for non-positive distance, non-positive duration,
and unparseable duration text. `app.py` catches `ValueError` at the route
boundary and re-renders `index.html` with an error banner and the submitted
values preserved, returning HTTP 400. No stack trace reaches the user, and no
invalid row is written. The `CHECK` constraints in the schema are the backstop.

## Testing

`tests/test_calc.py` — the substance of the suite, pure and fast:

- **Pace:** 10 km in 50:00 -> 300 s/km -> `"5:00 /km"`; rounding carry at 359.6 s
- **Duration parsing:** `MM:SS`, `HH:MM:SS`, and malformed input raising `ValueError`
- **MET bands:** each boundary speed exactly, and values just either side of it
- **Calories:** two hand-computed reference points — 10 km in 50:00 at 70 kg ->
  643.125 kcal, and 10 km in 40:00 at 70 kg -> 578.2 kcal; exact linearity in
  weight (doubling weight doubles kcal); linearity in duration within a single band
- **Guards:** zero and negative distance and duration raise `ValueError`

`tests/test_routes.py` — a thinner integration pass over a tmp-path database:

- POST a valid run -> 303 -> row persisted -> appears in `GET /` with its pace
- POST malformed duration -> 400, error banner present, no row written
- POST to the delete route removes the row

`conftest.py` provides a tmp-path SQLite fixture and a `TestClient` bound to it,
so tests never touch a developer's real `runfuel.db`.

## Tooling

`uv` for dependency management and virtualenv. `hatchling` build backend with the
`src/` layout, so the package is imported as installed rather than by accident of
the working directory. Runtime dependencies: `fastapi`, `uvicorn[standard]`,
`jinja2`, `python-multipart` (required for form parsing). Dev dependency group:
`pytest`, `httpx` (needed by `TestClient`).
