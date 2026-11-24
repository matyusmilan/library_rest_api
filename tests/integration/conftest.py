"""
Shared fixtures for integration tests.

Each test gets a fresh in-memory SQLite database and a FastAPI TestClient
wired to it, so tests are fully isolated from each other and from the
development database.
"""

import pytest
from fastapi.testclient import TestClient
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = "sqlite://"  # pure in-memory, no file


@pytest.fixture(autouse=True, scope="session")
def reset_otel():
    """
    Replace the global OTel providers with no-op instances for the test session.
    This prevents the console exporters (configured for local dev) from trying
    to write to stdout after pytest has already closed it, which would produce
    harmless but noisy 'I/O operation on closed file' tracebacks.
    """
    trace.set_tracer_provider(TracerProvider())
    metrics.set_meter_provider(MeterProvider())


@pytest.fixture
def client() -> TestClient:
    """
    Provide a TestClient backed by a fresh in-memory SQLite database.
    The database is created before the test and torn down after it.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single connection shared across threads
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)
