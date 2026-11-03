"""Persisted leases survive a killed process; a new process fences the old one."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import UUID
from sqlalchemy import text
from app.db.timestamps import utcnow
from app.overseas.drafts import queue
from app.overseas.drafts.models import DraftImport
from test_overseas_draft_postgres import seed, add_job
from test_overseas_draft_reads_postgres import get, record
from test_overseas_members_postgres import pg_factory


CHILD = r'''
import json, os, sys, time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.overseas.drafts import queue
from app.overseas.tasks import models  # Register Material's Task foreign key.
mode, schema, report = sys.argv[1:]
engine = create_engine(os.environ['TEST_OVERSEAS_MEMBERS_DATABASE_URL'],
    connect_args={'options': '-c search_path=' + schema + ' -c statement_timeout=10000'})
factory = sessionmaker(engine, expire_on_commit=False)
job = queue.claim(factory)
assert job is not None
result = {'job': vars(job)}
if mode == 'recover':
    item = SimpleNamespace(id=uuid4(), bucket='test', object_key=uuid4().hex,
        content_type='application/pdf', size_bytes=3, checksum='a' * 64)
    result['accepted'] = queue.complete(factory, job, item)
temporary = Path(report + '.tmp')
temporary.write_text(json.dumps(result, default=str), encoding='utf-8')
temporary.replace(report)
if mode == 'claim':
    time.sleep(60)  # Parent kills this process after the durable claim is visible.
engine.dispose()
'''


def test_killed_worker_lease_recovered_by_new_process(pg_factory, tmp_path):
    actor_id, _ = seed(pg_factory)
    add_job(pg_factory, actor_id)
    with pg_factory() as session:
        schema = session.scalar(text('SELECT current_schema()'))
    assert schema.startswith('p18_') and schema[4:].isalnum()
    report = tmp_path / 'claimed.json'
    cwd = Path(__file__).resolve().parents[1]
    child = subprocess.Popen([sys.executable, '-c', CHILD, 'claim', schema, str(report)],
        cwd=cwd, env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = monotonic() + 10
        while not report.exists():
            assert child.poll() is None, 'claim process exited before reporting its durable lease'
            assert monotonic() < deadline, 'claim process did not report its durable lease'
            sleep(0.02)
        # Atomic report rename occurs only after claim committed in the child.
        child.terminate()
        child.communicate(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    assert child.returncode != 0
    old_data = json.loads(report.read_text(encoding='utf-8'))['job']
    for key in ('id', 'draft_id', 'epoch', 'owner_id', 'lease_token'):
        old_data[key] = UUID(old_data[key])
    old = SimpleNamespace(**old_data)
    with pg_factory.begin() as session:
        row = session.get(DraftImport, old.id)
        assert row.state == 'running' and row.lease_token == old.lease_token
        row.lease_until = utcnow() - timedelta(seconds=1)
    recovered = tmp_path / 'recovered.json'
    result = subprocess.run([sys.executable, '-c', CHILD, 'recover', schema, str(recovered)],
        cwd=cwd, env=os.environ.copy(), capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(recovered.read_text(encoding='utf-8'))
    assert outcome['accepted'] and outcome['job']['lease_token'] != str(old.lease_token)
    assert queue.complete(pg_factory, old, record()) is False
    current = get(pg_factory, actor_id)
    assert len(current['materials']) == 1 and current['imports'][0]['state'] == 'ready'
    with pg_factory() as session:
        assert session.get(DraftImport, old.id).attempts == 2
