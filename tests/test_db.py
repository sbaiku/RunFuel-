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

    def test_same_date_runs_break_ties_newest_id_first(self, conn):
        first_id = db.add_run(conn, date(2026, 8, 27), 5.0, 1500)
        second_id = db.add_run(conn, date(2026, 8, 27), 10.0, 3000)

        ids = [run.id for run in db.list_runs(conn)]

        assert ids == [second_id, first_id]


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


OLD_SCHEMA = """
CREATE TABLE runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         TEXT    NOT NULL,
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def _columns(connection) -> set[str]:
    return {row["name"] for row in connection.execute("PRAGMA table_info(runs)")}


class TestFelt:
    def test_round_trips_a_rating(self, conn):
        db.add_run(conn, date(2026, 8, 27), 10.0, 3000, felt=4)

        assert db.list_runs(conn)[0].felt == 4

    def test_a_run_without_a_rating_reads_back_as_none(self, conn):
        db.add_run(conn, date(2026, 8, 27), 10.0, 3000)

        assert db.list_runs(conn)[0].felt is None

    @pytest.mark.parametrize("felt", [0, 6, -1])
    def test_schema_rejects_ratings_outside_one_to_five(self, conn, felt):
        with pytest.raises(sqlite3.IntegrityError):
            db.add_run(conn, date(2026, 8, 27), 10.0, 3000, felt=felt)


class TestUpgradingAnExistingDatabase:
    """`CREATE TABLE IF NOT EXISTS` cannot add a column to a table that exists."""

    def test_init_db_adds_felt_to_a_pre_existing_table(self, tmp_path):
        path = tmp_path / "old.db"
        connection = db.connect(path)
        connection.executescript(OLD_SCHEMA)
        connection.execute(
            "INSERT INTO runs (run_date, distance_km, duration_seconds)"
            " VALUES ('2026-08-27', 10.0, 3000)"
        )
        connection.commit()
        assert "felt" not in _columns(connection)

        db.init_db(connection)

        assert "felt" in _columns(connection)
        connection.close()

    def test_rows_logged_before_the_upgrade_survive_it(self, tmp_path):
        path = tmp_path / "old.db"
        connection = db.connect(path)
        connection.executescript(OLD_SCHEMA)
        connection.execute(
            "INSERT INTO runs (run_date, distance_km, duration_seconds)"
            " VALUES ('2026-08-27', 10.0, 3000)"
        )
        connection.commit()

        db.init_db(connection)

        runs = db.list_runs(connection)
        assert len(runs) == 1
        assert runs[0].distance_km == 10.0
        assert runs[0].felt is None
        connection.close()

    def test_new_runs_are_loggable_after_the_upgrade(self, tmp_path):
        path = tmp_path / "old.db"
        connection = db.connect(path)
        connection.executescript(OLD_SCHEMA)
        connection.commit()

        db.init_db(connection)
        db.add_run(connection, date(2026, 8, 27), 10.0, 3000, felt=5)

        assert db.list_runs(connection)[0].felt == 5
        connection.close()
