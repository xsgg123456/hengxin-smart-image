"""Migration runs twice on an actual PostgreSQL old-schema shape, preserving audit."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text

from app.models import utcnow
from app.modules.api_image_edits.models import ApiAttempt, ApiItem
from app.modules.api_image_edits.service import submit
from test_api_image_domain import enabled_api
from test_api_image_execution_pg import pg_api

pytestmark = pytest.mark.integration


def test_retry_migration_preserves_legacy_terminals_and_never_resets_budget(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        task_id = submit(session, user, data, 'legacy-migrate')
    with factory.begin() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == task_id))
        item.state, item.cycle_retries = 'failed', 3
        for _ in range(6):
            session.add(ApiAttempt(item_id=item.id, operator_id=user.id,
                state='uncertain', completed_at=utcnow()))
        item_id = item.id
    path = Path(__file__).parents[1] / 'migrations/versions/0031_api_retry_policy.py'
    spec = importlib.util.spec_from_file_location('retry_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory.kw['bind'].begin() as connection:
        for table, columns in migration.columns().items():
            for column in columns:
                connection.execute(text(f'ALTER TABLE {table} DROP COLUMN {column.name}'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            with pytest.raises(RuntimeError, match='cannot be discarded'):
                migration.downgrade()
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'failed'
        assert item.retry_policy_version == 'legacy-v1' and item.retry_cycle_id is None
        assert item.attempts == item.max_attempts == 4
        attempts = session.scalars(select(ApiAttempt)).all()
        assert len(attempts) == 6
        assert all(a.state == 'uncertain' and a.completed_at for a in attempts)
    # Explicit new user action upgrades the policy; migration itself never does.
    from app.modules.api_image_edits.versions import retry_item
    with factory() as session:
        retry_item(session, user, task_id, item_id, 'new-policy')
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.max_attempts == 20 and item.attempts == 0
        assert item.retry_cycle_id and item.retry_policy_version == 'bounded-v2'
    from app.modules.api_image_edits.claims import claim, start_attempt
    claimed = claim(factory)
    assert start_attempt(factory, *claimed[:2])  # Historical unknown audit is not live capacity.
