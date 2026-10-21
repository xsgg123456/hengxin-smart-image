"""Real PostgreSQL migration, locking, receipts, and object retry assertions."""
from datetime import timedelta
import importlib.util
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select, text, func
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.retention import api
from app.retention.events import receipt, finish
from app.retention.models import RetentionEntry
from app.retention.observability_models import (
    RetentionRecord, RetentionTotals, RetentionObjectLink, RetentionRun, RetentionService)
from app.retention.objects import retry_objects
from app.retention.queries import filtered
from app.retention.state import entry
from app.modules.api_image_edits.models import ApiTask, ApiItem
from test_api_cli_concurrency import pg_edit
from test_retention_concurrency import prepared_api, Store
from concurrency_helpers import compete


def test_migration_0032_repeated_changes_only_active_schedule(pg_edit):
    factory, _, _, _ = pg_edit
    now, identifier, _, _, _ = prepared_api(pg_edit)
    with factory.begin() as session:
        tracked = entry(session, 'api_cli', identifier)
        tracked.cache_cleared_at = now - timedelta(days=7)
        session.flush()
        old_activity = tracked.last_activity_at
        old_updated = tracked.updated_at
        pending_id = uuid4()
        session.add(RetentionEntry(domain='api_cli', resource_id=pending_id, status='expire_pending',
            last_activity_at=old_activity, next_cleanup_at=now + timedelta(hours=1)))
    spec = importlib.util.spec_from_file_location('retention0032',
        Path(__file__).parents[1] / 'migrations/versions/0032_retention_observability.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory().get_bind().begin() as connection:
        schema = connection.get_execution_options()['schema_translate_map'][None]
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        for model in (RetentionRecord, RetentionTotals, RetentionObjectLink, RetentionRun, RetentionService):
            model.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
    with factory() as session:
        tracked = entry(session, 'api_cli', identifier)
        assert tracked.last_activity_at == old_activity
        assert tracked.next_cleanup_at == old_activity + timedelta(hours=72)
        assert tracked.updated_at == old_updated
        assert entry(session, 'api_cli', pending_id).next_cleanup_at == now + timedelta(hours=1)
        assert session.get(RetentionTotals, 'api_cli').history_total == 0
        assert session.scalar(select(func.count()).select_from(RetentionRun)) == 0


def test_concurrent_cleaners_and_object_retries_count_once(pg_edit, tmp_path):
    factory, _, _, _ = pg_edit
    now, identifier, _, _, _ = prepared_api(pg_edit)
    outcomes = compete(lambda _: api.process(factory, Store(), tmp_path, identifier, now))
    assert outcomes.count('expired') == 1
    with factory() as session:
        record = session.scalar(select(RetentionRecord))
        assert record.result == 'objects_pending' and not record.counted
        assert session.get(RetentionTotals, 'api_cli').history_total == 0
        query, _, _ = filtered(session, 'pending', now)
        assert len(session.execute(query).all()) == 1
    assert sum(compete(lambda _: retry_objects(factory, Store(), now=now))) == 1
    with factory() as session:
        records = session.scalars(select(RetentionRecord)).all()
        assert len(records) == 1 and records[0].result == 'complete'
        assert records[0].objects_removed == 1 and records[0].objects_pending == 0
        assert session.get(RetentionTotals, 'api_cli').history_total == 1


def test_repeated_protection_updates_one_receipt_without_success(pg_edit, tmp_path):
    factory, _, _, _ = pg_edit
    now, identifier, _, _, _ = prepared_api(pg_edit, status='uncertain')
    for i in range(3):
        assert api.process(factory, Store(), tmp_path, identifier, now + timedelta(hours=i)) == 'protected'
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RetentionRecord)) == 1
        assert session.get(RetentionTotals, 'api_cli').history_total == 0
        query, _, _ = filtered(session, 'pending', now)
        assert session.execute(query).mappings().one()['result'] == 'protected'


def test_heartbeat_uses_own_session_while_scan_transaction_is_open(pg_edit, monkeypatch):
    from threading import Event, get_ident
    from app.models import utcnow
    from app.retention import service
    factory = pg_edit[0]
    observed, threads = Event(), set()
    original = service.heartbeat
    def write(*args, **kwargs):
        original(*args, **kwargs)
        threads.add(get_ident())
        if len(threads) == 2:
            observed.set()
    monkeypatch.setattr(service, 'HEARTBEAT_SECONDS', 0.02)
    monkeypatch.setattr(service, 'heartbeat', write)
    with service.beating(factory):
        with factory.begin() as held:
            held.add(RetentionRun(started_at=utcnow(), status='running'))
            held.flush()  # An unrelated scan write is still uncommitted.
            assert observed.wait(3)
            with factory() as reader:
                assert reader.get(RetentionService, 'api_cli').heartbeat_at is not None
    assert len(threads) == 2


def test_failed_scan_persists_failure_and_next_scan(pg_edit, tmp_path, monkeypatch):
    import pytest
    from app.core.config import get_settings
    from app.retention import worker
    factory = pg_edit[0]
    now, _, _, _, _ = prepared_api(pg_edit)
    settings = get_settings()
    monkeypatch.setattr(settings, 'cli_retention_enabled', True)
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    monkeypatch.setattr(worker, 'scan', lambda *args: (_ for _ in ()).throw(RuntimeError('injected')))
    with pytest.raises(RuntimeError):
        worker.run_once(factory, Store(), settings, now)
    with factory() as session:
        run = session.scalar(select(RetentionRun))
        assert run.status == 'failed' and run.finished_at >= run.started_at
        beat = session.get(RetentionService, 'api_cli')
        assert beat.next_scan_at == run.finished_at + timedelta(hours=1)


def test_resource_failure_before_receipt_still_marks_scan_failed(pg_edit, tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.retention import worker
    factory = pg_edit[0]
    now, _, _, _, _ = prepared_api(pg_edit)
    settings = get_settings()
    monkeypatch.setattr(settings, 'cli_retention_enabled', True)
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    monkeypatch.setattr(api, 'process', lambda *args: (_ for _ in ()).throw(RuntimeError('private error')))
    result = worker.run_once(factory, Store(), settings, now)
    assert result['status'] == 'failed' and 'private error' not in str(result)
    with factory() as session:
        assert session.scalar(select(RetentionRun)).status == 'failed'
