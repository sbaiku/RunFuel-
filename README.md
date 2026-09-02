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

After each run, RunFuel suggests a meal sized to what you burned: it picks the
recipe and whole serving count (up to three) whose total calories land closest,
and shows it above the weekly summary. Only dish names and published
per-serving nutrition are stored - the recipes themselves belong to their
authors and are not reproduced here.

If you have a database from before the felt rating existed, it is upgraded in
place the next time the app starts; existing runs simply show no rating.

## Docker

```bash
docker build -t runfuel .
docker run -d -p 8000:8000 -v runfuel-data:/data runfuel
```

Then open http://127.0.0.1:8000.

The image is a two-stage build on `python:3.13-slim`: dependencies are
installed in a builder stage and only the finished virtualenv is copied into a
clean runtime image, which carries no uv, no compilers and no lockfile. The app
runs as the unprivileged user `appuser` (uid 1000).

**Mount something at `/data` or your log dies with the container.** Inside the
image `RUNFUEL_DB_PATH` points at `/data/runfuel.db`; without a volume that
path lives in the container's own writable layer and is discarded when the
container is removed.

If you bind-mount a host directory rather than a named volume, the host
directory must be writable by uid 1000 - a bind mount keeps the host's
ownership, so a root-owned directory will leave the app unable to write.

`GET /health` returns `{"status": "ok"}`, or 503 if the database cannot be
reached. It is wired to a Docker `HEALTHCHECK` and is what a deploy platform
should probe. It deliberately queries the database rather than only confirming
the process is alive, so a broken volume mount reports unhealthy instead of
pretending everything is fine.

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
