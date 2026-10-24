"""Late collectors and incomplete CLI evidence cannot resurrect or publish work."""
from datetime import timedelta
from uuid import UUID

import pytest

from app.overseas.execution import claims, reconcile, runner
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.studio import delivery_context, delivery_job
from app.overseas.studio import conversation_cleanup
from app.overseas.studio.models import ConversationDeletion
from app.overseas.tasks import cleanup
from app.overseas.tasks.models import TaskDeletion
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas
from studio_sessions_helpers import mutate
from test_overseas_plans import post
from test_overseas_task_deletion import request


def pending(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)

    def unavailable(*_args):
        raise OSError('storage unavailable')

    monkeypatch.setattr(case.store, 'put', unavailable)
    case.run()
    assert case.current()['status'] == 'collecting' and case.count() == 0
    return case


def late_collect(case, job):
    summary = delivery_context.success(case.workspace)
    return delivery_job.deliver(case.factory, job, job.claim_token,
                                case.workspace, summary, case.store)


def test_expired_lease_and_old_token_cannot_publish_after_takeover(studio, monkeypatch, tmp_path):
    case = pending(studio, monkeypatch, tmp_path)
    old = case.job()
    case.due()
    before = dict(case.store.data)
    with pytest.raises(delivery_job.OwnershipLost):
        late_collect(case, old)
    assert case.store.data == before and case.count() == 0
    original, checked = delivery_job.deliver, []

    def new_owner(factory, job, token, workspace, summary, store):
        assert claims.valid(case.job(), token) and token != old.claim_token
        with pytest.raises(delivery_job.OwnershipLost):
            original(factory, old, old.claim_token, workspace, summary, store)
        checked.append(True)
        return original(factory, job, token, workspace, summary, store)

    monkeypatch.setattr(case.store, 'put', case.put)
    monkeypatch.setattr(delivery_job, 'deliver', new_owner)
    case.recover()
    assert checked == [True]
    case.complete(expected=1)


def test_cancel_during_pending_collection_never_publishes(studio, monkeypatch, tmp_path):
    case = pending(studio, monkeypatch, tmp_path)
    old = case.job()
    response = post(case.client, case.task, '/studio/turns/' + case.turn['id'] + '/cancel',
                    {'version': case.current()['jobVersion']})
    assert response.status_code == 200, response.text
    monkeypatch.setattr(case.store, 'put', case.put)
    case.recover()
    assert case.current()['status'] == 'cancelled' and case.count() == 0
    before = dict(case.store.data)
    with pytest.raises(delivery_job.OwnershipLost):
        late_collect(case, old)
    reconcile.reconcile_once(case.factory)
    case.run()
    assert case.store.data == before and case.count() == 0 and len(case.commands) == 1


def test_upload_finishing_after_lease_expiry_cannot_publish(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)

    def delayed_upload(record, data):
        case.put(record, data)
        after_expiry = utcnow() + timedelta(seconds=get_settings().job_lease_seconds + 1)
        patch.setattr(claims, 'utcnow', lambda: after_expiry)

    with monkeypatch.context() as patch:
        patch.setattr(case.store, 'put', delayed_upload)
        case.run()
    assert case.current()['status'] != 'succeeded'
    assert case.count() == 0 and case.current()['pictures'] == []
    before = dict(case.store.data)
    case.recover()
    case.complete(expected=1)
    assert case.store.data == before and len(case.puts) == 1


@pytest.mark.parametrize('scope', ['task', 'conversation'])
def test_deleted_work_cannot_be_revived_by_a_late_collector(studio, monkeypatch, tmp_path, scope):
    case = pending(studio, monkeypatch, tmp_path)
    old = case.job()
    summary = delivery_context.success(case.workspace)
    if scope == 'task':
        response = request(case.client, case.task)
        assert response.status_code == 200, response.text
    else:
        # Session deletion requires stopping its active invocation first.
        response = post(case.client, case.task, '/studio/turns/' + case.turn['id'] + '/cancel',
                        {'version': case.current()['jobVersion']})
        assert response.status_code == 200, response.text
    case.recover()
    if scope == 'conversation':
        channel = next(row for row in case.view()['conversations']
                       if row['id'] == case.turn['conversationId'])
        response = mutate(case.client, case.task, channel['id'], 'DELETE', {'version': channel['version']})
        assert response.status_code == 200, response.text
    monkeypatch.setattr(case.store, 'put', case.put)
    with pytest.raises(delivery_job.OwnershipLost):
        delivery_job.deliver(case.factory, old, old.claim_token, case.workspace, summary, case.store)
    operation = cleanup.cleanup_once if scope == 'task' else conversation_cleanup.cleanup_once
    assert operation(case.factory, case.store) == 1
    with case.factory() as session:
        receipt = session.get(TaskDeletion, UUID(case.task['id'])) if scope == 'task' else (
            session.get(ConversationDeletion, UUID(case.turn['conversationId'])))
        assert receipt.status == 'deleted'
    before = dict(case.store.data)
    reconcile.reconcile_once(case.factory)
    case.run()
    with pytest.raises(delivery_job.OwnershipLost):
        delivery_job.deliver(case.factory, old, old.claim_token, case.workspace, summary, case.store)
    assert case.store.data == before and case.count() == 0 and len(case.commands) == 1


@pytest.mark.parametrize('outcome', ['nonzero', 'missing_receipt', 'incomplete_events'])
def test_image_files_are_not_a_success_receipt(studio, monkeypatch, tmp_path, outcome):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    original = runner.execute

    def process(*args):
        receipt = original(*args)
        if outcome == 'missing_receipt':
            raise RuntimeError('worker disconnected before process receipt')
        if outcome == 'incomplete_events':
            events = args[2] / 'events.jsonl'
            events.write_text('\n'.join(events.read_text().splitlines()[:-1]))
            return receipt
        return dict(exit_code=7)

    monkeypatch.setattr(runner, 'execute', process)
    case.run()
    assert (case.workspace.work / 'output0.png').exists()
    expected = 'uncertain' if outcome == 'missing_receipt' else 'failed'
    assert case.current()['status'] == expected and case.count() == 0
    for _ in range(2):
        reconcile.reconcile_once(case.factory)
        case.run()
    assert case.current()['status'] == expected and case.count() == 0
    assert not case.puts and len(case.commands) == 1
    assert case.job().execution_count == 1
