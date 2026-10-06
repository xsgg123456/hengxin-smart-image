"""Preflight failures are distinct from dispatched CLI invocations."""
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.modules.api_image_edits import conversation_runner as runner
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.capacity.models import CapacityReservation
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_image_versions import setup_result
from test_api_cli_conversation import cli_enabled, seed_gate, submit, run, fake_executor
from test_capacity_admission import policy


@pytest.mark.parametrize('failure', ['version', 'inputs', 'sandbox'])
def test_preflight_failure_can_start_first_session_after_environment_repair(files_env, monkeypatch, failure):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    policy(factory)
    calls = fake_executor(monkeypatch)
    first = submit(client, path)
    with monkeypatch.context() as patch:
        if failure == 'version':
            patch.setattr(runner.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1, stdout=''))
        else:
            def unavailable(*args):
                raise OSError('isolated preflight failure')
            patch.setattr(runner, 'prepare_inputs' if failure == 'inputs' else 'sandbox_command', unavailable)
        run(factory, store, first)
    assert calls == []
    with factory() as session:
        turn = session.get(ConversationTurn, UUID(first['id']))
        assert turn.status == 'failed'
        assert not turn.snapshot.get('executionDispatched')
        assert session.get(CapacityReservation, turn.id).state == 'published'
    second = submit(client, path)
    run(factory, store, second)
    assert len(calls) == 1 and 'resume' not in calls[0][0]
    assert client.get(path + '/conversation').json()['turns'][-1]['status'] == 'waiting_user'


def test_dispatched_without_session_id_never_silently_creates_replacement(files_env, monkeypatch):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    calls = []
    def execute(*args):
        calls.append(args)
        return {'exit_code': 1, 'reason': None}
    monkeypatch.setattr(runner, 'execute', execute)
    first = submit(client, path)
    run(factory, store, first)
    with factory() as session:
        turn = session.get(ConversationTurn, UUID(first['id']))
        assert turn.status == 'failed' and turn.snapshot['executionDispatched']
    second = submit(client, path)
    run(factory, store, second)
    assert len(calls) == 1
    result = client.get(path + '/conversation').json()['turns'][-1]
    assert result['status'] == 'failed' and '原会话编号缺失' in result['error']


def test_cancel_before_dispatch_publishes_capacity_without_running_cli(files_env, monkeypatch):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    policy(factory)
    first = submit(client, path)
    calls = fake_executor(monkeypatch)
    class StopBeforeDispatch:
        def __init__(self, *args):
            pass

        def __call__(self):
            with factory.begin() as session:
                session.get(ConversationTurn, UUID(first['id'])).cancel_requested = True
            return True
    monkeypatch.setattr(runner, 'Monitor', StopBeforeDispatch)
    run(factory, store, first)
    assert not calls
    with factory() as session:
        turn = session.get(ConversationTurn, UUID(first['id']))
        assert turn.status == 'cancelled'
        assert session.get(CapacityReservation, turn.id).state == 'published'
