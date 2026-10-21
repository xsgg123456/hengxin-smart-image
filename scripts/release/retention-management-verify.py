"""Verify empty observation origin and a real completed, fresh first cleanup scan."""
import importlib.util
import json
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('retention_runtime', Path(__file__).with_name('retention-management-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
m, r, n = s.m, s.r, s.n
ADDED = {'cli_retention_records', 'cli_retention_object_links', 'cli_retention_runs',
         'cli_retention_service', 'cli_retention_totals'}
OBSERVE = """SELECT json_build_object(
 'heartbeatFresh',coalesce((SELECT heartbeat_at >= now()-interval '120 seconds'
     AND heartbeat_at >= {started}::timestamptz FROM cli_retention_service WHERE id='api_cli'),false),
 'scan', (SELECT json_build_object('id',id,'status',status,'startedAt',started_at,'finishedAt',finished_at)
     FROM cli_retention_runs WHERE started_at >= {started}::timestamptz ORDER BY started_at DESC LIMIT 1),
 'records',(SELECT count(*) FROM cli_retention_records))"""


def migrated():
    for name in ADDED - {'cli_retention_totals'}:
        assert r.sql('SELECT count(*) FROM ' + name) == '0', 'Migration fabricated cleanup observations'
    assert r.sql("SELECT count(*) FROM cli_retention_totals") == '1'


def frontend(source):
    assert (m.APP / 'frontend/package.json').read_bytes() == (source / 'frontend/package.json').read_bytes()
    for origin in ('http://127.0.0.1:18080', r.ORIGIN):
        actual = m.run('curl', '--max-time', '15', '-fsS', origin + '/', capture=True)
        assert actual == (source / 'frontend/dist/index.html').read_text().strip()
    m.run('curl', '--max-time', '15', '--retry', '10', '--retry-delay', '2', '--retry-connrefused',
          '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18008/api/v1/health/ready')
    for path in ('summary', 'records', 'records/00000000-0000-0000-0000-000000000000'):
        status = m.run('curl', '--max-time', '15', '-sS', '-o', '/dev/null', '-w', '%{http_code}',
            'http://127.0.0.1:18008/api/v1/management/retention/' + path, capture=True)
        assert status == '401', 'Management route missing or unauthenticated access allowed'


def mark_start(work):
    # Server database clock avoids comparison with a workstation's timezone/skew.
    m.private(work / 'cleanup-start.json', r.sql('SELECT to_json(now())'))


def observation_sql(started):
    from datetime import datetime
    assert isinstance(started, str)
    value = datetime.fromisoformat(started)
    assert value.tzinfo is not None
    return OBSERVE.format(started="'" + value.isoformat() + "'")


def completed(row):
    assert isinstance(row, dict) and set(row) == {'heartbeatFresh', 'scan', 'records'}
    assert type(row['heartbeatFresh']) is bool and type(row['records']) is int and row['records'] >= 0
    scan = row['scan']
    if scan is None:
        return False
    assert isinstance(scan, dict) and set(scan) == {'id', 'status', 'startedAt', 'finishedAt'}
    assert scan['status'] in ('running', 'completed', 'failed'), 'Unknown cleanup state'
    assert scan['status'] != 'failed', 'First cleanup scan failed'
    if scan['status'] != 'completed':
        return False
    assert scan['finishedAt'] and scan['startedAt'] and scan['id'], 'Incomplete persistent scan receipt'
    return row['heartbeatFresh']


def first_scan(work, timeout=240):
    query = observation_sql(json.loads((work / 'cleanup-start.json').read_text()))
    invocations = {unit: n.show(unit, 'InvocationID') for unit in (n.DELETE, n.RETENTION)}
    assert all(invocations.values())
    db = s.p.DATABASE
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'No fresh persisted first scan; keep intake closed'
        row = json.loads(m.run('docker', 'exec', db[0], 'psql', '-v', 'ON_ERROR_STOP=1',
            '-U', db[1], '-d', db[2], '-Atc', query, capture=True, timeout=min(10, remaining)))
        m.private(work / 'cleanup-first-scan.json', row)
        if completed(row):
            break
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    for unit, invocation in invocations.items():
        assert n.show(unit, 'InvocationID') == invocation, 'Cleanup restarted during startup'
        m.run('systemctl', 'is-active', unit, capture=True)
    m.private(work / 'CLEANUP_READY', 'First real persisted scan completed with fresh heartbeat; counts are observed, not fabricated')
