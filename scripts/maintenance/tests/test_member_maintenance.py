import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, ForeignKey, JSON, String, Table, Uuid, event, insert, select, update

from conftest import seed
from member_audit import audit
from member_catalog import Catalog, transaction
from member_codec import SafetyError, read_json
from member_reconcile import reconcile
from member_restore import restore


def approve(report, member=None):
    return {'formatVersion': 1, 'business': report['business'], 'sourceFingerprint': report['sourceFingerprint'],
            'reviewedBy': '测试审核者', 'reason': '隔离测试确认空壳',
            'members': [{'id': item['id'], 'expected': item['expected']} for item in report['members']
                        if member is None or item['id'].replace('-', '') == member.hex]}


def count(engine, table):
    with engine.connect() as connection:
        return len(connection.execute(select(table)).all())


def test_audit_and_default_reconcile_are_read_only(database):
    engine, business, tables = database
    seed(engine, tables, business)
    writes = []
    def observe(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.strip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'}:
            writes.append(statement)
    event.listen(engine, 'before_cursor_execute', observe)
    report = audit(engine, business)
    result = reconcile(engine, business, approve(report))
    assert result['results'][0]['outcome'] == 'would_delete'
    assert result['results'][0]['recoveryPreview']['member']['status'] == 'pending'
    assert report['counts'] == {'total': 1, 'cleanupCandidates': 1, 'enrolled': 0, 'legacy': 1, 'applications': 0}
    assert writes == []
    assert count(engine, tables['member']) == 1


def test_empty_shell_delete_repeat_restore_full_round_trip(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    before = audit(engine, business)
    approved = approve(before)
    result = reconcile(engine, business, approved, apply=True, recovery_dir=tmp_path / 'recovery')
    assert result['results'][0]['outcome'] == 'deleted'
    assert count(engine, tables['member']) == 0
    if business == 'domestic':
        assert count(engine, tables['identities']) == 0
    bundle = read_json(result['results'][0]['recoveryFile'])
    assert 'token' not in json.dumps(bundle)
    assert reconcile(engine, business, approved, apply=True, recovery_dir=tmp_path)['results'][0]['outcome'] == 'already_absent'
    assert restore(engine, business, bundle)['outcome'] == 'would_restore'
    assert count(engine, tables['member']) == 0
    assert restore(engine, business, bundle, apply=True)['outcome'] == 'restored'
    assert restore(engine, business, bundle, apply=True)['outcome'] == 'already_restored'
    assert audit(engine, business)['members'] == before['members']


@pytest.mark.parametrize('reference', ['roles', 'sessions', 'applications', 'history', 'archives'])
def test_new_reference_after_approval_is_kept_and_no_credentials_exported(database, tmp_path, reference):
    engine, business, tables = database
    member_id = seed(engine, tables, business)
    approved = approve(audit(engine, business))
    values = {'id': uuid4()}
    if reference == 'roles':
        values.update(user_id=member_id, role='super_admin')
    elif reference == 'sessions':
        values.update(user_id=member_id, token_hash='never-export-secret', identity_session_id='never-export-session')
    elif reference == 'applications':
        values.update(corp_id='corp', provider_user_id=str(member_id), status='rejected', version=1)
    elif reference == 'history':
        values.update(recipient=member_id)
    else:
        values.update(created_by=member_id)
    with engine.begin() as connection:
        connection.execute(insert(tables[reference]).values(**values))
    report = audit(engine, business)
    assert report['members'][0]['cleanupEligible'] is False
    assert 'never-export' not in json.dumps(report)
    result = reconcile(engine, business, approved, apply=True, recovery_dir=tmp_path / 'recovery')
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, tables['member']) == count(engine, tables[reference]) == 1
    assert not (tmp_path / 'recovery').exists()


@pytest.mark.parametrize('change', ['name', 'status', 'directory_state', 'identity', 'version'])
def test_changed_expected_state_is_skipped(database, tmp_path, change):
    engine, business, tables = database
    seed(engine, tables, business)
    approved = approve(audit(engine, business))
    with engine.begin() as connection:
        if change == 'identity':
            table = tables.get('identities', tables['member'])
            connection.execute(update(table).values(provider_user_id='changed'))
        elif change == 'version':
            if business == 'domestic':
                connection.execute(update(tables['member']).values(role='super_admin'))
            else:
                connection.execute(update(tables['member']).values(version=2))
        else:
            value = {'name': '姓名改变', 'status': 'active', 'directory_state': 'enrolled'}[change]
            connection.execute(update(tables['member']).values(**{change: value}))
    result = reconcile(engine, business, approved, apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['reasons'] == ['expected_snapshot_changed']
    assert count(engine, tables['member']) == 1


def test_approved_and_disabled_members_never_candidates(database):
    engine, business, tables = database
    seed(engine, tables, business, status='active', directory_state='enrolled')
    seed(engine, tables, business, status='disabled', directory_state='enrolled')
    assert audit(engine, business)['counts']['cleanupCandidates'] == 0


def test_identity_mapping_incoming_fk_blocks_cascade(database, tmp_path):
    engine, business, tables = database
    if business != 'domestic':
        pytest.skip('only domestic has a separate identity table')
    seed(engine, tables, business)
    approved = approve(audit(engine, business))
    metadata = tables['identities'].metadata
    extra = Table('identity_history', metadata, Column('id', Uuid, primary_key=True),
                  Column('binding_id', Uuid, ForeignKey('user_identities.id', ondelete='CASCADE')))
    extra.create(engine)
    with engine.begin() as connection:
        identity = connection.scalar(select(tables['identities'].c.id))
        connection.execute(insert(extra).values(id=uuid4(), binding_id=identity))
    result = reconcile(engine, business, approved, apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, extra) == 1


def test_apply_requires_recovery_and_approval_expected_fields(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    approval = approve(audit(engine, business))
    with pytest.raises(SafetyError, match='recovery_directory_required'):
        reconcile(engine, business, approval, apply=True)
    del approval['members'][0]['expected']['version']
    with pytest.raises(SafetyError, match='complete_expected_snapshot_required'):
        reconcile(engine, business, approval, apply=True, recovery_dir=tmp_path)


def test_recovery_io_failure_rolls_back(database, tmp_path, monkeypatch):
    import member_reconcile
    engine, business, tables = database
    seed(engine, tables, business)
    approval = approve(audit(engine, business))
    def fail(*_args, **_kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(member_reconcile, 'write_json', fail)
    with pytest.raises(OSError):
        reconcile(engine, business, approval, apply=True, recovery_dir=tmp_path)
    assert count(engine, tables['member']) == 1


def test_same_name_and_other_business_do_not_determine_membership(database):
    engine, business, tables = database
    first = seed(engine, tables, business)
    second = seed(engine, tables, business, status='active', directory_state='enrolled')
    report = audit(engine, business)
    by_id = {item['id'].replace('-', ''): item for item in report['members']}
    assert by_id[first.hex]['cleanupEligible']
    assert not by_id[second.hex]['cleanupEligible']


def test_restore_detects_tampered_bundle_and_existing_changes(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    result = reconcile(engine, business, approve(audit(engine, business)), apply=True, recovery_dir=tmp_path)
    bundle = read_json(result['results'][0]['recoveryFile'])
    restore(engine, business, bundle, apply=True)
    with engine.begin() as connection:
        connection.execute(update(tables['member']).values(name='新资料'))
    assert restore(engine, business, bundle, apply=True)['outcome'] == 'skipped_existing_changed'
    bundle['reason'] = 'changed'
    with pytest.raises(SafetyError, match='recovery_integrity_failure'):
        restore(engine, business, bundle, apply=True)


def test_read_transaction_enforces_no_writes(database):
    from sqlalchemy.exc import DBAPIError
    engine, business, tables = database
    with pytest.raises(DBAPIError):
        with transaction(engine) as connection:
            connection.execute(insert(tables['member']).values(id=uuid4()))


def test_missing_application_migration_reports_but_refuses_cleanup(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    tables['applications'].drop(engine)
    report = audit(engine, business)
    assert report['members'][0]['skipReasons'] == ['isolation_migration_required']
    result = reconcile(engine, business, approve(report), apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, tables['member']) == 1


def test_member_credentials_are_never_exported_or_deleted(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE "{tables["member"].name}" ADD COLUMN password_hash VARCHAR')
        connection.exec_driver_sql(f'UPDATE "{tables["member"].name}" SET password_hash = ?', ('do-not-export',))
    report = audit(engine, business)
    assert 'do-not-export' not in json.dumps(report)
    assert 'unsafe_recovery_schema' in report['members'][0]['skipReasons']
    result = reconcile(engine, business, approve(report), apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, tables['member']) == 1


def test_audit_history_is_retained_without_exporting_arbitrary_payload(database, tmp_path):
    engine, business, tables = database
    member_id = seed(engine, tables, business)
    table = Table(('overseas_' if business == 'overseas' else '') + 'member_audit', tables['member'].metadata,
        Column('id', Uuid, primary_key=True),
        Column('member_id', Uuid, ForeignKey(tables['member'].name + '.id')),
        Column('action', String), Column('before', JSON))
    table.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(table).values(id=uuid4(), member_id=member_id, action='grant_role',
                                               before={'token': 'not-exported'}))
    report = audit(engine, business)
    assert 'not-exported' not in json.dumps(report)
    summaries = [ref['auditEntries'] for ref in report['members'][0]['references'] if 'auditEntries' in ref]
    assert summaries[0][0]['action'] == 'grant_role'
    result = reconcile(engine, business, approve(report), apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, table) == 1


def test_nested_recovery_credentials_are_refused():
    from member_codec import safe_rows
    with pytest.raises(SafetyError, match='credential_column_in_recovery_table'):
        safe_rows([{'id': 'member', 'profile': {'nested': [{'access_token': 'never-export'}]}}])
