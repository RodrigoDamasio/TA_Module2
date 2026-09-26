import pytest
from fakes import FakeLLM, report, text
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm, get_rate_limiter
from app.api.guards import RateLimiter
from app.main import app


@pytest.fixture
def llm():
    """Scripted fake LLM; each test pushes the responses it needs."""
    return FakeLLM([])


@pytest.fixture
def limiter():
    return RateLimiter(per_minute=5, per_day=50)


@pytest.fixture
def client(tmp_path, monkeypatch, llm, limiter):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BASE_URL", "http://test.local")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-never-used")
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def good_run():
    """Responses for one successful single-chunk analysis without tools."""
    return [text(), report()]
