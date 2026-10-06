import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from app.main import app  # noqa: F401 - all model registrations
from app.core.config import get_settings
from app.models import Base, Job
from app.resource_models import UserRecord
from app.modules.api_image_edits.conversation import SubmitTurn, AdoptTurn, submit, adopt
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn, ConversationEvent
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask, ApiVersion, ApiChannel
from app.modules.api_image_edits.conversation_runtime import claim
from app.modules.tasks.models import ExecutionGate
from test_tasks_concurrency import compete


@pytest.fixture
def pg_edit(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'api_cli_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    with factory.begin() as session:
        users = [UserRecord(id=uuid4(), name=str(i), role='operator', status='active', identity_source='development')
                 for i in range(2)]
        session.add_all([*users, ExecutionGate(id=1), ApiChannel(id=1)])
        session.flush()
        file = ApiFile(id=uuid4(), owner_id=users[0].id, name='x.png', bucket='test', object_key=str(uuid4()),
                       content_type='image/png', checksum='a' * 64, size_bytes=1, width=8, height=6, status='ready')
        session.add(file)
        session.flush()
        task = ApiTask(id=uuid4(), owner_id=users[0].id, operator_id=users[0].id, name='test', prompt='test',
                       material_id=file.id, parameters={}, state='succeeded')
        session.add(task)
        session.flush()
        item = ApiItem(id=uuid4(), task_id=task.id, source_id=file.id, result_id=file.id,
                       position=1, state='succeeded', current_version=1)
        session.add(item)
        session.flush()
        session.add(ApiVersion(item_id=item.id, number=1, file_id=file.id, operator_id=users[0].id))
    try:
        yield factory, users, task.id, item.id
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()


def test_pg_simultaneous_submit_adopt_and_duplicate_claim(pg_edit):
    factory, users, task_id, item_id = pg_edit
    def send(i):
        with factory() as session:
            try:
                submit(session, users[i], task_id, item_id, SubmitTurn(text='调整', baseVersion=1), str(i))
                return 202
            except HTTPException as error:
                return error.status_code
    assert sorted(compete(send)) == [202, 409]
    with factory() as session:
        turn = session.scalar(select(ConversationTurn))
        turn_id, job_id = turn.id, turn.job_id
    assert sum(value is not None for value in compete(lambda _: claim(factory, job_id))) == 1
    with factory.begin() as session:
        turn = session.get(ConversationTurn, turn_id)
        turn.status, turn.candidate_id = 'candidate', turn.base_file_id
        session.get(Job, job_id).status = 'succeeded'
    def accept(i):
        with factory() as session:
            try:
                adopt(session, users[i], task_id, item_id, turn_id, AdoptTurn(expectedVersion=1), 'adopt')
                return 200
            except HTTPException as error:
                return error.status_code
    assert sorted(compete(accept)) == [200, 409]
    with factory() as session:
        assert session.get(ApiItem, item_id).current_version == 2
        assert len(session.scalars(select(ApiVersion)).all()) == 2


def test_pg_same_key_only_one_turn(pg_edit):
    factory, users, task_id, item_id = pg_edit
    def send(_):
        with factory() as session:
            submit(session, users[0], task_id, item_id, SubmitTurn(text='修改', baseVersion=1), 'same')
    compete(send)
    with factory() as session:
        assert len(session.scalars(select(ConversationTurn)).all()) == 1
        assert len(session.scalars(select(ConversationEvent)).all()) == 1


def test_pg_migration_idempotent_preserves_conversation(pg_edit):
    factory, users, task_id, item_id = pg_edit
    spec = importlib.util.spec_from_file_location('api_cli_migration',
        Path(__file__).parents[1] / 'migrations/versions/0023_api_cli_conversations.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory().get_bind().begin() as connection:
        for model in (ConversationEvent, ConversationTurn, Conversation):
            model.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
    with factory() as session:
        submit(session, users[0], task_id, item_id, SubmitTurn(text='修改', baseVersion=1), 'migration')
    with factory().get_bind().begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()
    with factory() as session:
        assert session.scalar(select(ConversationTurn)).text == '修改'
