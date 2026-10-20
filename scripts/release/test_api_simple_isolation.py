"""Opt-in real PostgreSQL evidence queries, scoped to a disposable local container."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('HX_API_SIMPLE_DOCKER_TEST') != '1',
                               reason='opt-in isolated local Docker')
spec = importlib.util.spec_from_file_location('handoff_pg', Path(__file__).with_name('api-simple-handoff.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def run(*args):
    return subprocess.check_output(args, text=True, encoding='utf-8', stderr=subprocess.STDOUT, timeout=30).strip()


@pytest.fixture(scope='module')
def isolated_pg():
    name = 'hx-api-simple-pg-' + uuid4().hex[:12]
    created = False
    try:
        run('docker', 'run', '-d', '--network', 'none', '--name', name,
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17')
        created = True
        deadline = time.monotonic() + 30
        while True:
            try:
                run('docker', 'exec', name, 'pg_isready', '-U', 'postgres')
                break
            except subprocess.CalledProcessError:
                assert time.monotonic() < deadline
                time.sleep(0.2)
        def sql(query):
            return run('docker', 'exec', name, 'psql', '-U', 'postgres', '-d', 'postgres',
                       '-v', 'ON_ERROR_STOP=1', '-Atc', query)
        sql("""
            CREATE TABLE api_image_channel(id int, paused bool, item_id uuid, token uuid, lease_until timestamptz);
            CREATE TABLE api_image_items(id uuid, state text, lease_token uuid, lease_until timestamptz,
                                         result_url text, result_bytes bytea);
            CREATE TABLE api_image_attempts(id uuid, item_id uuid, state text, completed_at timestamptz);
            CREATE TABLE api_image_tasks(id uuid, state text);
            CREATE TABLE api_edit_turns(id uuid, status text);
            CREATE TABLE api_image_versions(id uuid, item_id uuid, file_id uuid);
            CREATE TABLE api_image_files(id uuid, checksum text);
        """)
        yield sql
    finally:
        if created:
            run('docker', 'rm', '-f', '-v', name)


@pytest.fixture
def database(isolated_pg):
    isolated_pg("""
        TRUNCATE api_image_channel,api_image_items,api_image_attempts,api_image_tasks,api_edit_turns,
                 api_image_versions,api_image_files;
        INSERT INTO api_image_channel(id,paused) VALUES (1,true);
    """)
    return isolated_pg


ITEM = "'00000000-0000-0000-0000-000000000001'"
TOKEN = "'00000000-0000-0000-0000-000000000002'"


@pytest.mark.parametrize('state,token,lease,receipt,allowed', [
    ('queued', 'NULL', 'NULL', 'NULL', True),
    ('retry_wait', 'NULL', 'NULL', 'NULL', True),
    ('collecting', 'NULL', 'NULL', "'private-receipt'", True),
    ('collecting', 'NULL', 'NULL', "''", False),
    ('collecting', 'NULL', 'NULL', 'NULL', False),
    ('uncertain', TOKEN, "now()-interval '2 hours'", 'NULL', True),
    ('uncertain', TOKEN, "now()+interval '1 hour'", 'NULL', False),
    ('uncertain', TOKEN, 'NULL', 'NULL', False),
    ('uncertain', 'NULL', "now()-interval '1 hour'", 'NULL', False),
    ('uncertain', 'NULL', 'NULL', 'NULL', False),
    ('queued', TOKEN, "now()+interval '1 hour'", 'NULL', False),
    ('queued', TOKEN, 'NULL', 'NULL', False),
    ('retry_wait', 'NULL', "now()-interval '1 hour'", 'NULL', False),
    ('running', 'NULL', 'NULL', 'NULL', False),
    ('unrecognized', 'NULL', 'NULL', 'NULL', False),
])
def test_real_item_and_lease_boundaries(database, state, token, lease, receipt, allowed):
    database(f"INSERT INTO api_image_items VALUES ({ITEM},'{state}',{token},{lease},{receipt},NULL)")
    before = database('SELECT row_to_json(t) FROM api_image_items t')
    assert h.safe(json.loads(database(h.EVIDENCE))) is allowed
    assert database('SELECT row_to_json(t) FROM api_image_items t') == before


@pytest.mark.parametrize('state,completed,allowed', [
    ('running', 'NULL', False), ('running', 'now()', False),
    ('uncertain', 'NULL', False), ('uncertain', 'now()', True),
    ('retryable', 'now()', True), ('permanent', 'now()', True),
    ('succeeded', 'now()', True), ('unknown', 'now()', False),
])
def test_expired_uncertain_requires_all_attempts_finished(database, state, completed, allowed):
    database(f"INSERT INTO api_image_items VALUES ({ITEM},'uncertain',{TOKEN},now()-interval '2 hours',NULL,NULL)")
    database(f"INSERT INTO api_image_attempts VALUES ({TOKEN},{ITEM},'{state}',{completed})")
    assert h.safe(json.loads(database(h.EVIDENCE))) is allowed


@pytest.mark.parametrize('status,allowed', [
    ('queued', False), ('running', False), ('cancelling', False), ('uncertain', False),
    ('unknown', False), ('candidate', True), ('waiting_user', True), ('adopted', True),
    ('failed', True), ('cancelled', True),
])
def test_native_cli_activity_and_unknown_states_block(database, status, allowed):
    database(f"INSERT INTO api_edit_turns VALUES ({ITEM},'{status}')")
    assert h.safe(json.loads(database(h.EVIDENCE))) is allowed


@pytest.mark.parametrize('assignment', [
    f'item_id={ITEM}', f'token={TOKEN}', "lease_until=now()-interval '2 hours'",
])
def test_any_channel_reservation_blocks(database, assignment):
    database('UPDATE api_image_channel SET ' + assignment)
    assert not h.safe(json.loads(database(h.EVIDENCE)))


@pytest.mark.parametrize('statement', [
    'UPDATE api_image_channel SET paused=false',
    'DELETE FROM api_image_channel',
])
def test_channel_pause_must_exist_and_be_true(database, statement):
    database(statement)
    with pytest.raises(AssertionError, match='not paused'):
        h.safe(json.loads(database(h.EVIDENCE)))


@pytest.mark.parametrize('statement', [
    f"INSERT INTO api_image_attempts VALUES ({TOKEN},{ITEM},NULL,now())",
    f"INSERT INTO api_edit_turns VALUES ({ITEM},NULL)",
    f"INSERT INTO api_image_tasks VALUES ({ITEM},NULL)",
])
def test_null_state_is_unknown_work(database, statement):
    database(statement)
    assert not h.safe(json.loads(database(h.EVIDENCE)))


def test_binary_receipt_and_unknown_task_state(database):
    database(f"INSERT INTO api_image_items VALUES ({ITEM},'collecting',NULL,NULL,NULL,decode('aa','hex'))")
    assert h.safe(json.loads(database(h.EVIDENCE)))
    database(f"INSERT INTO api_image_tasks VALUES ({TOKEN},'unrecognized')")
    assert not h.safe(json.loads(database(h.EVIDENCE)))


def test_real_completed_evidence_hashes_allow_new_rows_but_reject_changes(database):
    runtime = SimpleNamespace(DATABASE=None, b=SimpleNamespace(query=lambda _, query: database(query)))
    database(f"""
        INSERT INTO api_image_items VALUES ({ITEM},'succeeded',NULL,NULL,NULL,NULL);
        INSERT INTO api_image_attempts VALUES ({TOKEN},{ITEM},'succeeded',now());
        INSERT INTO api_image_versions VALUES ({ITEM},{ITEM},{TOKEN});
        INSERT INTO api_image_files VALUES ({TOKEN},'original');
    """)
    before = h.protected(runtime)
    assert all(before[table] for table in h.PROTECTED)
    database(f"INSERT INTO api_image_items VALUES ({TOKEN},'succeeded',NULL,NULL,NULL,NULL)")
    h.verify_protected(runtime, before)
    database("UPDATE api_image_files SET checksum='changed'")
    with pytest.raises(AssertionError, match='completed API evidence'):
        h.verify_protected(runtime, before)
