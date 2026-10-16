"""Prove all queues and deletion work idle before stopping old schema consumers."""
import importlib.util
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('domestic_drain', Path(__file__).with_name('domestic-drain.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
m = d.m
n = m.module('retirement-native')
CLEANUP = """SELECT (SELECT count(*) FROM api_task_deletions WHERE status != 'deleted')
 + (SELECT count(*) FROM cli_retention_objects)
 + (SELECT count(*) FROM cli_retention WHERE status NOT IN ('active','expired'))"""


def cleanup_idle(timeout=180):
    deadline = time.monotonic() + timeout
    stable = 0
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'Deletion/retention pending; no process force-stop'
        value = m.run('docker', 'exec', m.r.PREFIX + 'postgres-1', 'psql', '-v', 'ON_ERROR_STOP=1',
                      '-U', 'hengxin', '-d', 'hengxin', '-Atc', CLEANUP, capture=True, timeout=remaining)
        stable = stable + 1 if value == '0' else 0
        if stable == 2:
            return
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def stop(work, source, data):
    # API admission has stopped. Leave cleanup running until durable work has settled.
    d.wait_empty(work, 'drained-before-cleanup-stop')
    cleanup_idle()
    for unit in (n.RETENTION, n.DELETE):
        assert n.snapshot(unit) == data['nativeProcesses'][unit], 'Cleanup process drift'
        # Disable systemd's escalation for this one stop; unknown work must never be SIGKILLed.
        m.run('systemctl', 'kill', '--kill-whom=main', '--signal=SIGTERM', unit)
        deadline = time.monotonic() + 30
        while n.show(unit, 'MainPID') != '0':
            assert time.monotonic() < deadline, 'Cleanup did not exit gracefully'
            time.sleep(0.5)
    cleanup_idle()
    d.stop(work, source, data)
    for unit in n.UNITS:
        assert n.show(unit, 'MainPID') == '0'
    assert m.r.pending() == 0
    cleanup_idle()
    m.private(work / 'CLEANUP_STOPPED', 'All three old native processes exited; no pending deletion or retention')
