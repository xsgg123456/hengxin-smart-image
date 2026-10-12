from itertools import combinations
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import Column, Integer, MetaData, Table, Uuid, create_engine, select

from app.overseas.permissions import (
    Principal, capabilities, can_access_task, require_task_access, task_filter,
)


@pytest.mark.parametrize('role,expected', [
    ('operator', {'task.read', 'task.create', 'stats.read'}),
    ('operator_manager', {'task.read', 'task.create', 'stats.read'}),
    ('designer', {'task.read', 'task.design', 'stats.read'}),
    ('design_manager', {'task.read', 'task.design', 'task.reassign', 'stats.read'}),
    ('super_admin', {'task.read', 'task.reassign', 'stats.read', 'members.manage',
                     'skills.manage', 'settings.manage'}),
])
def test_five_role_capabilities(role, expected):
    assert set(capabilities([role])) == expected


@pytest.mark.parametrize('roles', [(), ('administrator',), ('super_admin', 'domestic_admin')])
def test_empty_unknown_and_domestic_roles_do_not_grant_access(roles):
    assert capabilities(roles) == []
    principal = Principal(uuid4(), frozenset(roles))
    with pytest.raises(HTTPException) as error:
        require_task_access(principal, principal.id, principal.id)
    assert error.value.status_code == 403


def test_super_admin_does_not_implicitly_become_operator_or_designer():
    uid = uuid4()
    admin = Principal(uid, frozenset(('super_admin',)))
    assert not can_access_task(admin, uid, uid, 'task.create')
    assert not can_access_task(admin, uid, uid, 'task.design')
    combined = Principal(uid, frozenset(('super_admin', 'designer', 'operator')))
    assert can_access_task(combined, uuid4(), uid, 'task.design')
    assert not can_access_task(combined, uid, uuid4(), 'task.design')
    assert can_access_task(combined, uid, uid, 'task.create')


ROLES = ('operator', 'operator_manager', 'designer', 'design_manager', 'super_admin')
COMBINATIONS = [roles for size in range(1, 6) for roles in combinations(ROLES, size)]


@pytest.mark.parametrize('roles', COMBINATIONS)
def test_sql_list_detail_and_actions_share_real_ownership_scope(roles):
    own, other = uuid4(), uuid4()
    principal = Principal(own, frozenset(roles))
    engine = create_engine('sqlite://')
    metadata = MetaData()
    tasks = Table('overseas_test_tasks', metadata, Column('id', Integer, primary_key=True),
                  Column('created_by', Uuid), Column('designer_id', Uuid))
    metadata.create_all(engine)
    fixtures = [dict(id=1, created_by=own, designer_id=other),
                dict(id=2, created_by=other, designer_id=own),
                dict(id=3, created_by=other, designer_id=other),
                dict(id=4, created_by=own, designer_id=own)]
    try:
        with engine.begin() as connection:
            connection.execute(tasks.insert(), fixtures)
            for action in ('task.read', 'stats.read', 'task.design', 'task.reassign'):
                if action in ('task.read', 'stats.read'):
                    expected = ({1, 2, 3, 4} if any(r in roles for r in (
                        'operator_manager', 'design_manager', 'super_admin')) else
                        ({1, 4} if 'operator' in roles else set()) |
                        ({2, 4} if 'designer' in roles else set()))
                elif action == 'task.design':
                    expected = {1, 2, 3, 4} if 'design_manager' in roles else (
                        {2, 4} if 'designer' in roles else set())
                else:
                    expected = {1, 2, 3, 4} if any(r in roles for r in (
                        'design_manager', 'super_admin')) else set()
                visible = set(connection.scalars(select(tasks.c.id).where(task_filter(
                    principal, tasks.c.created_by, tasks.c.designer_id, action))))
                assert visible == expected
                for task in fixtures:
                    assert can_access_task(principal, task['created_by'], task['designer_id'], action) == (task['id'] in expected)
                    if task['id'] not in expected:
                        with pytest.raises(HTTPException):
                            require_task_access(principal, task['created_by'], task['designer_id'], action)
    finally:
        engine.dispose()


def test_unknown_action_is_denied_even_to_super_admin():
    principal = Principal(uuid4(), frozenset(('super_admin',)))
    assert not can_access_task(principal, principal.id, principal.id, 'unknown')
