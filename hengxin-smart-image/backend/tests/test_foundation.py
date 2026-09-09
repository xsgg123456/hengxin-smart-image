import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENABLE_TEST_JOBS", "false")
    get_settings.cache_clear()
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result
    get_settings.cache_clear()


def test_production_rejects_test_jobs():
    with pytest.raises(ValidationError, match="forbidden"):
        Settings(app_env="production", enable_test_jobs=True)


def test_database_driver_is_explicit():
    with pytest.raises(ValidationError, match="postgresql"):
        Settings(database_url="sqlite://")


def test_liveness_does_not_require_dependencies(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}


def test_readiness_reflects_dependency_failure(client, monkeypatch):
    monkeypatch.setattr("app.health.dependency_checks",
                        lambda: {"postgresql": "up", "redis": "down", "minio": "up"})
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "down"


def test_test_jobs_disabled_by_default(client):
    response = client.post("/api/v1/internal/test-jobs", json={"value": "hello"},
                           headers={"Idempotency-Key": "key"})
    assert response.status_code == 404
    assert set(response.json()) == {"code", "message", "requestId"}


def test_invalid_input_returns_sanitized_error(client, monkeypatch):
    monkeypatch.setenv("ENABLE_TEST_JOBS", "true")
    get_settings.cache_clear()
    response = client.post("/api/v1/internal/test-jobs", json={"value": "secret", "delaySeconds": 31},
                           headers={"Idempotency-Key": "key"})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "secret" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["requestId"]
    responses = client.get('/openapi.json').json()['paths'][
        '/api/v1/internal/test-jobs']['post']['responses']
    for code in ['404', '409', '422', '500']:
        assert responses[code]['content']['application/json']['schema'][
            '$ref'].endswith('/ApiErrorBody')


def test_worker_guard(monkeypatch):
    from app.worker.tasks import run_job
    monkeypatch.setenv("ENABLE_TEST_JOBS", "false")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="disabled"):
        run_job("not-reached")
