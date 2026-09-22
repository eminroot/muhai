"""Shared pytest fixtures.

The suite is deliberately split: the service-layer tests are pure and need no
database, while the API smoke tests exercise the FastAPI app object. The app's
lifespan swallows migration failures, so the TestClient starts even when no
database is reachable.
"""
import pytest


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
