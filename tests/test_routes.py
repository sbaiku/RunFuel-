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
