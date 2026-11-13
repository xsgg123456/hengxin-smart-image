import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from types import SimpleNamespace

from app.execution.models import ExecutionGate
from app.modules.domestic_studio.bindings import (
    assert_unbound, freeze_for_send, read_bindings, save_bindings as save_checked,
)
from app.modules.domestic_studio.models import WorkspaceBinding
from app.modules.domestic_studio.policy import WORKSPACES


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    ExecutionGate.__table__.create(engine)
    WorkspaceBinding.__table__.create(engine)
    with Session(engine) as value:
        value.add(ExecutionGate(id=1))
        value.commit()
        yield value
    engine.dispose()


def empty_bindings():
    return dict.fromkeys(WORKSPACES)


def save_bindings(session, values, verify):
    return save_checked(session, values, verify, expected=read_bindings(session))


def test_initial_bindings_are_empty(session):
    assert read_bindings(session) == empty_bindings()


def test_bind_and_freeze_exact_installed_skill(session):
    values = empty_bindings() | {'camera': 'installed-a', 'case': 'installed-a'}
    checks = []
    assert save_bindings(session, values, checks.append) == values
    assert checks == ['installed-a', 'installed-a']
    assert freeze_for_send(session, 'camera', 'installed-a', lambda key: {'skill': {'id': key}}) == {
        'skill': {'id': 'installed-a'}, 'skillSelection': 'explicit'}


def test_invalid_catalog_entry_does_not_partially_change_bindings(session):
    initial = empty_bindings() | {'camera': 'old'}
    save_bindings(session, initial, lambda _: None)
    session.commit()
    def verify(identity):
        if identity == 'disabled':
            raise HTTPException(422, 'Skill 已停用')
    with pytest.raises(HTTPException):
        save_bindings(session, initial | {'camera': 'new', 'phone': 'disabled'}, verify)
    session.rollback()
    assert read_bindings(session) == initial


def test_client_skill_override_cannot_change_server_selection(session):
    save_bindings(session, empty_bindings() | {'camera': 'trusted'}, lambda _: None)
    with pytest.raises(HTTPException) as error:
        freeze_for_send(session, 'camera', 'other', lambda _: pytest.fail('must not freeze'))
    assert error.value.status_code == 409


def test_bound_skill_cannot_be_disabled_or_removed_until_unbound(session):
    save_bindings(session, empty_bindings() | {'camera': 'skill-a'}, lambda _: None)
    with pytest.raises(HTTPException) as error:
        assert_unbound(session, 'skill-a')
    assert error.value.status_code == 409
    save_bindings(session, empty_bindings(), lambda _: None)
    assert_unbound(session, 'skill-a')
    assert session.scalars(select(WorkspaceBinding)).all() == []


@pytest.mark.parametrize('invalid', [None, {'camera': 'x'}, {'unknown': 'x'}])
def test_complete_workspace_mapping_required(session, invalid):
    with pytest.raises((HTTPException, TypeError)):
        save_bindings(session, invalid, lambda _: None)
    assert read_bindings(session) == empty_bindings()


def test_missing_admission_gate_fails_closed(session):
    session.delete(session.get(ExecutionGate, 1))
    session.flush()
    with pytest.raises(RuntimeError, match='gate missing'):
        save_bindings(session, empty_bindings(), lambda _: None)


def test_cached_binding_is_refreshed_after_another_session_changes_it(session):
    save_bindings(session, empty_bindings() | {'camera': 'old'}, lambda _: None)
    session.commit()
    cached = session.get(WorkspaceBinding, 'camera')
    with Session(session.bind) as other:
        save_bindings(other, empty_bindings() | {'camera': 'new'}, lambda _: None)
        other.commit()
    assert cached.skill_id == 'old'  # The identity map really is stale.
    assert freeze_for_send(session, 'camera', 'new', lambda value: {'skill': {'id': value}}) == {
        'skill': {'id': 'new'}, 'skillSelection': 'explicit'}


def test_saving_refreshes_a_previously_cached_binding(session):
    save_bindings(session, empty_bindings() | {'camera': 'old'}, lambda _: None)
    session.commit()
    cached = session.get(WorkspaceBinding, 'camera')
    with Session(session.bind) as other:
        save_bindings(other, empty_bindings() | {'camera': 'third'}, lambda _: None)
        other.commit()
    assert cached.skill_id == 'old'
    expected = empty_bindings() | {'camera': 'old'}
    assert save_bindings(session, expected, lambda _: None) == expected
    session.commit()
    with Session(session.bind) as other:
        assert read_bindings(other) == expected


def test_unsupported_postgresql_isolation_fails_before_the_gate():
    class WrongIsolation:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))

        def connection(self):
            return SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(autocommit=False)))

        def scalar(self, query):
            assert str(query) == 'SHOW transaction_isolation'
            return 'repeatable read'

    with pytest.raises(RuntimeError, match='require READ COMMITTED'):
        freeze_for_send(WrongIsolation(), 'camera', None, lambda _: pytest.fail('must not freeze'))


def test_autocommit_connection_is_rejected_before_lock():
    class AutoCommit:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))

        def connection(self):
            return SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(autocommit=True)))

        def scalar(self, _query):
            pytest.fail('must reject autocommit before executing SQL')

    with pytest.raises(RuntimeError, match='transactional connections'):
        freeze_for_send(AutoCommit(), 'camera', None, lambda _: pytest.fail('must not freeze'))
