"""Migration and legacy retention ownership with real isolated PostgreSQL."""
import importlib.util
from datetime import timedelta
from pathlib import Path
from uuid import UUID
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import select, text
from app.core.config import get_settings
from app.models import Job, utcnow
from app.contracts.business import RevisionInput
from app.modules.api_image_edits.models import ApiTask, ApiItem
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.tasks.models import TaskRecord, RoundRecord
from app.modules.tasks.service import create_task, accept_round
from app.modules.tasks.claims import claim as claim_legacy
from app.retention import legacy, paths
from app.retention.models import RetentionEntry, RetentionObject
from app.retention.state import entry, touch
from test_api_cli_concurrency import pg_edit
from test_tasks_concurrency import compete, pg_tasks
from test_retention_concurrency import Store, prepared_api


def test_pg_migration_0024_repeated_preserves_business_and_receipts(pg_edit):
    factory, _, task_id, item_id = pg_edit
    now, identifier, turn_id, _, _ = prepared_api(pg_edit)
    spec = importlib.util.spec_from_file_location('retention_migration',
        Path(__file__).parents[1] / 'migrations/versions/0024_cli_retention.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory().get_bind().begin() as connection:
        schema = connection.get_execution_options()['schema_translate_map'][None]
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        RetentionObject.__table__.drop(connection)
        RetentionEntry.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
    with factory.begin() as session:
        touch(session, 'api_cli', identifier, now)
        session.add(RetentionObject(bucket='test', object_key='receipt', next_attempt_at=now, attempts=3))
    with factory().get_bind().begin() as connection:
        schema = connection.get_execution_options()['schema_translate_map'][None]
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()
            migration.upgrade()
    with factory() as session:
        assert session.get(ApiTask, task_id).prompt == 'test'
        assert session.get(ApiItem, item_id).current_version == 1
        assert session.get(ConversationTurn, turn_id).text == '测试意见'
        assert entry(session, 'api_cli', identifier).last_activity_at == now
        assert session.scalar(select(RetentionObject)).attempts == 3


@pytest.mark.parametrize('active', [False, True])
def test_pg_legacy_cleaners_serialize_and_protect_uncertain(pg_tasks, tmp_path, monkeypatch, active):
    factory, user, _, body = pg_tasks
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    with factory() as session:
        receipt = create_task(session, user, body, 'legacy-retention')
    identifier = UUID(receipt.taskId)
    now = utcnow()
    directory = tmp_path / str(identifier)
    directory.mkdir()
    (directory / 'history.json').write_text('history', encoding='utf-8')
    with factory.begin() as session:
        turn = session.get(RoundRecord, UUID(receipt.roundId))
        turn.status = 'uncertain' if active else 'succeeded'
        turn.finished_at = None if active else now
        session.get(Job, turn.job_id).status = turn.status
        row = entry(session, 'legacy_cli', identifier)
        row.last_activity_at = row.initialized_at = now - timedelta(days=8)
        row.next_cleanup_at = now - timedelta(days=1)
    outcomes = compete(lambda _: legacy.process(factory, Store(), tmp_path, identifier, now))
    with factory() as session:
        row = entry(session, 'legacy_cli', identifier)
        assert session.get(TaskRecord, identifier)
        if active:
            assert outcomes == ['active_execution', 'active_execution']
            assert row.status == 'active'
            assert directory.exists()
        else:
            assert outcomes.count('expired') == 1
            assert row.status == 'expired'
            assert row.counters == {'roundsCleared': 1}
            assert not directory.exists()


def test_pg_legacy_pending_fence_blocks_new_round_and_claim(pg_tasks, tmp_path, monkeypatch):
    factory, user, _, body = pg_tasks
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    with factory() as session:
        receipt = create_task(session, user, body, 'legacy-fence')
    identifier, now = UUID(receipt.taskId), utcnow()
    with factory.begin() as session:
        turn = session.get(RoundRecord, UUID(receipt.roundId))
        turn.status, turn.finished_at = 'succeeded', now
        job_id = turn.job_id
        session.get(Job, job_id).status = 'succeeded'
        row = entry(session, 'legacy_cli', identifier)
        row.last_activity_at = row.initialized_at = now - timedelta(days=8)
        row.next_cleanup_at = now - timedelta(days=1)
    def fail(*args, **kwargs):
        raise OSError('isolated cleanup failure')
    monkeypatch.setattr(paths, 'clean', fail)
    assert legacy.process(factory, Store(), tmp_path, identifier, now) == 'retry'
    assert claim_legacy(factory, job_id) is None
    with factory() as session:
        with pytest.raises(HTTPException) as error:
            accept_round(session, user, identifier, RevisionInput(taskId=str(identifier), target=None, note='修改'), 'blocked')
        assert error.value.status_code == 409
    with factory() as session:
        assert entry(session, 'legacy_cli', identifier).status == 'expire_pending'
        assert len(session.scalars(select(RoundRecord)).all()) == 1
        assert session.get(Job, job_id).execution_count == 0
