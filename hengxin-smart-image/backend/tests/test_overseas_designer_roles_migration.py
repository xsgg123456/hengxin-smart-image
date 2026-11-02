"""Real PostgreSQL 0023 -> 0024 role conversion and immutable history checks."""
from datetime import datetime, timezone
import runpy
import subprocess
import sys
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.exc import IntegrityError

from test_overseas_database import BACKEND, disposable_databases, migration_environment, snapshot


@pytest.mark.integration
def test_legacy_roles_convert_once_preserving_identity_status_tasks_and_history(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0023'], cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    times = dict(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    members = [uuid4() for _ in range(6)]
    roles = ['operator', 'operator_manager', 'designer', 'design_manager', 'super_admin', 'operator']
    expected = ['designer', 'design_manager', 'designer', 'design_manager', 'super_admin', 'designer']
    try:
        with engine.begin() as connection:
            md = MetaData()
            md.reflect(connection)
            for index, (identity, role) in enumerate(zip(members, roles)):
                connection.execute(md.tables['overseas_members'].insert().values(id=identity,
                    corp_id='test', provider_user_id=str(identity), name='历史成员', department='设计',
                    status=['active', 'disabled', 'pending'][index % 3], version=7,
                    directory_state='enrolled' if index < 5 else 'legacy_unconfirmed', **times))
                connection.execute(md.tables['overseas_member_roles'].insert().values(
                    id=uuid4(), user_id=identity, role=role, **times))
            task_id = uuid4()
            connection.execute(md.tables['overseas_tasks'].insert().values(id=task_id, name='历史图需',
                product_name='产品', brand='品牌', platform='Amazon', market='US', remarks='历史说明',
                created_by=members[0], designer_id=members[2], status='returned', workflow='studio',
                version=3, requirements_approved=False, material_ids=[], **times))
            connection.execute(md.tables['overseas_member_audits'].insert().values(id=uuid4(),
                member_id=members[0], actor_id=members[4], action='update',
                before={'roles': []}, after={'roles': ['operator'], 'version': 7}, **times))
            connection.execute(md.tables['overseas_requirements_reviews'].insert().values(id=uuid4(),
                task_id=task_id, actor_id=members[2], actor_name='设计', decision='reject',
                comment='补充', version=2, submission={'remarks': '历史说明', 'market': 'US'}, **times))
            original_members = {row['id']: dict(row) for row in connection.execute(
                select(md.tables['overseas_members'])).mappings()}
            original_roles = {row['user_id']: dict(row) for row in connection.execute(
                select(md.tables['overseas_member_roles'])).mappings()}
        original = snapshot(url)
        domestic_before = snapshot(domestic)
        result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
            'upgrade', 'overseas_0024'], cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
        assert result.returncode == 0, result.stderr
        after = snapshot(url)
        # Every other table, including audits, review snapshots, tasks and ownership, is identical.
        for table, rows in original[1].items():
            if table not in ('overseas_alembic_version', 'overseas_members', 'overseas_member_roles'):
                assert after[1][table] == rows, table
        with engine.begin() as connection:
            for index, identity in enumerate(members):
                row = connection.execute(select(md.tables['overseas_members']).where(
                    md.tables['overseas_members'].c.id == identity)).mappings().one()
                assert {key: value for key, value in row.items() if key not in ('version', 'updated_at')} == {
                    key: value for key, value in original_members[identity].items() if key not in ('version', 'updated_at')}
                assert row['version'] == (8 if roles[index].startswith('operator') else 7)
                assert row['status'] == ['active', 'disabled', 'pending'][index % 3]
                assert row['created_at'] == times['created_at']
                assert row['directory_state'] == ('enrolled' if index < 5 else 'legacy_unconfirmed')
                role_row = connection.execute(select(md.tables['overseas_member_roles']).where(
                    md.tables['overseas_member_roles'].c.user_id == identity)).mappings().one()
                assert {key: value for key, value in role_row.items() if key not in ('role', 'updated_at')} == {
                    key: value for key, value in original_roles[identity].items() if key not in ('role', 'updated_at')}
                assert role_row['role'] == expected[index] and role_row['created_at'] == times['created_at']
                assert role_row['id'] in {entry[0] for entry in original[1]['overseas_member_roles']}
            with Operations.context(MigrationContext.configure(connection)):
                upgrade = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0024_designer_roles.py'))['upgrade']
                upgrade()
                upgrade()
        assert snapshot(url) == after
        for role in ('operator', 'operator_manager'):
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(text('UPDATE overseas_member_roles SET role=:role WHERE user_id=:id'),
                                   {'role': role, 'id': members[0]})
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
