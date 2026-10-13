"""Read-only queue evidence before shutting down confirmed-idle execution services."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PROBE = '''import json
from {module} import celery_app as c
i=c.control.inspect(timeout=5)
states=[i.active(),i.reserved(),i.scheduled()]
queues=i.active_queues()
names={queues!r}
assert all(isinstance(s,dict) and len(s)==1 and all(isinstance(v,list) for v in s.values()) for s in states)
assert isinstance(queues,dict) and len(queues)==1 and all(set(s)==set(queues) for s in states)
assert [q['name'] for q in next(iter(queues.values()))]==names
with c.connection_for_read() as connection:
    channel=connection.channel()
    counts={{q:sum(channel.client.llen(channel._q_for_pri(q,p)) for p in channel.priority_steps) for q in names}}
    unacked=channel.client.hlen(channel.unacked_key)
print(json.dumps({{'states':states,'queues':counts,'unacked':unacked}}))
'''

VARIANTS = """SELECT
 (SELECT count(*) FROM image_variants WHERE NOT completed OR token IS NOT NULL OR lease_until IS NOT NULL)
 +(SELECT count(*) FROM files f WHERE status='ready' AND deleted_at IS NULL AND NOT EXISTS
   (SELECT 1 FROM image_variants v WHERE v.domain='originals' AND v.file_id=f.id))
 +(SELECT count(*) FROM api_image_files f WHERE status='ready' AND deleted_at IS NULL AND NOT EXISTS
   (SELECT 1 FROM image_variants v WHERE v.domain='api-image-edits' AND v.file_id=f.id))"""


def native_probe(unit, code, diagnostics=None):
    pid = int(m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
    assert pid > 0, 'Native worker PID unavailable'
    cwd = Path(os.readlink(f'/proc/{pid}/cwd'))
    configured = m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True)
    assert cwd == Path(configured), 'Native running/configured directory differs'
    env = dict(os.fsdecode(v).split('=', 1) for v in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if v)
    env['PYTHONPATH'] = str(cwd)
    result = subprocess.run([str(cwd / '.venv/bin/python'), '-c', code], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=45)
    if result.returncode and diagnostics is not None:
        m.private(diagnostics / (unit + '-probe.private.log'), result.stderr)
    assert result.returncode == 0, 'Worker probe failed; inspect private runtime, no force stop'
    return json.loads(result.stdout)


def worker_evidence(work=None):
    domestic = native_probe(m.UNITS[0], PROBE.format(module='app.worker.celery_app', queues=['celery']), work)
    overseas = native_probe(m.UNITS[1], PROBE.format(module='app.overseas.execution.worker', queues=['overseas.cli']), work)
    api = json.loads(m.run('docker', 'exec', m.container('domestic', 'api-image-worker'), 'python', '-c',
        PROBE.format(module='app.modules.api_image_edits.celery_app', queues=['api_image_edits']), capture=True))
    return dict(domestic=domestic, overseas=overseas, api=api)


def idle(evidence):
    for value in evidence.values():
        states = value['states']
        assert len(states) == 3 and all(isinstance(s, dict) and len(s) == 1 for s in states)
        assert all(isinstance(tasks, list) for state in states for tasks in state.values())
        assert value['queues'] and all(isinstance(n, int) and n >= 0 for n in value['queues'].values())
        assert isinstance(value['unacked'], int) and value['unacked'] >= 0
        if any(tasks for state in states for tasks in state.values()):
            return False
        if any(value['queues'].values()) or value['unacked']:
            return False
    return True


def evidence(work=None):
    workers = worker_evidence(work)
    return dict(workers=workers, domestic=m.r.pending(), overseas=m.u.pending(),
                variants=int(m.r.sql(VARIANTS)))


def wait_empty(work, label, timeout=180):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        result = evidence(work)
        empty = idle(result['workers']) and all(result[k] == 0 for k in ('domestic', 'overseas', 'variants'))
        stable = stable + 1 if empty else 0
        if stable == 2:
            m.private(work / (label + '.json'), result)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Work not drained; intake stays closed and executors remain running')
        time.sleep(3)


def drain_and_stop(work, source, data):
    # Outboxes continue dispatching already admitted jobs until durable work AND broker are empty.
    wait_empty(work, 'drained-before-outbox-stop')
    m.compose(data['domestic'], 'stop', '-t', '30', 'outbox', 'api-image-outbox')
    m.run('systemctl', 'stop', m.UNITS[2])
    # Publications racing the first check must be consumed before any executor is stopped.
    wait_empty(work, 'drained-after-outbox-stop')
    helper = source / 'scripts/release/image-inputs-worker.py'
    m.r.worker(helper, 'api-drain')
    m.u.drain()
    assert m.r.pending() == m.u.pending() == int(m.r.sql(VARIANTS)) == 0
    m.r.worker(helper, 'native-stop')
    m.run('systemctl', 'stop', m.UNITS[1])
    m.compose(data['domestic'], 'stop', '-t', '30', 'api-image-worker', 'image-variants')
    assert m.r.pending() == m.u.pending() == int(m.r.sql(VARIANTS)) == 0
    m.private(work / 'EXECUTORS_STOPPED', 'Two stable queue/DB checks; no force-stop of unknown work')
