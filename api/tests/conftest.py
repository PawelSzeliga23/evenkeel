import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://portfolio:portfolio@localhost:5433/portfolio_test",
)

BASE_SETTINGS = {
    "database_url": TEST_DATABASE_URL,
    "jwt_secret": "test-secret-that-is-at-least-32-bytes-long",
    "cookie_secure": False,
    "registration_mode": "open",
    "invite_codes": "",
    "login_rate_limit_per_minute": 10,
    "register_rate_limit_per_minute": 5,
}


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def clean_db(engine: Engine) -> None:
    """Empties every application table before the test (schema stays)."""
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars().all()
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def settings() -> Settings:
    return Settings(**BASE_SETTINGS)


@pytest.fixture
def make_app(engine: Engine, clean_db: None) -> Callable[..., FastAPI]:
    def _make(**overrides: object) -> FastAPI:
        app_settings = Settings(**{**BASE_SETTINGS, **overrides})
        app = create_app(app_settings)
        test_sessionmaker = sessionmaker(bind=engine, expire_on_commit=False)

        def _get_db() -> Iterator[Session]:
            with test_sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_settings] = lambda: app_settings
        return app

    return _make


@pytest.fixture
def client(make_app: Callable[..., FastAPI]) -> TestClient:
    return TestClient(make_app())
