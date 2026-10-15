"""Domestic durable records and Celery/broker queues must be idle twice."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('member_drain', Path(__file__).with_name('member-release-drain.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
m = d.m


def raw_evidence(work):
    native = d.native_probe(m.UNITS[0], d.PROBE.format(module='app.worker.celery_app', queues=['celery']), work)
    api = json.loads(m.run('docker', 'exec', m.container('domestic', 'api-image-worker'), 'python', '-c',
        d.PROBE.format(module='app.modules.api_image_edits.celery_app', queues=['api_image_edits']), capture=True))
    return dict(workers=dict(native=native, api=api), durable=m.r.pending(), variants=int(m.r.sql(d.VARIANTS)))


def evidence(work, timeout):
    command = [sys.executable, str(Path(__file__).resolve()), '--probe', str(work)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
        raise RuntimeError('Domestic drain probe timed out; no executor force-stop') from None
    if process.returncode:
        m.private(work / 'drain-probe.private.log', stderr)
        raise RuntimeError('Domestic drain probe failed; no executor force-stop')
    return json.loads(stdout)


def wait_empty(work, label, timeout=180):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Domestic work busy/unknown; no executor force-stop')
        result = evidence(work, remaining)
        empty = d.idle(result['workers']) and result['durable'] == result['variants'] == 0
        stable = stable + 1 if empty else 0
        m.private(work / (label + '.json'), result)
        if stable == 2:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Domestic work busy/unknown; intake stays closed, no executor force-stop')
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def stop(work, source, data):
    wait_empty(work, 'drained-before-outbox-stop')
    m.compose(data['domestic'], 'stop', '-t', '30', 'outbox', 'api-image-outbox')
    wait_empty(work, 'drained-after-outbox-stop')
    helper = source / 'scripts/release/image-inputs-worker.py'
    m.r.worker(helper, 'api-drain')
    assert m.r.pending() == int(m.r.sql(d.VARIANTS)) == 0
    m.r.worker(helper, 'native-stop')
    m.compose(data['domestic'], 'stop', '-t', '30', 'api-image-worker', 'image-variants')
    assert m.r.pending() == int(m.r.sql(d.VARIANTS)) == 0
    m.private(work / 'EXECUTORS_STOPPED', 'Domestic durable/Celery/broker/unacked idle twice before each stop phase')


if __name__ == '__main__':
    assert len(sys.argv) == 3 and sys.argv[1] == '--probe'
    print(json.dumps(raw_evidence(Path(sys.argv[2]))))
