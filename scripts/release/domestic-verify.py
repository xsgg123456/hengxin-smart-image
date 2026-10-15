"""Read-only deletion worker readiness: schema scan and two successful empty loops."""
import importlib.util
import json
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('member_drain', Path(__file__).with_name('member-release-drain.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
m = d.m
UNIT = 'hengxin-domestic-deletions'
PROBE = '''import json
from sqlalchemy import select,text,func
from app.db.session import session_factory
from app.core.config import get_settings
from app.models import utcnow
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion as D
from app.storage.minio_store import get_store
assert not get_settings().cli_retention_enabled
assert get_settings().codex_execution_root == '/opt/hengxin-smart-image/infra/runtime/execution'
get_store()
with session_factory()() as s:
    s.execute(text("SET TRANSACTION READ ONLY"))
    assert s.scalar(text("SELECT version_num FROM alembic_version")) == '0029'
    assert s.scalar(select(func.count()).select_from(D)) == 0
    rows=s.scalars(select(D.task_id).where(D.status.in_(('deleting','delete_failed')),
        D.next_attempt_at <= utcnow()).order_by(D.next_attempt_at).limit(10)).all()
    assert not rows
print(json.dumps({'schema':'0029','receipts':0,'scan':'PASS'}))
'''


def deletion_ready(work, timeout=25):
    # Native read-only probe has its own strict 45s subprocess timeout and no worker mutation.
    result = d.native_probe(UNIT, PROBE, work)
    assert result == {'schema': '0029', 'receipts': 0, 'scan': 'PASS'}
    invocation = m.run('systemctl', 'show', UNIT, '-p', 'InvocationID', '--value', capture=True, timeout=5)
    assert invocation, 'Deletion worker invocation unavailable'
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'Deletion loop did not demonstrate readiness'
        body = m.run('journalctl', '--no-pager', '-o', 'cat', '_SYSTEMD_INVOCATION_ID=' + invocation,
                     capture=True, timeout=min(5, remaining))
        m.private(work / 'deletion-startup.private.log', body)
        assert 'unavailable' not in body and 'Traceback' not in body, 'Deletion worker failed its startup scan'
        completed = sum(line.strip() == '[]' for line in body.splitlines())
        if completed >= 2:
            assert m.run('systemctl', 'show', UNIT, '-p', 'InvocationID', '--value', capture=True, timeout=5) == invocation
            m.private(work / 'DELETIONS_READY', result)
            return
        time.sleep(min(2, max(0, deadline - time.monotonic())))
