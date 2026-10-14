"""Native-only dual-business CLI cutover. No schema, image or frontend changes."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


p = module('overseas-codex-prepare')
h = module('overseas-hotfix-deploy')
m, u, r = h.m, h.u, h.r
WORK = p.WORK
UNITS = ('hengxin-vps-codex-worker', 'hengxin-overseas-worker', 'hengxin-overseas-outbox')
APIS = ('hengxin-vps-staging-api-1', 'hengxin-overseas-api-1')
OUTBOX = 'hengxin-vps-staging-outbox-1'
DROP = '95-codex-astra.conf'


def closed_config(original):
    changed, count = re.subn(r'location \^~ /api/overseas/v1/ \{[^{}]*\}',
                            'location ^~ /api/overseas/v1/ { return 503; }', original)
    assert count == 1
    pattern = r'location \^~ /api/v1/ \{[^{}]*\}'
    if re.search(pattern, changed):
        changed, count = re.subn(pattern, 'location ^~ /api/v1/ { return 503; }', changed)
        assert count == 1
    else:
        anchor = '    ssl_prefer_server_ciphers off;\n'
        assert changed.count(anchor) == 1
        changed = changed.replace(anchor, anchor + '    location ^~ /api/v1/ { return 503; }\n')
    return changed


def closed():
    for path in ('/api/v1/auth/me', '/api/overseas/v1/auth/me'):
        assert h.verify.status(r.ORIGIN + path) == '503', 'Admission not closed'


def idle_evidence():
    workers = {kind: h.drain.native_probe(unit, h.drain.PROBE.format(module=mod, queues=[queue]), WORK)
        for kind, unit, mod, queue in (
            ('domestic', UNITS[0], 'app.worker.celery_app', 'celery'),
            ('overseas', UNITS[1], 'app.overseas.execution.worker', 'overseas.cli'))}
    return dict(workers=workers, domestic=r.pending(), overseas=u.pending(),
                deleting=int(u.sql(h.DELETING)))


def wait_idle(label, timeout=300):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        result = idle_evidence()
        m.private(WORK / (label + '.json'), result)
        empty = h.drain.idle(result['workers']) and all(result[k] == 0 for k in ('domestic', 'overseas', 'deleting'))
        stable = stable + 1 if empty else 0
        if stable == 2:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Work not drained; intake stays closed, no forced termination')
        time.sleep(3)


def dropin(unit, target):
    prefix = 'OVERSEAS_' if 'overseas' in unit else ''
    content = ('[Service]\nEnvironmentFile=' + str(WORK / (prefix.lower() + 'runtime.env')) + '\n')
    if prefix:
        command = (str(target / '.venv/bin/celery') + ' -A app.overseas.execution.worker:celery_app worker '
                   '--pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
                   if unit.endswith('worker') else str(target / '.venv/bin/python') + ' -m app.overseas.execution.outbox')
        content += 'WorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + command + '\n'
    return content


def runtime(unit):
    code = '''import json,subprocess
from app.core.config import get_settings
s=get_settings()
value=dict(binary=s.codex_binary,pinned=s.codex_version,
 actual=subprocess.check_output([s.codex_binary,'--version'],text=True,timeout=15).strip())
if 'overseas' in s.codex_execution_root:
 from app.overseas.studio.execution import StudioProtocol
 from types import SimpleNamespace
 value['new']=StudioProtocol().arguments(SimpleNamespace(previous_session=None))
 value['resume']=StudioProtocol().arguments(SimpleNamespace(previous_session='original-session'))
print(json.dumps(value))
'''
    return h.drain.native_probe(unit, code, WORK)


def validate():
    data = json.loads((WORK / 'prepared.json').read_text())
    assert p.tree(p.TARGET) == data['files'] and p.tree(p.RUNTIME) == data['runtime_files']
    assert p.tree(Path(data['old'])) == data['baseline'], 'Native baseline drift'
    for unit in UNITS:
        m.run('systemctl', 'is-active', unit)
        path = Path('/etc/systemd/system') / (unit + '.service.d') / DROP
        assert not path.exists(), 'Existing override requires inspection'
    assert m.run('systemctl', 'show', UNITS[1], '-p', 'WorkingDirectory', '--value', capture=True) == data['old']
    smoke = json.loads((WORK / 'smoke-pass.json').read_text())
    assert smoke['source_hash'] == p.digest(p.TARGET / p.MODULE)
    assert smoke['runtime_files'] == data['runtime_files'] and smoke['passed'] is True
    assert (WORK / 'tests-pass').read_text().strip() == p.digest(p.TARGET / p.MODULE)
    return data


def verify_topology(before):
    after = m.topology()
    for group in ('domestic', 'overseas', 'identity'):
        assert after[group] == before[group], 'Container/config drift: ' + group
    expected = {**before['native'], UNITS[1]: str(p.TARGET), UNITS[2]: str(p.TARGET)}
    assert after['native'] == expected
    expected_files = dict(before['nativeFiles'])
    for unit in UNITS:
        path = Path('/etc/systemd/system') / (unit + '.service.d') / DROP
        assert path.read_text() == dropin(unit, p.TARGET)
        expected_files[str(path)] = m.digest(path)
    for prefix in ('', 'OVERSEAS_'):
        path = WORK / (prefix.lower() + 'runtime.env')
        expected_files[str(path)] = m.digest(path)
    assert after['nativeFiles'] == expected_files, 'Unexpected native configuration change'


def deploy():
    assert not (WORK / 'DEPLOY_STARTED').exists(), 'Inspect prior attempt; never blindly replay'
    data = validate()
    before = {unit: runtime(unit) for unit in UNITS[:2]}
    assert all(value['actual'] == 'codex-cli 0.156.1' for value in before.values()), 'Unexpected old CLI'
    topology = m.topology()
    schemas = [r.sql('SELECT version_num FROM alembic_version'), u.sql('SELECT version_num FROM overseas_alembic_version')]
    domestic_source = p.tree(Path(topology['native'][UNITS[0]]))
    edge = m.EDGE.read_text()
    changed = closed_config(edge)
    m.private(WORK / 'edge-before.conf', edge)
    m.private(WORK / 'topology-before.json', topology)
    m.private(WORK / 'runtime-before.json', before)
    for unit in UNITS:
        m.private(WORK / (unit + '-before.txt'), m.run('systemctl', 'cat', unit, capture=True))
    for prefix in ('', 'OVERSEAS_'):
        m.private(WORK / (prefix.lower() + 'runtime.env'),
            prefix + 'CODEX_VERSION=' + p.VERSION + '\n' + prefix + 'CODEX_BINARY=' + str(p.RUNTIME / 'codex') + '\n')
    m.private(WORK / 'DEPLOY_STARTED', p.RELEASE)
    try:
        m.EDGE.write_text(changed)
        u.reload_edge()
        closed()
        m.run('docker', 'stop', '-t', '30', *APIS)
        wait_idle('before-outbox-stop')
        m.run('docker', 'stop', '-t', '30', OUTBOX)
        m.run('systemctl', 'stop', UNITS[2])
        wait_idle('after-outbox-stop')
        m.run('systemctl', 'stop', *UNITS[:2])
        m.private(WORK / 'STOPPED', 'DB, active, reserved, scheduled, broker and unacked empty twice')
        for unit in UNITS:
            path = Path('/etc/systemd/system') / (unit + '.service.d') / DROP
            m.private(path, dropin(unit, p.TARGET))
        m.run('systemctl', 'daemon-reload')
        m.run('systemctl', 'start', *UNITS)
        m.run('docker', 'start', OUTBOX)
        wait_idle('new-workers-ready')
        after = {unit: runtime(unit) for unit in UNITS[:2]}
        for value in after.values():
            assert value['binary'] == str(p.RUNTIME / 'codex')
            assert value['pinned'] == p.VERSION and value['actual'] == 'codex-cli ' + p.VERSION
        for mode in ('new', 'resume'):
            args = after[UNITS[1]][mode]
            assert args[args.index('--model') + 1] == 'gpt-6-astra'
            assert args[args.index('-c') + 1] == 'model_reasoning_effort="high"'
        assert p.tree(p.TARGET) == data['files'] and p.tree(Path(data['old'])) == data['baseline']
        m.run('docker', 'start', *APIS)
        for address in ('http://127.0.0.1:18008/api/v1/health/ready', 'http://127.0.0.1:18018/api/overseas/v1/health/ready'):
            m.run('curl', '--retry', '15', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-o', '/dev/null', address)
        verify_topology(topology)
        assert p.tree(Path(topology['native'][UNITS[0]])) == domestic_source
        assert [r.sql('SELECT version_num FROM alembic_version'), u.sql('SELECT version_num FROM overseas_alembic_version')] == schemas
        m.EDGE.write_text(edge)
        u.reload_edge()
        h.verify.public()
        verify_topology(topology)
        assert m.digest(m.EDGE) == topology['edgeHash']
        m.private(WORK / 'verification.json', dict(release=p.RELEASE, before=before, after=after,
                  schemasUnchanged=True, frontendUnchanged=True, containerIdentitiesUnchanged=True))
        print('CODEX_ASTRA_DEPLOY_COMPLETE', flush=True)
    except BaseException as exc:
        m.EDGE.write_text(changed)
        u.reload_edge()
        m.private(WORK / 'FAILURE.json', dict(type=type(exc).__name__,
            recovery='Keep intake closed. Inspect worker/broker state; only stop proven idle workers. '
            'Remove this release 95-codex-astra.conf overrides, daemon-reload and restore old native runtime. '
            'Restart APIs/outboxes as needed, verify both ready/auth before restoring edge-before.conf. No database restore.'))
        raise


if __name__ == '__main__':
    assert os.geteuid() == 0 and not sys.flags.optimize
    deploy()
