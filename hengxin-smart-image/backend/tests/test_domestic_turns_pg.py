"""Real transaction tests for fixed-Skill submission and private inputs."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models import Job, Outbox
from app.modules.domestic_studio.bindings import read_bindings, save_bindings
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion, ConversationRequest, Workspace
from app.modules.domestic_studio.conversation_service import create
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.modules.domestic_studio.models import SkillExecutionReference
from app.modules.domestic_studio.skill_state import DomesticSkillState
from app.modules.domestic_studio.turn_models import Picture, Turn, Upload
from app.modules.domestic_studio import turn_service
from app.modules.management.models import SystemSettings
from app.overseas.studio.schemas import NewConversation, Send
from app.resource_models import UserRecord
from test_domestic_installed_skills import install_fixture
from test_domestic_studio_bindings_pg import database


@pytest.fixture
def context(database, tmp_path, monkeypatch):
    monkeypatch.setenv('DOMESTIC_STUDIO_LOCK_ROOT', str(tmp_path / 'shared-locks'))
    for model in (UserRecord, Job, Outbox, Workspace, Conversation, ConversationDeletion, ConversationRequest,
                  DomesticSkillState, SkillExecutionReference, Turn, Upload, Picture, SystemSettings):
        model.__table__.create(database)
    monkeypatch.setattr(turn_service, 'get_settings', lambda: SimpleNamespace(enable_codex_executor=True))
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    installed = DomesticInstalledSkills(root, protected=False)
    skill = installed.list()[0]
    factory = sessionmaker(database, expire_on_commit=False)
    first, second = uuid4(), uuid4()
    with factory.begin() as session:
        for identity in (first, second):
            session.add(UserRecord(id=identity, name='国内成员', role='designer', status='active',
                                   identity_source='development', directory_state='enrolled'))
        session.add(DomesticSkillState(name=skill['name'], enabled=True, version=1))
        session.flush()
        one = create(session, first, 'camera', NewConversation(), 'one').id
        two = create(session, second, 'camera', NewConversation(), 'two').id
    return factory, installed, skill, first, second, one, two


def bind(session, identity):
    old = read_bindings(session)
    save_bindings(session, old | {'camera': identity}, lambda _: None, expected=old)


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_unbound_explicit_selection_never_enqueues(context):
    factory, catalog, skill, actor, _, channel, _ = context
    for identity in (skill['id'], uuid4()):
        with pytest.raises(HTTPException) as error:
            with factory.begin() as session:
                turn_service.send(session, actor, 'camera', channel,
                    Send(text='用户输入', skillId=identity), str(uuid4()), catalog)
        assert error.value.status_code == 409
    with factory() as session:
        assert [count(session, model) for model in (Job, Outbox, Turn, SkillExecutionReference)] == [0, 0, 0, 0]


def test_enqueue_freezes_skill_with_job_and_retry_creates_no_duplicate(context):
    factory, catalog, skill, actor, _, channel, _ = context
    with factory.begin() as session:
        bind(session, skill['id'])
    body = Send(conversationId=channel, text='实际用户要求', skillId=skill['id'])
    with factory.begin() as session:
        turn_service.send(session, actor, 'camera', channel, body, 'request', catalog)
        turn_service.send(session, actor, 'camera', channel, body, 'request', catalog)
    with factory() as session:
        assert [count(session, model) for model in (Job, Outbox, Turn, SkillExecutionReference)] == [1, 1, 1, 1]
        turn = session.scalar(select(Turn))
        assert turn.text == turn.snapshot['text'] == '实际用户要求'
        assert turn.snapshot['skill'] == catalog.freeze(skill['id'])
        assert session.get(SkillExecutionReference, turn.job_id).checksum == turn.snapshot['skill']['checksum']
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, actor, 'camera', channel, body, 'different', catalog)
    assert error.value.status_code == 409


def test_other_members_attachments_cannot_be_sent(context):
    factory, catalog, skill, actor, other, channel, other_channel = context
    identity = uuid4()
    with factory.begin() as session:
        bind(session, skill['id'])
        session.add(Upload(id=identity, conversation_id=other_channel, name='资料.png',
            content_type='image/png', size_bytes=10, checksum='a' * 64,
            bucket='private', object_key='private-other-owner'))
    body = Send(conversationId=channel, text='处理', attachmentIds=['upload:' + str(identity)])
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, actor, 'camera', channel, body, 'request', catalog)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, other, 'camera', channel, Send(text='处理'), 'other', catalog)
    assert error.value.status_code == 404
    with factory() as session:
        assert count(session, Job) == 0


def test_stop_is_owner_scoped_and_queued_job_never_starts(context):
    factory, catalog, skill, actor, other, channel, _ = context
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='处理'), 'send', catalog)
        turn = session.scalar(select(Turn))
        turn_id, job_id, version = turn.id, turn.job_id, turn.version
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.cancel(session, other, 'camera', channel, turn_id, version)
    assert error.value.status_code == 404
    with factory.begin() as session:
        turn_service.cancel(session, actor, 'camera', channel, turn_id, version)
    with factory() as session:
        assert session.get(Job, job_id).status == 'cancelled'
        assert session.get(Job, job_id).execution_count == 0
        assert session.get(Outbox, job_id).completed_at is not None
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.cancel(session, actor, 'camera', channel, turn_id, version)
    assert error.value.status_code == 409
