"""Observe the new cleanup service invocations completing their real startup scans."""
import importlib.util
import json
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('retirement_native', Path(__file__).with_name('retirement-native.py'))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
m = n.m


def completed(body, deletion):
    assert 'Traceback' not in body, 'Cleanup startup traceback'
    results = []
    for line in body.splitlines():
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            assert result.get('status') not in ('unavailable', 'disabled', 'unsupported_database'), 'Cleanup unavailable'
        results.append(result)
    if deletion:
        return sum(result == [] for result in results) >= 2
    scans = [result for result in results if isinstance(result, dict) and result.get('status') == 'completed']
    for scan in scans:
        assert isinstance(scan.get('resources'), list) and isinstance(scan.get('objectsRemoved'), int)
        assert all(row.get('status') != 'retry' for row in scan['resources']), 'Retention startup retry'
    return bool(scans)


def cleanup_ready(work, timeout=45):
    units = (n.DELETE, n.RETENTION)
    invocations = {unit: n.show(unit, 'InvocationID') for unit in units}
    assert all(invocations.values()), 'Cleanup invocation missing'
    deadline = time.monotonic() + timeout
    ready = set()
    while len(ready) != len(units):
        for unit in units:
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'Cleanup startup scan deadline exceeded'
            body = m.run('journalctl', '--no-pager', '-o', 'cat',
                         '_SYSTEMD_INVOCATION_ID=' + invocations[unit], capture=True, timeout=min(5, remaining))
            m.private(work / (unit + '-startup.private.log'), body)
            if completed(body, unit == n.DELETE):
                ready.add(unit)
        if len(ready) != len(units):
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    for unit in units:
        assert n.show(unit, 'InvocationID') == invocations[unit], 'Cleanup restarted during verification'
        m.run('systemctl', 'is-active', unit, capture=True)
    m.private(work / 'CLEANUP_READY', 'Two empty deletion loops and successful retention scan in new invocations')
