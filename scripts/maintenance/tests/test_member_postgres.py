"""Real PostgreSQL locking, cross-schema FK coverage and UUID recovery."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import insert, text
from sqlalchemy.engine import make_url

from conftest import schema_tables, seed
from member_audit import audit
from member_catalog import Catalog, engine_for
from member_codec import read_json
from member_reconcile import reconcile
from member_restore import restore
from test_member_maintenance import approve, count


@pytest.fixture(params=['domestic', 'overseas'])
def pg_database(request):
    url = os.getenv('TEST_MEMBER_MAINTENANCE_DATABASE_URL')
    if not url:
        pytest.skip('explicit isolated PostgreSQL test URL required')
    parsed = make_url(url)
    if parsed.drivername != 'postgresql+psycopg' or not (parsed.database or '').endswith('_test'):
        pytest.fail('maintenance PostgreSQL tests require a *_test database')
    namespace = 'member_audit_' + uuid4().hex
    root = engine_for(url)
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{namespace}"'))
    engine = engine_for(parsed.update_query_dict({'options': f'-c search_path={namespace} -c statement_timeout=15000'}))
    tables = schema_tables(engine, request.param)
    try:
        yield engine, request.param, tables, namespace, root
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{namespace}" CASCADE'))
        root.dispose()


def test_postgres_delete_and_recovery_round_trip(pg_database, tmp_path):
    engine, business, tables, namespace, _root = pg_database
    seed(engine, tables, business)
    before = audit(engine, business, namespace)
    result = reconcile(engine, business, approve(before), schema=namespace,
                       apply=True, recovery_dir=tmp_path)
    assert result['results'][0]['outcome'] == 'deleted'
    bundle = read_json(result['results'][0]['recoveryFile'])
    assert restore(engine, business, bundle, schema=namespace, apply=True)['outcome'] == 'restored'
    assert audit(engine, business, namespace)['members'] == before['members']


@pytest.mark.parametrize('reference', ['roles', 'applications', 'archives'])
def test_postgres_lock_rechecks_reference_committed_while_waiting(pg_database, tmp_path, monkeypatch, reference):
    engine, business, tables, namespace, _root = pg_database
    identifier = seed(engine, tables, business)
    approval = approve(audit(engine, business, namespace))
    started = Event()
    original_lock = Catalog.lock
    def mark_lock(catalog):
        started.set()
        return original_lock(catalog)
    monkeypatch.setattr(Catalog, 'lock', mark_lock)
    values = {'id': uuid4()}
    if reference == 'roles':
        values.update(user_id=identifier, role='super_admin')
    elif reference == 'applications':
        values.update(corp_id='corp', provider_user_id=str(identifier), status='pending', version=1)
    else:
        values.update(created_by=identifier)
    with engine.connect() as writer, ThreadPoolExecutor(1) as pool:
        writer.execute(insert(tables[reference]).values(**values))
        future = pool.submit(reconcile, engine, business, approval, schema=namespace,
                             apply=True, recovery_dir=tmp_path)
        assert started.wait(5), 'cleanup never reached lock'
        writer.commit()
        result = future.result(timeout=15)
    assert result['results'][0]['outcome'] == 'skipped'
    assert count(engine, tables['member']) == count(engine, tables[reference]) == 1


def test_cross_schema_arbitrary_foreign_key_cannot_cascade(pg_database, tmp_path):
    engine, business, tables, namespace, root = pg_database
    identifier = seed(engine, tables, business)
    approval = approve(audit(engine, business, namespace))
    other = 'external_' + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{other}"'))
        connection.execute(text(f'CREATE TABLE "{other}".history (id uuid PRIMARY KEY, '
                                f'recipient uuid REFERENCES "{namespace}"."{tables["member"].name}" (id) ON DELETE CASCADE)'))
        connection.execute(text(f'INSERT INTO "{other}".history VALUES (:id, :person)'),
                           {'id': uuid4(), 'person': identifier})
    try:
        result = reconcile(engine, business, approval, schema=namespace, apply=True, recovery_dir=tmp_path)
        assert result['results'][0]['outcome'] == 'skipped'
        assert any(ref['table'] == other + '.history' for ref in result['results'][0]['references'])
        assert count(engine, tables['member']) == 1
    finally:
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{other}" CASCADE'))
