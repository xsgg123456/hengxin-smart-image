from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.overseas import health
from app.storage.minio_store import MinioStore


@pytest.fixture
def dependencies(monkeypatch):
    settings = SimpleNamespace(redis_url='redis://fake-secret@redis:6379/0',
                               minio_bucket='overseas-test')
    monkeypatch.setattr(health, 'get_settings', lambda: settings)
    connection = MagicMock()
    connection.execute.return_value.scalars.return_value.all.return_value = [health.SCHEMA_VERSION]
    engine = MagicMock()
    engine.connect.return_value = nullcontext(connection)
    monkeypatch.setattr(health, 'get_engine', lambda: engine)
    redis = MagicMock()
    monkeypatch.setattr(health.Redis, 'from_url', lambda *a, **kw: nullcontext(redis))
    store = MagicMock()
    monkeypatch.setattr(health, 'MinioStore', lambda **kw: store)
    app = FastAPI()
    app.include_router(health.router)
    return SimpleNamespace(connection=connection, engine=engine, redis=redis,
                           store=store, client=TestClient(app))


def test_ready_checks_exact_schema_and_private_bucket(dependencies):
    response = dependencies.client.get('/api/overseas/v1/health/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ready', 'checks': {
        'postgresql': 'up', 'redis': 'up', 'minio': 'up',
    }}
    dependencies.store.ensure_private.assert_called_once_with('overseas-test', create_missing=False)
    dependencies.redis.ping.assert_called_once()
    queries = [str(call.args[0]) for call in dependencies.connection.execute.call_args_list]
    assert queries == ["SET LOCAL statement_timeout = '2000ms'",
                       'SELECT version_num FROM overseas_alembic_version']


@pytest.mark.parametrize('versions', [[], ['old'], ['overseas_0001', 'unexpected']])
def test_ready_rejects_missing_old_or_branched_schema(dependencies, versions):
    dependencies.connection.execute.return_value.scalars.return_value.all.return_value = versions
    response = dependencies.client.get('/api/overseas/v1/health/ready')
    assert response.status_code == 503
    assert response.json()['checks']['postgresql'] == 'down'


@pytest.mark.parametrize('failed', ['postgresql', 'redis', 'minio'])
def test_dependency_failure_is_sanitized_and_live_stays_up(dependencies, failed):
    target = {'postgresql': dependencies.engine.connect,
              'redis': dependencies.redis.ping,
              'minio': dependencies.store.ensure_private}[failed]
    target.side_effect = RuntimeError('fake-secret-sensitive-internal-address')
    response = dependencies.client.get('/api/overseas/v1/health/ready')
    assert response.status_code == 503
    assert response.json()['checks'][failed] == 'down'
    assert 'fake-secret' not in response.text
    assert all(value == 'up' for key, value in response.json()['checks'].items() if key != failed)
    assert dependencies.client.get('/api/overseas/v1/health/live').status_code == 200


def test_live_never_contacts_resources(dependencies):
    assert dependencies.client.get('/api/overseas/v1/health/live').json() == {'status': 'ok'}
    dependencies.engine.connect.assert_not_called()
    dependencies.redis.ping.assert_not_called()
    dependencies.store.ensure_private.assert_not_called()


def test_readonly_private_check_never_creates_a_missing_bucket():
    store = object.__new__(MinioStore)
    store.client = MagicMock()
    store.client.bucket_exists.return_value = False
    with pytest.raises(RuntimeError, match='not been initialized'):
        store.ensure_private('overseas-test', create_missing=False)
    store.client.make_bucket.assert_not_called()


def test_readonly_private_check_rejects_public_policy():
    store = object.__new__(MinioStore)
    store.client = MagicMock()
    store.client.bucket_exists.return_value = True
    store.client.get_bucket_policy.return_value = '{"Statement":[]}'
    with pytest.raises(RuntimeError, match='no anonymous'):
        store.ensure_private('overseas-test', create_missing=False)
    store.client.make_bucket.assert_not_called()
