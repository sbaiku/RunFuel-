from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from runfuel import db
from runfuel.app import create_app
from runfuel.config import Settings


class TestIndex:
    def test_empty_state_renders(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "No runs logged yet" in response.text

    def test_concurrent_requests_all_succeed(self, client):
        with ThreadPoolExecutor(8) as ex:
            codes = [f.result().status_code for f in [ex.submit(client.get, "/") for _ in range(40)]]
        assert set(codes) == {200}

    def test_building_the_app_creates_no_database(self, settings):
        create_app(settings)
        assert not settings.db_path.exists()


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
        assert "duration must be" in response.text
        assert db.list_runs(conn) == []

    def test_zero_distance_returns_400_and_writes_nothing(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "0", "duration": "50:00"},
        )

        assert response.status_code == 400
        assert db.list_runs(conn) == []

    @pytest.mark.parametrize("distance", ["inf", "1e309", "nan"])
    def test_non_finite_distance_returns_400_and_writes_nothing(self, client, conn, distance):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": distance, "duration": "50:00"},
        )

        assert response.status_code == 400
        assert db.list_runs(conn) == []

        # The index page must still render afterward: a non-finite value must
        # never reach the database and permanently break the index page.
        follow_up = client.get("/")
        assert follow_up.status_code == 200

    def test_submitted_values_survive_the_error_rerender(self, client):
        response = client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "0", "duration": "50:00"},
        )

        assert response.status_code == 400
        # 0.0 is falsy: the form must still echo it back, not blank the field.
        assert 'value="0.0"' in response.text
        assert 'value="50:00"' in response.text
        assert 'value="2026-08-27"' in response.text

    def test_malformed_date_is_rejected_by_validation(self, client, conn):
        response = client.post(
            "/runs",
            data={"run_date": "not-a-date", "distance_km": "10", "duration": "50:00"},
        )

        assert response.status_code == 422
        assert db.list_runs(conn) == []


class TestWeight:
    def test_weight_flows_end_to_end_through_a_route(self, tmp_path):
        heavy_settings = Settings(db_path=tmp_path / "heavy.db", weight_kg=140.0)
        app = create_app(heavy_settings)
        with TestClient(app) as heavy_client:
            heavy_client.post(
                "/runs",
                data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
            )

            body = heavy_client.get("/").text

        # Reference is 643 calories at 70 kg; doubling the weight to 140 kg
        # must exactly double the rendered calorie figure.
        assert "1286" in body


class TestOrdering:
    def test_newer_run_appears_first_through_http(self, client):
        client.post(
            "/runs",
            data={"run_date": "2026-08-01", "distance_km": "5", "duration": "25:00"},
        )
        client.post(
            "/runs",
            data={"run_date": "2026-08-27", "distance_km": "10", "duration": "50:00"},
        )

        body = client.get("/").text

        assert body.index("2026-08-27") < body.index("2026-08-01")


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

        assert "15.00" in body  # total distance
        assert "1:15:00" in body  # total duration
