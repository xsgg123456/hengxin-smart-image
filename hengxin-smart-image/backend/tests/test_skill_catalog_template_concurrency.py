"""Real PostgreSQL interleaving of task admission and template edits."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.main import app  # Register the complete production model metadata.
from app.models import Base
from app.core.config import get_settings
from app.contracts.business import CreateTaskInput, Picture, TemplateInput
from app.modules.skills.models import SkillRecord, SkillVersionRecord
from app.modules.tasks.models import TaskRecord
from app.modules.tasks.service import create_task
from app.modules.templates.service import save_template
from app.resource_models import FileRecord, UserRecord
from test_skill_catalog_database import database


@pytest.mark.integration
def test_edit_and_task_admission_lock_template_before_skill(database, monkeypatch):
    engine, schema = database
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', True)
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='并发测试', role='super_admin', status='active', identity_source='development')
        skill = SkillRecord(name='catalog-lock-test', mode='wallpaper', description='')
        session.add_all([user, skill])
        session.flush()
        session.add(SkillVersionRecord(skill=skill, version='1.0.0', status='available', checksum='a' * 64,
            bucket='test', object_key=str(uuid4())))
        picture = FileRecord(owner_id=user.id, name='image.png', bucket='test', object_key=str(uuid4()),
            content_type='image/png', checksum='b' * 64, size_bytes=10, width=1, height=1, status='ready')
        session.add(picture)
    image = Picture(name='image.png', fileId=str(picture.id), url='/test')
    body = TemplateInput(name='模板', mode='wallpaper', images=[image], skillVersionId=str(skill.id),
                         active=True, notes='')
    with factory() as session:
        template = save_template(session, user, body)
    task_locked, editor_attempt = Event(), Event()
    def before(connection, cursor, statement, parameters, context, many):
        if (connection.info.get('catalog_test_role') == 'editor' and '.templates' in statement
                and ('FOR UPDATE' in statement or statement.startswith('UPDATE'))):
            editor_attempt.set()
    def after(connection, cursor, statement, parameters, context, many):
        if (connection.info.get('catalog_test_role') == 'task' and '.templates' in statement
                and 'FOR UPDATE' in statement):
            task_locked.set()
            assert editor_attempt.wait(5), 'Editor never attempted its template lock'
    event.listen(engine, 'before_cursor_execute', before)
    event.listen(engine, 'after_cursor_execute', after)
    def admit():
        with factory() as session:
            session.connection().info['catalog_test_role'] = 'task'
            session.execute(text("SET LOCAL statement_timeout = '8s'"))
            return create_task(session, user, CreateTaskInput(mode='wallpaper', name='并发任务',
                templateId=template.id, templateVersion=1, sources=[image], note=''), 'concurrent-create')
    def edit():
        assert task_locked.wait(5)
        with factory() as session:
            session.connection().info['catalog_test_role'] = 'editor'
            session.execute(text("SET LOCAL statement_timeout = '8s'"))
            return save_template(session, user, body.model_copy(update={'expectedVersion': 1}), UUID(template.id))
    try:
        with ThreadPoolExecutor(2) as executor:
            admitted, edited = executor.submit(admit), executor.submit(edit)
            receipt, updated = admitted.result(timeout=12), edited.result(timeout=12)
    finally:
        event.remove(engine, 'before_cursor_execute', before)
        event.remove(engine, 'after_cursor_execute', after)
    assert updated.version == 2
    with factory() as session:
        assert session.get(TaskRecord, UUID(receipt.taskId)).template_snapshot['version'] == 1
        with pytest.raises(HTTPException) as stale:
            save_template(session, user, body.model_copy(update={'expectedVersion': 1}), UUID(template.id))
        assert stale.value.status_code == 409
