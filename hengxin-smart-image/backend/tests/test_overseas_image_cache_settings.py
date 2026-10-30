"""Default changes affect new overseas freezes, never stored job runtime values."""
from uuid import UUID
from app.core.config import Settings, get_settings
from app.overseas.config import OverseasSettings
from app.overseas.execution.models import Job
from app.overseas.management.models import Settings as ManagedSettings
from test_overseas_tasks import overseas
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish
from test_overseas_configuration import FAKE_OVERSEAS


def test_overseas_defaults_domestic_and_explicit_configuration(monkeypatch):
    for key in ('CODEX_TIMEOUT_SECONDS', 'QUEUE_VISIBILITY_SECONDS',
                'OVERSEAS_CODEX_TIMEOUT_SECONDS', 'OVERSEAS_QUEUE_VISIBILITY_SECONDS'):
        monkeypatch.delenv(key, raising=False)
    settings = OverseasSettings(**{key.lower(): value for key, value in FAKE_OVERSEAS.items()})
    assert (settings.codex_timeout_seconds, settings.queue_visibility_seconds) == (7200, 7800)
    domestic = Settings(_env_file=None)
    assert (domestic.codex_timeout_seconds, domestic.queue_visibility_seconds) == (3600, 4200)
    monkeypatch.setenv('OVERSEAS_CODEX_TIMEOUT_SECONDS', '1200')
    monkeypatch.setenv('OVERSEAS_QUEUE_VISIBILITY_SECONDS', '1800')
    explicit = OverseasSettings(**{key.lower(): value for key, value in FAKE_OVERSEAS.items()})
    assert (explicit.codex_timeout_seconds, explicit.queue_visibility_seconds) == (1200, 1800)


def test_new_turn_uses_new_default_old_frozen_turn_and_explicit_config_survive(studio):
    client, factory, _, task, _, _ = studio
    settings = get_settings()
    settings.codex_timeout_seconds = 3600
    old = send(client, task, key='old').json()['turns'][0]
    settings.codex_timeout_seconds = 7200
    assert send(client, task, key='old').status_code == 200
    with factory() as session:
        assert session.get(Job, UUID(old['jobId'])).payload['runtime']['timeoutSeconds'] == 3600
    finish(factory, old)
    fresh = send(client, task, key='fresh').json()['turns'][-1]
    with factory() as session:
        assert session.get(Job, UUID(fresh['jobId'])).payload['runtime']['timeoutSeconds'] == 7200
    finish(factory, fresh)
    with factory.begin() as session:
        session.add(ManagedSettings(id=1, version=1, values={'timeoutSeconds': 180}))
    explicit = send(client, task, key='explicit').json()['turns'][-1]
    with factory() as session:
        assert session.get(Job, UUID(explicit['jobId'])).payload['runtime']['timeoutSeconds'] == 180
        assert session.get(Job, UUID(old['jobId'])).payload['runtime']['timeoutSeconds'] == 3600
