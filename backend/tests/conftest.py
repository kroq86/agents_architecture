"""Pytest setup: env and DB before any `app` import during collection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_TEST_DB = Path(__file__).resolve().parent / "test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("APP_ENV", "local")


def pytest_configure(config: pytest.Config) -> None:
    _TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND,
        check=True,
        env={**os.environ},
    )
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.db.session import reset_engine_for_tests

    reset_engine_for_tests()


@pytest.fixture(autouse=True)
def _reset_settings_and_engine_after_each_test():
    yield
    from app.core.config import get_settings
    from app.db.session import reset_engine_for_tests

    get_settings.cache_clear()
    reset_engine_for_tests()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())
