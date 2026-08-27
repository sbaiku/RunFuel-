"""HTTP layer: routes, forms, and rendering.

Holds no calculation logic of its own — it calls ``calc`` and ``db``.
"""

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
    app = FastAPI(title="RunFuel")

    # Create the schema up front: init_db is idempotent, and doing it here
    # rather than in a startup hook keeps the app usable the moment it is built.
    _bootstrap = db.connect(settings.db_path)
    db.init_db(_bootstrap)
    _bootstrap.close()

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
