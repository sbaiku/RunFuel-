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
