"""Real overseas runner authentication, public errors and resumed-session fencing."""
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.execution import managed_credentials
from app.overseas.execution import runner, protocols
from app.overseas.execution.events import FAILURES
from app.overseas.execution.models import Job
from app.overseas.studio.models import Conversation, Turn
from test_managed_credentials import auth, write
from test_overseas_runner import execution, fake_execute
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT


@pytest.mark.parametrize('code', [
    'credentials_invalid', 'credentials_busy', 'credentials_refresh_failed',
    'credentials_account_changed',
])
def test_sync_failure_precedes_studio_dispatch(studio, monkeypatch, tmp_path, code):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        workspace = commands[-1][0]
        assert kwargs == dict(broker_socket=None, control=workspace.control.parent,
                             require_existing=False)
        assert not (workspace.home / '.codex/auth.json').exists()
        raise managed_credentials.CredentialsError(code)
    monkeypatch.setattr(runner, 'sync_credentials', fail)
    monkeypatch.setattr(runner, 'execute', lambda *a: pytest.fail('must not dispatch'))
    turn = send(client, task).json()['turns'][0]
    runner.run(factory, turn['jobId'])
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        assert job.status == 'failed' and job.error == FAILURES[code]
        assert job.process_exited and job.process_id is None and job.result is None
        assert session.get(Turn, UUID(turn['id'])).dispatched is False
        assert session.scalar(select(Conversation)).session_id is None
    public = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()['turns'][0]
    assert public['error'] == FAILURES[code] and public['pictures'] == []


@pytest.mark.parametrize('reason,code', [
    (None, 'authentication_failed'), ('timeout', 'timeout'), ('output_limit', 'output_limit'),
])
@pytest.mark.parametrize('exit_code', [0, 1])
def test_failed_stream_never_collects_and_platform_stop_outranks_auth(
        studio, monkeypatch, tmp_path, reason, code, exit_code):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path, image_count=1)
    original = runner.execute
    def failed(*args):
        original(*args)
        with (args[2] / 'events.jsonl').open('a') as output:
            output.write('\n' + json.dumps({'type': 'turn.failed', 'error': {
                'message': '401 Unauthorized secret-refresh /private/auth.json'}}))
        return dict(exit_code=exit_code, reason=reason)
    monkeypatch.setattr(runner, 'execute', failed)
    turn = send(client, task).json()['turns'][0]
    runner.run(factory, turn['jobId'])
    runner.run(factory, turn['jobId'])
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()['turns'][0]
    assert view['status'] == 'failed' and view['error'] == FAILURES[code]
    assert view['pictures'] == [] and 'secret-refresh' not in str(view)
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).execution_count == 1


def test_real_sync_new_then_legacy_studio_resume_preserves_session(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    settings = get_settings()
    write(Path(settings.codex_auth_file), auth(ttl=86400))
    monkeypatch.setattr(runner, 'sync_credentials', managed_credentials.sync_credentials)
    monkeypatch.setattr(managed_credentials, '_request_refresh', lambda _: pytest.fail('network'))
    original = runner.execute
    def checked(*args):
        workspace = commands[-1][0]
        private = json.loads((workspace.home / '.codex/auth.json').read_text())
        assert private['tokens']['refresh_token'] == ''
        assert private['tokens']['access_token'] == auth_data['tokens']['access_token']
        return original(*args)
    auth_data = json.loads(Path(settings.codex_auth_file).read_text())
    monkeypatch.setattr(runner, 'execute', checked)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    workspace = commands[-1][0]
    (workspace.work / 'history.txt').write_text('preserved original research')
    # Emulate a deployed pre-broker session: old private auth exists, binding absent.
    (workspace.control.parent / 'auth-identity.json').unlink()
    write(workspace.home / '.codex/auth.json', auth(ttl=-1))
    second = send(client, task, key='legacy-resume').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    assert 'resume' in commands[-1][1] and 'session-123' in commands[-1][1]
    assert (workspace.work / 'history.txt').read_text() == 'preserved original research'
    with factory() as session:
        assert session.get(Job, UUID(second['jobId'])).status == 'succeeded'
        assert session.scalar(select(Conversation)).session_id == 'session-123'


@pytest.mark.parametrize('change,code', [
    ('missing', 'credentials_invalid'), ('account', 'credentials_account_changed'),
])
def test_legacy_resume_missing_or_changed_identity_never_dispatches(
        studio, monkeypatch, tmp_path, change, code):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    settings = get_settings()
    write(Path(settings.codex_auth_file), auth(ttl=86400))
    monkeypatch.setattr(runner, 'sync_credentials', managed_credentials.sync_credentials)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    workspace = commands[-1][0]
    (workspace.control.parent / 'auth-identity.json').unlink()
    if change == 'missing':
        (workspace.home / '.codex/auth.json').unlink()
    else:
        write(Path(settings.codex_auth_file), auth(ttl=86400, account='different-workspace'))
    monkeypatch.setattr(runner, 'execute', lambda *a: pytest.fail('must not dispatch'))
    second = send(client, task, key='identity-rejected').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    with factory() as session:
        job = session.get(Job, UUID(second['jobId']))
        assert job.status == 'failed' and job.error == FAILURES[code]
        assert session.get(Turn, UUID(second['id'])).dispatched is False
        assert session.scalar(select(Conversation)).session_id == 'session-123'
    assert (workspace.home / '.codex/sessions/rollout-session-123.jsonl').read_text() == '{}'


def test_runner_passes_broker_configuration_without_reading_master(execution, monkeypatch):
    from app.execution import credential_broker_client
    factory, new, settings = execution
    settings.codex_auth_broker_socket = '/private/credential-broker.sock'
    Path(settings.codex_auth_file).unlink()
    received = []
    def request(socket, timeout):
        received.append((socket, timeout))
        value = auth(ttl=86400)
        value['tokens']['refresh_token'] = ''
        return value
    monkeypatch.setattr(credential_broker_client, 'request_credentials', request)
    monkeypatch.setattr(runner, 'execute', fake_execute())
    identity = new({'runtime': {'timeoutSeconds': 120}})
    runner.run(factory, identity)
    assert received == [(settings.codex_auth_broker_socket, 120)]
    with factory() as session:
        assert session.get(Job, identity).status == 'succeeded'


@pytest.mark.parametrize('kind', ['analysis', 'reanalysis', 'generation', 'revision'])
def test_every_legacy_protocol_receives_access_only_credentials(execution, monkeypatch, kind):
    factory, new, settings = execution
    protocols._handlers[kind] = protocols._handlers['analysis']
    identity = new()
    with factory.begin() as session:
        session.get(Job, identity).kind = kind
    original = fake_execute()
    def checked(*args):
        path = Path(settings.codex_execution_root) / str(identity) / 'home/.codex/auth.json'
        private = json.loads(path.read_text())
        assert private['tokens']['refresh_token'] == ''
        assert private['tokens']['account_id'] == 'workspace-one'
        return original(*args)
    monkeypatch.setattr(runner, 'execute', checked)
    runner.run(factory, identity)
    with factory() as session:
        assert session.get(Job, identity).status == 'succeeded'
