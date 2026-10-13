"""Single-role database migration, API boundary and bootstrap regressions."""
import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from test_overseas_auth import overseas, seed
from app.overseas.auth.models import MemberRole
from app.overseas.members.bootstrap import bootstrap_admins
from sqlalchemy import select


def test_database_rejects_second_role(overseas):
    _, factory, _ = overseas
    member = seed(factory)
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(MemberRole(user_id=member, role='operator'))


def test_bootstrap_replaces_existing_role(overseas):
    _, factory, _ = overseas
    member = seed(factory, roles=('operator',))
    with factory() as session:
        assert bootstrap_admins(session, 'corp', 'member-1') == 1
        assert list(session.scalars(select(MemberRole.role).where(MemberRole.user_id == member))) == ['super_admin']


def legacy_database():
    # Reflect the pre-0011 schema with no user_id-only unique constraint.
    import sqlalchemy as sa
    engine = create_engine('sqlite://')
    md = sa.MetaData()
    sa.Table('overseas_members', md, sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('status', sa.String), sa.Column('version', sa.Integer), sa.Column('updated_at', sa.DateTime))
    sa.Table('overseas_member_roles', md, sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('user_id', sa.Uuid), sa.Column('role', sa.String))
    sa.Table('overseas_member_audits', md, sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('member_id', sa.Uuid), sa.Column('actor_id', sa.Uuid), sa.Column('action', sa.String),
        sa.Column('before', sa.JSON), sa.Column('after', sa.JSON),
        sa.Column('created_at', sa.DateTime), sa.Column('updated_at', sa.DateTime))
    md.create_all(engine)
    return engine, md


def migrate(connection):
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0011_single_member_role.py'
    with Operations.context(MigrationContext.configure(connection)):
        runpy.run_path(str(path))['upgrade']()


@pytest.mark.parametrize('ambiguous', [False, True])
def test_migration_admin_audit_or_ambiguous_atomic_refusal(ambiguous):
    engine, md = legacy_database()
    admin, ordinary = uuid4(), uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(md.tables['overseas_members'].insert(), [
                {'id': uid, 'status': 'active', 'version': 1} for uid in (admin, ordinary)])
            values = [(admin, 'super_admin'), (admin, 'designer'), (ordinary, 'operator')]
            if ambiguous:
                values.append((ordinary, 'designer'))
            conn.execute(md.tables['overseas_member_roles'].insert(),
                         [{'id': uuid4(), 'user_id': uid, 'role': role} for uid, role in values])
            if ambiguous:
                with pytest.raises(RuntimeError, match=str(ordinary)):
                    migrate(conn)
                assert conn.scalar(text('SELECT count(*) FROM overseas_member_roles')) == 4
                assert conn.scalar(text('SELECT count(*) FROM overseas_member_audits')) == 0
            else:
                migrate(conn)
                assert conn.scalar(text('SELECT count(*) FROM overseas_member_roles')) == 2
                audit = conn.execute(select(md.tables['overseas_member_audits'])).mappings().one()
                assert audit['before']['roles'] == ['designer', 'super_admin']
                assert audit['after']['roles'] == ['super_admin']
                assert audit['after']['version'] == 2
                with pytest.raises(IntegrityError):
                    conn.execute(md.tables['overseas_member_roles'].insert(),
                                 {'id': uuid4(), 'user_id': ordinary, 'role': 'designer'})
    finally:
        engine.dispose()


def test_admin_can_reject_and_resubmit_unowned_unassigned_task(materials, monkeypatch):
    from app.overseas.materials import parsers
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: '完整资料')
    from uuid import UUID
    from test_overseas_requirements import pending, review
    from test_overseas_tasks import add_member, payload
    from test_overseas_plans import post
    from test_overseas_assignment import change_roles
    from app.overseas.tasks.models import Task
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    stranger = add_member(factory, ('operator',))
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).created_by = stranger
    change_roles(factory, actor, ('super_admin',))
    rejected = review(client, task, 'reject', '补充')
    assert rejected.status_code == 200
    body = {**payload(designer), 'version': 2, 'materialIds': [original['id']]}
    assert post(client, task, '/resubmit', body).status_code == 200
    assert post(client, task, '/resubmit', {**body, 'version': 3}, 'invalid-state').status_code == 409


from test_overseas_materials import materials
