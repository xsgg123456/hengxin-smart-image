"""Retirement is atomic, snapshot-bound, idempotent and domestic-only."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.modules.auth.application_models import MemberAudit
from app.modules.auth.models import AuthSessionRecord, RoleAssignmentRecord, UserIdentityRecord
from app.modules.auth.sessions import issue_session
from app.resource_models import UserRecord

script = Path(__file__).resolve().parents[3] / 'scripts/maintenance/retire_domestic_design_manager.py'
spec = importlib.util.spec_from_file_location('role_retirement', script)
retirement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retirement)


@pytest.fixture(params=['sqlite', 'postgresql'])
def retirement_env(request):
    url = os.getenv('TEST_DOMESTIC_STUDIO_DATABASE_URL')
    if request.param == 'postgresql' and not url:
        pytest.skip('Requires explicit isolated PostgreSQL URL')
    schema = 'role_retirement_' + uuid4().hex
    engine = create_engine(url if request.param == 'postgresql' else 'sqlite://')
    if request.param == 'postgresql':
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
        engine.dispose()
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    tables = [model.__table__ for model in
              (UserRecord, UserIdentityRecord, RoleAssignmentRecord, MemberAudit, AuthSessionRecord)]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        users = [UserRecord(name=f'测试成员{n}', role=role, status='active',
                            identity_source='dingtalk', directory_state='enrolled')
                 for n, role in enumerate(['super_admin'] + ['operator'] * 17
                                          + ['designer'] * 5 + ['design_manager'] * 2)]
        session.add_all(users)
        session.flush()
        for n, user in enumerate(users):
            session.add(UserIdentityRecord(user_id=user.id, provider='dingtalk', corp_id='test-corp',
                        provider_user_id=f'person-{n}', union_id=f'union-{n}', department='测试部门'))
            if n:
                session.add(RoleAssignmentRecord(user_id=user.id, role=user.role))
            issue_session(session, user.id)
        session.flush()
        expected = retirement.export_snapshot(session)
        changes = [dict(id=str(user.id), name=user.name, fromRole=user.role,
                        toRole='super_admin' if n == 1 else 'designer')
                   for n, user in enumerate(users[-2:])]
        manifest = dict(actorId=str(users[0].id), expectedMembers=expected, changes=changes)
    try:
        yield factory, manifest
    finally:
        engine.dispose()
        if request.param == 'postgresql':
            cleanup = create_engine(url)
            with cleanup.begin() as conn:
                conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            cleanup.dispose()


def snapshot(factory):
    with factory() as session:
        return retirement.export_snapshot(session)


def test_dry_run_apply_repeat_preserves_members_sessions_and_actor(retirement_env):
    factory, manifest = retirement_env
    before = snapshot(factory)
    with factory.begin() as session:
        receipt = retirement.apply_retirement(session, manifest)
        assert receipt['state'] == 'dry_run'
    assert snapshot(factory) == before
    with factory.begin() as session:
        result = retirement.apply_retirement(session, manifest, apply=True)
        assert result['rolesBefore'] == {'super_admin': 1, 'operator': 17, 'designer': 5, 'design_manager': 2}
        assert result['rolesAfter'] == {'super_admin': 2, 'operator': 17, 'designer': 6}
    after = snapshot(factory)
    target_ids = {change['id'] for change in manifest['changes']}
    for old, new in zip(before, after):
        if old['id'] not in target_ids:
            assert old == new
        else:
            assert new['identities'] == old['identities']
            assert new['status'] == old['status'] and new['directoryState'] == old['directoryState']
            assert new['assignment']['role'] == new['role']
            assert new['assignment']['assignedBy'] == manifest['actorId']
    with factory.begin() as session:
        assert retirement.apply_retirement(session, manifest, apply=True)['state'] == 'already_applied'
        audits = session.scalars(select(MemberAudit)).all()
        assert len(audits) == 2 and all(a.actor_id == UUID(manifest['actorId']) for a in audits)
        assert all(a.before['role'] == 'design_manager' for a in audits)
        sessions = session.scalars(select(AuthSessionRecord)).all()
        assert len(sessions) == 25 and all(s.revoked_at is None for s in sessions)
    assert snapshot(factory) == after


@pytest.mark.parametrize('drift', ['name', 'role', 'status', 'identity', 'assignment', 'extra'])
def test_snapshot_drift_refused_before_any_write(retirement_env, drift):
    factory, manifest = retirement_env
    with factory.begin() as session:
        user = session.get(UserRecord, UUID(manifest['changes'][0]['id']))
        if drift in ('name', 'role', 'status'):
            setattr(user, drift, {'name': '变更姓名', 'role': 'designer', 'status': 'disabled'}[drift])
        elif drift == 'identity':
            session.scalar(select(UserIdentityRecord).where(
                UserIdentityRecord.user_id == user.id)).provider_user_id = 'changed'
        elif drift == 'assignment':
            session.scalar(select(RoleAssignmentRecord).where(
                RoleAssignmentRecord.user_id == user.id)).role = 'operator'
        else:
            session.add(UserRecord(name='新增成员', role='operator', status='active',
                                   identity_source='dingtalk'))
    before = snapshot(factory)
    with pytest.raises(ValueError, match='snapshot'):
        with factory.begin() as session:
            retirement.apply_retirement(session, manifest, apply=True)
    assert snapshot(factory) == before
    with factory() as session:
        assert session.scalar(select(MemberAudit)) is None


@pytest.mark.parametrize('invalid', ['missing_target', 'duplicate_id', 'wrong_name', 'ambiguous_name'])
def test_invalid_target_set_refused(retirement_env, invalid):
    factory, manifest = retirement_env
    invalid_manifest = deepcopy(manifest)
    if invalid == 'missing_target':
        invalid_manifest['changes'].pop()
    elif invalid == 'duplicate_id':
        invalid_manifest['changes'].append(invalid_manifest['changes'][0])
    elif invalid == 'wrong_name':
        invalid_manifest['changes'][0]['name'] = '错误姓名'
    else:
        target = manifest['changes'][0]
        other = next(row for row in invalid_manifest['expectedMembers'] if row['id'] != target['id'])
        other['name'] = target['name']
    with pytest.raises(ValueError):
        with factory.begin() as session:
            retirement.apply_retirement(session, invalid_manifest, apply=True)
    assert snapshot(factory) == manifest['expectedMembers']


def test_audit_failure_rolls_back_all_roles(retirement_env):
    factory, manifest = retirement_env
    engine = factory.kw['bind']
    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO domestic_member_audits'):
            raise RuntimeError('injected audit failure')
    event.listen(engine, 'before_cursor_execute', fail_audit)
    try:
        with pytest.raises(RuntimeError, match='audit failure'):
            with factory.begin() as session:
                retirement.apply_retirement(session, manifest, apply=True)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_audit)
    assert snapshot(factory) == manifest['expectedMembers']


def test_rerun_refuses_changed_completed_snapshot(retirement_env):
    factory, manifest = retirement_env
    with factory.begin() as session:
        retirement.apply_retirement(session, manifest, apply=True)
    with factory.begin() as session:
        session.get(UserRecord, UUID(manifest['changes'][0]['id'])).role = 'operator'
    with pytest.raises(ValueError, match='after the audited retirement'):
        with factory.begin() as session:
            retirement.apply_retirement(session, manifest, apply=True)


def test_postgresql_cli_export_dry_run_apply_and_repeat(retirement_env, tmp_path):
    factory, manifest = retirement_env
    engine = factory.kw['bind']
    if engine.dialect.name != 'postgresql':
        pytest.skip('Production CLI requires PostgreSQL')
    with factory() as session:
        schema = session.scalar(text('SELECT current_schema()'))
    url = engine.url.update_query_dict({'options': f'-csearch_path={schema}'})
    env = {**os.environ, 'RETIREMENT_TEST_DB': url.render_as_string(hide_password=False),
           'PYTHONIOENCODING': 'utf-8'}
    base = [sys.executable, str(script), '--backend-root', str(Path(__file__).resolve().parents[1]),
            '--database-url-env', 'RETIREMENT_TEST_DB']
    output = tmp_path / 'reviewed-members.json'
    def run(*args):
        result = subprocess.run([*base, *args], env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    assert run('--snapshot-output', str(output), '--actor-id', manifest['actorId'])['members'] == 25
    exported = json.loads(output.read_text(encoding='utf-8'))
    assert exported['expectedMembers'] == manifest['expectedMembers']
    exported['changes'] = manifest['changes']
    output.write_text(json.dumps(exported, ensure_ascii=False), encoding='utf-8')
    assert run('--manifest', str(output))['state'] == 'dry_run'
    assert snapshot(factory) == manifest['expectedMembers']
    assert run('--manifest', str(output), '--apply')['rolesAfter'] == {
        'super_admin': 2, 'operator': 17, 'designer': 6}
    assert run('--manifest', str(output), '--apply')['state'] == 'already_applied'
