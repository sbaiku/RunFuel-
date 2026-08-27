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

## What it records

Each run stores a date, a distance in kilometres, a duration, and an optional
"how it felt" rating from 1 to 5. Pace and calories are derived on read, never
stored. Runs are grouped into ISO weeks (Monday-Sunday) in a summary above the
log, where average pace comes from the week's totals rather than a mean of the
individual paces - so a short run does not weigh as heavily as a long one.

If you have a database from before the felt rating existed, it is upgraded in
place the next time the app starts; existing runs simply show no rating.

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
