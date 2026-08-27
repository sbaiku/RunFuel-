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
