import builtins
import os
import runpy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_business_context, get_settings
from app.overseas.config import OverseasSettings


FAKE_OVERSEAS = {
    'DATABASE_URL': 'postgresql+psycopg://overseas:fake-secret@localhost:5433/overseas_test',
    'REDIS_URL': 'redis://localhost:6380/0',
    'MINIO_ENDPOINT': 'localhost:9100',
    'MINIO_ACCESS_KEY': 'fake-overseas-access',
    'MINIO_SECRET_KEY': 'fake-overseas-secret',
    'MINIO_BUCKET': 'overseas-test',
    'CODEX_EXECUTION_ROOT': '/tmp/hx-overseas-test/execution',
    'SKILL_INSTALL_ROOT': '/tmp/hx-overseas-test/skills',
    'LOCAL_SKILL_ROOT': '/tmp/hx-overseas-test/local-skills',
}
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith('OVERSEAS_') or name == 'HX_BUSINESS_CONTEXT':
            monkeypatch.delenv(name)
    yield
    get_settings.cache_clear()


def configure_overseas(monkeypatch):
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', 'overseas')
    for name, value in FAKE_OVERSEAS.items():
        monkeypatch.setenv('OVERSEAS_' + name, value)


def load_entry(name):
    # Execute isolated module namespaces, never replace app.main in sys.modules.
    return runpy.run_path(str(BACKEND / 'app' / name))


def test_domestic_default_and_existing_settings_are_unchanged(monkeypatch):
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/7')
    monkeypatch.setenv('GENERATION_CONCURRENCY', '9')
    settings = get_settings()
    assert get_business_context() == 'domestic'
    assert type(settings) is Settings
    assert settings.database_url == os.environ['DATABASE_URL']
    assert settings.redis_url == 'redis://localhost:6379/7'
    assert settings.generation_concurrency == 9


def test_domestic_dotenv_loading_is_preserved(monkeypatch, tmp_path):
    monkeypatch.delenv('WORKER_NODE_NAME', raising=False)
    (tmp_path / '.env').write_text('WORKER_NODE_NAME=domestic-dotenv\n', encoding='utf-8')
    assert get_settings().worker_node_name == 'domestic-dotenv'


@pytest.mark.parametrize('context', ['', 'oversea', 'OVERSEAS', 'secret-context'])
def test_invalid_context_is_rejected_without_echo(monkeypatch, context):
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', context)
    with pytest.raises(ValueError, match='HX_BUSINESS_CONTEXT') as caught:
        get_settings()
    assert 'secret-context' not in str(caught.value)


@pytest.mark.parametrize('missing', list(FAKE_OVERSEAS))
def test_domestic_env_and_dotenv_cannot_fill_missing_overseas(monkeypatch, tmp_path, missing):
    configure_overseas(monkeypatch)
    monkeypatch.delenv('OVERSEAS_' + missing)
    monkeypatch.setenv(missing, FAKE_OVERSEAS[missing])
    # Even correctly prefixed values in a domestic .env must be ignored.
    (tmp_path / '.env').write_text(
        f'{missing}={FAKE_OVERSEAS[missing]}\nOVERSEAS_{missing}={FAKE_OVERSEAS[missing]}\n',
        encoding='utf-8',
    )
    with pytest.raises(RuntimeError, match=missing.lower()) as caught:
        get_settings()
    assert 'fake-secret' not in str(caught.value)
    assert 'fake-overseas-secret' not in str(caught.value)


def test_explicit_overseas_settings_and_safe_defaults(monkeypatch):
    configure_overseas(monkeypatch)
    for flag in ('ENABLE_CODEX_EXECUTOR', 'ENABLE_FIXTURE_EXECUTOR', 'ENABLE_TEST_JOBS',
                 'ENABLE_DEV_IDENTITY', 'CLI_RETENTION_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    monkeypatch.setenv('CODEX_AUTH_FILE', '/domestic/auth.json')
    settings = get_settings()
    assert isinstance(settings, OverseasSettings)
    for name, value in FAKE_OVERSEAS.items():
        assert getattr(settings, name.lower()) == value
    assert settings.generation_concurrency == 5
    assert not settings.enable_codex_executor
    assert not settings.enable_fixture_executor
    assert not settings.enable_test_jobs
    assert not settings.enable_dev_identity
    assert not settings.cli_retention_enabled
    assert settings.codex_auth_file == ''
    assert settings.db_application_name == 'hx-overseas'
    assert 'fake-overseas-secret' not in repr(settings)
    assert 'fake-secret' not in repr(settings)


@pytest.mark.parametrize('value', ['0', '6', 'secret-invalid'])
def test_overseas_concurrency_rejects_invalid_values(monkeypatch, value):
    configure_overseas(monkeypatch)
    monkeypatch.setenv('OVERSEAS_GENERATION_CONCURRENCY', value)
    with pytest.raises(RuntimeError, match='generation_concurrency') as caught:
        get_settings()
    assert 'secret-invalid' not in str(caught.value)


@pytest.mark.parametrize('name', list(FAKE_OVERSEAS))
def test_overseas_required_resources_reject_blank(monkeypatch, name):
    configure_overseas(monkeypatch)
    monkeypatch.setenv('OVERSEAS_' + name, '   ')
    with pytest.raises(RuntimeError, match=name.lower()):
        get_settings()


def test_entrypoints_reject_wrong_context(monkeypatch):
    with pytest.raises(RuntimeError, match='Overseas entry requires'):
        load_entry('overseas/main.py')
    configure_overseas(monkeypatch)
    with pytest.raises(RuntimeError, match='Domestic entry requires'):
        load_entry('main.py')


def test_overseas_entry_fails_with_missing_config(monkeypatch):
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', 'overseas')
    with pytest.raises(RuntimeError, match='Invalid OVERSEAS_ configuration'):
        load_entry('overseas/main.py')


def test_overseas_liveness_routes_and_sanitized_errors(monkeypatch):
    configure_overseas(monkeypatch)
    original_import = builtins.__import__

    def forbid_domestic_imports(name, *args, **kwargs):
        shared_files = {'app.modules.skills.package_validator', 'app.modules.files.delivery', 'app.modules.files.streaming',
                        'app.modules.files.multipart', 'app.modules.files.validation'}
        assert name in shared_files or not name.startswith(('app.main', 'app.health', 'app.jobs', 'app.modules'))
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', forbid_domestic_imports)
    app = load_entry('overseas/main.py')['app']
    business_paths = {path for path in app.openapi()['paths'] if path.startswith('/api/')}
    assert business_paths == {
        '/api/overseas/v1/management/usage', '/api/overseas/v1/management/jobs',
        '/api/overseas/v1/management/skills', '/api/overseas/v1/management/skills/{identity}',
        '/api/overseas/v1/management/skills/{identity}/versions', '/api/overseas/v1/management/settings',
        '/api/overseas/v1/health/live', '/api/overseas/v1/health/ready',
        '/api/overseas/v1/auth/identity/session', '/api/overseas/v1/auth/me',
        '/api/overseas/v1/auth/logout',
        '/api/overseas/v1/members', '/api/overseas/v1/members/{member_id}',
        '/api/overseas/v1/members/{member_id}/audit',
        '/api/overseas/v1/tasks', '/api/overseas/v1/tasks/{task_id}',
        '/api/overseas/v1/tasks/{task_id}/assignment', '/api/overseas/v1/task-designers',
        '/api/overseas/v1/materials', '/api/overseas/v1/materials/{material_id}',
        '/api/overseas/v1/materials/{material_id}/content', '/api/overseas/v1/materials/{material_id}/retry',
        '/api/overseas/v1/tasks/{task_id}/materials',
        '/api/overseas/v1/tasks/{task_id}/jobs',
        '/api/overseas/v1/tasks/{task_id}/execution-events',
        '/api/overseas/v1/jobs/{job_id}/cancel',
        '/api/overseas/v1/tasks/{task_id}/pictures',
        '/api/overseas/v1/pictures/{picture_id}/versions/{version}/content',
        '/api/overseas/v1/pictures/{picture_id}/approve',
        '/api/overseas/v1/pictures/{picture_id}/revisions',
        '/api/overseas/v1/tasks/{task_id}/generation/retry',
        '/api/overseas/v1/tasks/{task_id}/archive',
        '/api/overseas/v1/archives',
        '/api/overseas/v1/archives/{archive_id}/download',
        '/api/overseas/v1/tasks/{task_id}/plans',
        '/api/overseas/v1/tasks/{task_id}/analysis',
        '/api/overseas/v1/tasks/{task_id}/plans/{plan_id}/confirm',
    }

    @app.get('/test-internal-error', include_in_schema=False)
    def fail():
        raise RuntimeError('fake-overseas-secret')

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/overseas/v1/health/live')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        assert 'X-Request-ID' in response.headers
        assert 'Server-Timing' in response.headers
        for path in ('/api/v1/health/live', '/api/v1/tasks'):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()['code'] == 'NOT_FOUND'
        response = client.get('/test-internal-error')
        assert response.status_code == 500
        assert response.json()['code'] == 'INTERNAL_ERROR'
        assert 'fake-overseas-secret' not in response.text
