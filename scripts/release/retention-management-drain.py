"""Drain current CLI, variants and API work; retain durable API retry handoff."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location('retry', Path(__file__).with_name('api-retry-deploy.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
m, r, probe = p.m, p.r, p.probe
n, handoff = m.module('retention-management-native'), m.module('api-simple-handoff')
CLI = """SELECT (SELECT count(*) FROM job_records WHERE status IS NULL OR
 status NOT IN ('succeeded','partial','failed','cancelled')) +
 (SELECT count(*) FROM api_edit_turns WHERE status IS NULL OR
 status NOT IN ('candidate','waiting_user','adopted','failed','cancelled'))"""


def native_probe(work, timeout):
    pid = m.run('systemctl', 'show', n.UNIT, '-p', 'MainPID', '--value', capture=True, timeout=min(5, timeout))
    assert int(pid) > 0
    proc = Path('/proc') / pid
    cwd = Path(os.readlink(proc / 'cwd'))
    env = dict(os.fsdecode(v).split('=', 1) for v in (proc / 'environ').read_bytes().split(b'\0') if v)
    env['PYTHONPATH'] = str(cwd)
    result = subprocess.run([str(cwd / '.venv/bin/python'), '-c',
        probe.PROBE.format(module='app.worker.celery_app', queues=['celery'])],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=max(.1, timeout - 5))
    if result.returncode:
        m.private(work / 'native-drain.private.log', result.stderr)
    assert result.returncode == 0, 'Native inspection failed; no force stop'
    return json.loads(result.stdout)


def wait_cli(work, timeout=1200):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'CLI/variants busy or unknown; no force stop'
        worker = native_probe(work, min(45, remaining))
        remaining = deadline - time.monotonic()
        assert remaining > 0
        db = p.DATABASE
        value = m.run('docker', 'exec', db[0], 'psql', '-v', 'ON_ERROR_STOP=1', '-U', db[1],
            '-d', db[2], '-Atc', 'SELECT (' + CLI + ') + (' + probe.VARIANTS + ')', capture=True, timeout=remaining)
        assert time.monotonic() <= deadline
        count = int(value)
        assert count >= 0
        stable = stable + 1 if count == 0 and probe.idle({'native': worker}) else 0
        m.private(work / 'native-drain.json', dict(worker=worker, pending=count, stable=stable))
        if stable == 2:
            return
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def stop(work, source, data):
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 't'
    # Pending cleanup/object receipts are durable; stop scanners before backing up, not by deleting their queues.
    for unit in (n.RETENTION, n.DELETE):
        assert n.snapshot(unit) == data['nativeSnapshots'][unit], 'Cleanup process drift'
        n.stop(unit)
    m.private(work / 'CLEANUP_STOPPED', 'Cleanup main processes exited with SIGTERM; pending receipts retained')
    p.graceful_stop('api-image-outbox')
    # CLI outbox may finish already accepted jobs before it is stopped.
    wait_cli(work)
    p.graceful_stop('outbox')
    wait_cli(work)
    handoff.wait_idle(work, p)
    n.stop(n.UNIT)
    p.graceful_stop('api-image-worker')
    p.graceful_stop('image-variants')
    assert handoff.safe(handoff.database(p)), 'API handoff changed after stop'
    assert r.sql(CLI) == '0' and r.sql(probe.VARIANTS) == '0'
    assert all(n.show(unit, 'MainPID') == '0' for unit in n.UNITS)
    m.private(work / 'EXECUTORS_STOPPED', 'CLI/broker/variants drained; API durable handoff proven; cleanup stopped')
