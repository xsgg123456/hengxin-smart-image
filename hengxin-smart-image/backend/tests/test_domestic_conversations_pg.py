"""Exercise creator isolation, retries and the cap against real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.member_policy import lock_permissions
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion, ConversationRequest, Workspace
from app.modules.domestic_studio.conversation_service import create, owned, rename
from app.overseas.studio.schemas import NewConversation, RenameConversation
from app.resource_models import UserRecord
from test_domestic_studio_bindings_pg import database


@pytest.fixture
def context(database):
    for model in (UserRecord, Workspace, Conversation, ConversationDeletion, ConversationRequest):
        model.__table__.create(database)
    factory = sessionmaker(database, expire_on_commit=False)
    first, second = uuid4(), uuid4()
    with factory.begin() as session:
        for identity, name in ((first, '甲'), (second, '乙')):
            session.add(UserRecord(id=identity, name=name, role='designer', status='active',
                                   identity_source='development', directory_state='enrolled'))
    return factory, first, second


def test_conversation_and_workspace_are_both_creator_scoped(context):
    factory, first, second = context
    with factory.begin() as session:
        original = create(session, first, 'camera', NewConversation(name='相机'), 'request-1')
        identity = original.id
        assert create(session, first, 'camera', NewConversation(name='相机'), 'request-1').id == identity
        with pytest.raises(HTTPException) as error:
            owned(session, second, 'camera', identity)
        assert error.value.status_code == 404
        with pytest.raises(HTTPException) as error:
            owned(session, first, 'case', identity)
        assert error.value.status_code == 404
        with pytest.raises(HTTPException) as error:
            create(session, first, 'camera', NewConversation(name='不同'), 'request-1')
        assert error.value.status_code == 409
    with factory.begin() as session:
        other = create(session, second, 'camera', NewConversation(), 'request-1')
        assert other.id != identity
        case = create(session, first, 'case', NewConversation(), 'request-1')
        assert case.id not in (other.id, identity)


def test_rename_checks_version_and_retries_without_duplicate_change(context):
    factory, first, second = context
    with factory.begin() as session:
        identity = create(session, first, 'camera', NewConversation(), 'create').id
    body = RenameConversation(name='新名称', version=1)
    with factory.begin() as session:
        row = rename(session, first, 'camera', identity, body, 'rename')
        assert row.version == 2 and row.name == '新名称'
        assert rename(session, first, 'camera', identity, body, 'rename').version == 2
    with factory.begin() as session:
        with pytest.raises(HTTPException) as error:
            rename(session, first, 'camera', identity, RenameConversation(name='旧版本', version=1), 'another')
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            rename(session, second, 'camera', identity, body, 'rename')
        assert error.value.status_code == 404
        assert session.get(Workspace, (first, 'camera')).version == 3


def test_concurrent_creates_cannot_exceed_ten(context):
    factory, first, _ = context
    def attempt(index):
        try:
            with factory.begin() as session:
                return str(create(session, first, 'camera', NewConversation(), f'key-{index}').id)
        except HTTPException as error:
            assert error.status_code == 409
            return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))
    assert len({item for item in results if item}) == 10
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 10
        assert session.scalar(select(func.count()).select_from(ConversationRequest)) == 10


def test_revocation_is_rechecked_after_permission_lock(context):
    factory, first, _ = context
    started = Event()
    def attempt():
        with factory.begin() as session:
            started.set()
            with pytest.raises(HTTPException) as error:
                create(session, first, 'camera', NewConversation(), 'create')
            assert error.value.status_code == 403
    with factory() as revoker, ThreadPoolExecutor(max_workers=1) as pool:
        lock_permissions(revoker)
        revoker.get(UserRecord, first).status = 'disabled'
        revoker.flush()
        future = pool.submit(attempt)
        assert started.wait(5)
        revoker.commit()
        future.result(timeout=10)
    with Session(factory.kw['bind']) as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
