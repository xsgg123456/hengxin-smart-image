"""Exercise actual cleanup transactions and HTTP authorization against isolated data."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.retention import api, paths
from app.retention.events import finish
from app.retention.observability_models import RetentionRecord, RetentionTotals, RetentionRun
from app.retention.objects import retry_objects
from app.retention.service import begin_scan, end_scan, heartbeat
from app.retention.state import entry, aware
from app.retention.worker import register_existing
from app.resource_models import UserRecord
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.api_image_edits.models import ApiTask
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_cli_conversation import cli_enabled, seed_gate
from test_api_retention import sample

URL = '/api/v1/management/retention'


def test_cache_retry_stays_visible_after_history_deadline(files_env, monkeypatch, cli_enabled):
    from app.modules.management import retention_router
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    admin(files_env)
    monkeypatch.setattr(paths, 'clean', lambda *a, **kw: (_ for _ in ()).throw(OSError('disk')))
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier,
                       now + timedelta(hours=24)) == 'retry'
    monkeypatch.setattr(retention_router, 'utcnow', lambda: now + timedelta(hours=73))
    response = client.get(URL + '/records?tab=pending&kind=cache&result=retry')
    assert response.status_code == 200 and response.json()['total'] == 1
    row = response.json()['items'][0]
    assert row['kind'] == 'cache' and row['result'] == 'retry'
    assert datetime.fromisoformat(row['dueAt'].replace('Z', '+00:00')) == (now + timedelta(hours=24)).replace(microsecond=0)
    detail = client.get(URL + '/records/' + row['id'] + '?tab=pending').json()
    assert detail['kind'] == 'cache' and detail['result'] == 'retry'
    counts = client.get(URL + '/summary').json()['counts']
    assert counts['retry'] == 1 and counts['overdue'] == 1


def admin(env, role='super_admin'):
    with env[1].begin() as session:
        session.get(UserRecord, env[3][0]).role = role


def test_permissions_and_validation(files_env):
    client = files_env[0]
    for role in ('operator', 'designer'):
        admin(files_env, role)
        assert client.get(URL + '/summary').status_code == 403
        assert client.get(URL + '/records').status_code == 403
        assert client.get(URL + '/records/' + str(uuid4())).status_code == 403
    for role in ('super_admin', 'design_manager'):
        admin(files_env, role)
        response = client.get(URL + '/summary')
        assert response.status_code == 200, response.text
        assert response.json()['service']['heartbeatAt'] is None
        assert response.json()['statisticsSince'] is None
        assert client.get(URL + '/records').json()['total'] == 0
    for query in ('page=0', 'pageSize=101', 'kind=invalid', 'result=invalid', 'tab=x',
                  'dateFrom=2026-10-22&dateTo=2026-10-21'):
        assert client.get(URL + '/records?' + query).status_code == 422
    assert client.get(URL + '/records/' + str(uuid4())).status_code == 404


def test_receipts_atomic_and_object_completion_not_premature(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    admin(files_env)
    root, expiry = Path(cli_enabled.codex_execution_root), now + timedelta(hours=72)
    from app.modules.management import retention_router
    monkeypatch.setattr(retention_router, 'utcnow', lambda: expiry)
    # At 71h this may clear cache, but must never erase history.
    assert api.process(factory, store, root, identifier, expiry - timedelta(hours=1)) == 'cache_cleared'
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ConversationTurn)) == 1
    assert api.process(factory, store, root, identifier, expiry) == 'expired'
    with factory() as session:
        totals = session.get(RetentionTotals, 'api_cli')
        assert totals.cache_total == 1 and totals.history_total == 0
        record = session.scalar(select(RetentionRecord).where(RetentionRecord.kind == 'history'))
        assert record.result == 'objects_pending' and record.turns_removed == 1
        record_id = record.id
    counts = client.get(URL + '/summary').json()['counts']
    assert counts['overdue'] == 1 and counts['objectsPending'] == 1
    store.fail_remove = True
    retry_objects(factory, store, now=expiry)
    failed = client.get(URL + '/records/' + str(record_id)).json()
    assert failed['result'] == 'retry' and failed['objectsPending'] == 1
    assert failed['detailTab'] == 'history'
    counts = client.get(URL + '/summary').json()['counts']
    assert counts['overdue'] == 1 and counts['retry'] == 1
    assert client.get(URL + '/records?tab=pending').json()['total'] == 1
    store.fail_remove = False
    assert retry_objects(factory, store, now=expiry + timedelta(hours=1)) == 1
    assert retry_objects(factory, store, now=expiry + timedelta(hours=2)) == 0
    with factory.begin() as session:
        record = session.get(RetentionRecord, record_id)
        finish(session, record, expiry + timedelta(hours=2))
        assert record.result == 'complete' and record.objects_removed == 1 and record.objects_pending == 0
        assert session.get(RetentionTotals, 'api_cli').history_total == 1
        task = session.get(ApiTask, record.task_id)
        task.deleted_at = expiry
    assert client.get(URL + '/records/' + str(record_id)).json()['taskDeleted'] is True
    assert client.get(URL + '/records?tab=pending').json()['total'] == 0
    assert client.get(URL + '/summary').json()['counts']['overdue'] == 0


def test_database_failure_rolls_back_history_and_receipt(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    _, factory, store, _ = files_env
    original = api.finish
    monkeypatch.setattr(api, 'finish', lambda *args: (_ for _ in ()).throw(RuntimeError('fail transaction')))
    expiry = now + timedelta(hours=72)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'retry'
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ConversationTurn)) == 1
        assert session.get(RetentionTotals, 'api_cli').history_total == 0
        record = session.scalar(select(RetentionRecord))
        assert record.result == 'retry' and record.turns_removed == 0 and record.objects_pending == 0
        assert entry(session, 'api_cli', identifier).status == 'expire_pending'
    monkeypatch.setattr(api, 'finish', original)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'expired'


def test_beijing_dates_pagination_keywords_and_durable_summary(files_env):
    client, factory, _, _ = files_env
    admin(files_env)
    first = datetime(2026, 10, 20, 16, tzinfo=timezone.utc)
    with factory.begin() as session:
        for i, processed in enumerate((first - timedelta(seconds=1), first, first + timedelta(days=1))):
            record = RetentionRecord(resource_id=uuid4(), task_name='已删除任务_%', task_id=uuid4(),
                image_position=i, kind='history', result='complete', last_activity_at=first - timedelta(days=3),
                due_at=first, processed_at=processed)
            session.add(record)
            session.flush()
            finish(session, record, processed)
        session.add(RetentionRecord(resource_id=uuid4(), task_name='尚未完成', task_id=None,
            image_position=1, kind='history', result='retry', last_activity_at=first - timedelta(days=3),
            due_at=first, processed_at=first))
    query = '?tab=history&dateFrom=2026-10-21&dateTo=2026-10-21&keyword=_%&pageSize=1'
    response = client.get(URL + '/records' + query)
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1 and response.json()['items'][0]['imagePosition'] == 1
    assert client.get(URL + '/records?keyword=%27%20OR%201=1--').json()['total'] == 0
    assert client.get(URL + '/records?result=complete&pageSize=1&page=2').json()['items'][0]['imagePosition'] == 1
    # Completed details expire, totals do not; unfinished observations remain.
    run = begin_scan(factory, first)
    end_scan(factory, run, 'completed', first + timedelta(days=100))
    with factory() as session:
        records = session.scalars(select(RetentionRecord)).all()
        assert len(records) == 1 and records[0].result == 'retry'
        assert session.get(RetentionTotals, 'api_cli').history_total == 3


def test_pending_keeps_retry_barrier_during_registration(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    factory = files_env[1]
    barrier = now + timedelta(days=7)
    with factory.begin() as session:
        row = entry(session, 'api_cli', identifier)
        row.status, row.next_cleanup_at = 'expire_pending', barrier
    register_existing(factory, 25, now + timedelta(days=5))
    with factory() as session:
        row = entry(session, 'api_cli', identifier)
        assert aware(row.last_activity_at) == now and aware(row.next_cleanup_at) == barrier


def test_real_heartbeat_and_scan_state(files_env, monkeypatch, cli_enabled):
    from app.retention import summary as module
    from app.models import utcnow
    client, factory, _, _ = files_env
    admin(files_env)
    cli_enabled.cli_retention_enabled = True
    monkeypatch.setattr(module, 'get_settings', lambda: cli_enabled)
    now = utcnow()
    heartbeat(factory, now=now - timedelta(seconds=121))
    assert client.get(URL + '/summary').json()['service']['state'] == 'offline'
    heartbeat(factory, now=now)
    run = begin_scan(factory, now)
    view = client.get(URL + '/summary').json()
    assert view['service']['state'] == 'online' and view['service']['scanState'] == 'running'
    end_scan(factory, run, 'failed', now)
    view = client.get(URL + '/summary').json()
    assert view['service']['scanState'] == 'failed' and view['service']['nextScanAt'] is not None


def test_reintroduced_object_then_explicit_task_delete_completes_receipt(files_env, monkeypatch, cli_enabled):
    from app.modules.api_image_edits import deletion
    from app.modules.api_image_edits.models import ApiFile, ApiItem
    from app.retention.observability_models import RetentionObjectLink
    from app.retention.models import RetentionObject
    identifier, _, _, now, candidate = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    with factory() as session:
        file = session.get(ApiFile, candidate)
        saved = {column.name: getattr(file, column.name) for column in ApiFile.__table__.columns}
    expiry = now + timedelta(hours=72)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'expired'
    with factory.begin() as session:
        record = session.scalar(select(RetentionRecord))
        record_id, task_id = record.id, record.task_id
        session.add(ApiFile(**saved))
        session.flush()
        session.scalar(select(ApiItem).where(ApiItem.task_id == task_id)).revision_annotation_id = candidate
    # A key reintroduced after queueing must never be deleted by the retry worker.
    assert retry_objects(factory, store, now=expiry) == 0
    with factory() as session:
        assert session.get(RetentionRecord, record_id).result == 'protected'
        assert session.get(RetentionTotals, 'api_cli').history_total == 0
    assert client.delete('/api/v1/api-image-edits/tasks/' + str(task_id)).status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'
    with factory() as session:
        record = session.get(RetentionRecord, record_id)
        assert record.result == 'complete' and record.objects_removed == 1
        assert session.get(RetentionTotals, 'api_cli').history_total == 1
        assert session.scalar(select(RetentionObjectLink)) is None
        assert session.scalar(select(RetentionObject)) is None
    admin(files_env)
    assert client.get(URL + '/records/' + str(record_id)).json()['taskDeleted'] is True


def test_protected_resources_still_count_as_overdue(files_env, monkeypatch, cli_enabled):
    from app.modules.management import retention_router
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    admin(files_env)
    expiry = now + timedelta(hours=72)
    monkeypatch.setattr(retention_router, 'utcnow', lambda: expiry)
    monkeypatch.setattr(api, 'busy', lambda *args: True)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'protected'
    counts = client.get(URL + '/summary').json()['counts']
    assert counts['protected'] == 1 and counts['overdue'] == 1
    assert counts['historyTotal'] == 0
