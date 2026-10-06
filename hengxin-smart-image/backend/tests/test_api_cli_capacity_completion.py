"""Capacity is accounted after known completion, never while invocation is ambiguous."""
from uuid import UUID

import pytest

from app.capacity.models import CapacityReservation
from app.modules.api_image_edits import conversation_runner as runner
from app.modules.api_image_edits.conversation_models import ConversationTurn
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_image_versions import setup_result
from test_api_cli_conversation import cli_enabled, seed_gate, submit, run, fake_executor
from test_capacity_admission import policy


@pytest.mark.parametrize('failure', ['invalid_delivery', 'store_put', 'cancel_after_execute', 'execute_unknown', 'cancel_unknown'])
def test_capacity_after_model_exit_vs_unknown_execution(files_env, monkeypatch, failure):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    policy(factory)
    first = submit(client, path)
    calls = fake_executor(monkeypatch, text='![结果](/work/missing.png)', image=failure != 'invalid_delivery')
    original_execute = runner.execute
    def execute(*args):
        if failure == 'cancel_unknown':
            with factory.begin() as session:
                session.get(ConversationTurn, UUID(first['id'])).cancel_requested = True
        if failure in ('execute_unknown', 'cancel_unknown'):
            raise OSError('Cannot establish process completion')
        result = original_execute(*args)
        if failure == 'cancel_after_execute':
            with factory.begin() as session:
                session.get(ConversationTurn, UUID(first['id'])).cancel_requested = True
        return result
    monkeypatch.setattr(runner, 'execute', execute)
    store.fail_put = failure == 'store_put'
    run(factory, store, first)
    with factory() as session:
        turn = session.get(ConversationTurn, UUID(first['id']))
        reservation = session.get(CapacityReservation, turn.id)
        assert turn.candidate_id is None
        if failure in ('execute_unknown', 'cancel_unknown'):
            assert turn.status == 'uncertain' and reservation.state == 'held'
            if failure == 'cancel_unknown':
                from app.models import Outbox
                assert session.get(Outbox, turn.job_id).completed_at is None
        else:
            assert len(calls) == 1
            assert turn.status == ('cancelled' if failure == 'cancel_after_execute' else 'failed')
            assert reservation.state == 'published'
