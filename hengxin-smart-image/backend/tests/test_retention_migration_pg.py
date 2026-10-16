"""API retention migration remains idempotent and preserves existing receipts."""
import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text
from app.modules.api_image_edits.models import ApiTask, ApiItem
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.retention.models import RetentionEntry, RetentionObject
from app.retention.state import entry, touch
from test_api_cli_concurrency import pg_edit
from test_retention_concurrency import prepared_api


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
