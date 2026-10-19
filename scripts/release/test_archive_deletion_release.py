"""Archive deletion cutover fault matrix; no production writes."""
import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a = load('overseas-archive-deletion-deploy')
d = a.d
p = load('package-archive-deletion')
baseline = load('test_studio_ux_release')
baseline.d = baseline.t.d = baseline.t.t.d = d
baseline.t.p = d.proxy
baseline.a = a.a


class ArchiveReleaseTests(baseline.StudioUXReleaseTests):
    pass


@pytest.mark.parametrize('fault', [None, 'domestic', 'revision', 'usage', 'visibility', 'audit', 'deletion'])
def test_schema_transition(monkeypatch, fault):
    monkeypatch.setattr(d.r, 'sql', lambda _: '0029' if fault == 'domestic' else '0030')
    values = ['wrong' if fault == 'revision' else 'overseas_0018',
              '1' if fault == 'usage' else '0', '0' if fault == 'visibility' else '1',
              '0' if fault == 'audit' else '1', '1' if fault == 'deletion' else '0']
    monkeypatch.setattr(d.u, 'sql', Mock(side_effect=values))
    if fault:
        with pytest.raises(AssertionError): a.schemas()
    else:
        a.schemas()


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'schema', 'config', 'migration', 'rows', 'extra', 'missing'])
def test_migration_is_only_additive_and_stays_closed(tmp_path, monkeypatch, fault):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').touch()
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').touch()
    (backup / 'fingerprints.json').write_text('{"archives":"original"}')
    before = {'services': {'migrate': {'image': 'old', 'environment': {'ROLE': 'owner'}}, 'api': {'image': 'old'}}}
    (work / 'overseas-compose.private.json').write_text(json.dumps(before))
    after = copy.deepcopy(before)
    after['services']['migrate']['image'] = 'tested'
    if fault == 'config': after['services']['api']['image'] = 'wrong'
    rows = {'archives': 'changed' if fault == 'rows' else 'original', a.TABLE: '0:empty'}
    if fault == 'extra': rows['unexpected'] = '0:empty'
    if fault == 'missing': rows.pop('archives')
    monkeypatch.setattr(a, 'schemas', Mock(side_effect=AssertionError('schema') if fault == 'schema' else None))
    monkeypatch.setattr(a, 'installed_schemas', Mock())
    monkeypatch.setattr(a.a, 'fingerprint', Mock(side_effect=[{'archives': 'original'}, rows]))
    compose = Mock(side_effect=[json.dumps(before), json.dumps(after), RuntimeError('migration') if fault == 'migration' else ''])
    monkeypatch.setattr(d.m, 'compose', compose)
    monkeypatch.setattr(d.m, 'private', lambda path, value: path.write_text(value if isinstance(value, str) else json.dumps(value)))
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            a.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert not (work / 'MIGRATION_VERIFIED').exists()
        if fault in ('backup', 'drain', 'schema', 'config'):
            assert not (work / 'MIGRATION_STARTED').exists()
    else:
        a.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert compose.call_args.args[-1] == 'overseas_0019'
        assert 'overseas_0019' in (work / 'MIGRATION_VERIFIED').read_text()


def command(unit):
    old = a.OVERSEAS_PATHS[unit]
    argv = (f'{old}/.venv/bin/python {old}/.venv/bin/celery -A app.overseas.execution.worker:celery_app worker '
        '--pool=prefork --concurrency=5 --loglevel=INFO --hostname=overseas@production --queues=overseas.cli'
        if unit == d.u.UNITS[0] else f'{old}/.venv/bin/python -m app.overseas.execution.outbox')
    return f'{{ path={old}/.venv/bin/python ; argv[]={argv} ; ignore_errors=no ; start_time=now ; stop_time=n/a ; pid=12 ; code=(null) ; status=0/0 }}'


def test_switch_keeps_auth_dropin_and_all_worker_arguments(tmp_path, monkeypatch):
    monkeypatch.setattr(a.c, 'SYSTEMD', tmp_path)
    target = Path('/new/backend')
    current = dict(a.OVERSEAS_PATHS)
    monkeypatch.setattr(a, 'settings', lambda unit: {'Environment': 'BROKER=unchanged', 'SupplementaryGroups': 'auth'})
    monkeypatch.setattr(a, 'show', lambda unit, key: command(unit) if key == 'ExecStart' else str(current[unit]))
    for unit in d.u.UNITS:
        folder = tmp_path / (unit + '.service.d'); folder.mkdir()
        (folder / 'zzzz-codex-auth-20261019.conf').write_text('preserve auth')
    monkeypatch.setattr(d.m, 'run', lambda *args: current.update(dict.fromkeys(d.u.UNITS, target)))
    monkeypatch.setattr(d.m, 'private', lambda path, body: path.write_text(body))
    a.switch_native(target)
    for unit in d.u.UNITS:
        folder = tmp_path / (unit + '.service.d')
        body = (folder / d.u.DROP).read_text()
        assert 'Environment=' not in body and 'SupplementaryGroups=' not in body
        assert (folder / 'zzzz-codex-auth-20261019.conf').read_text() == 'preserve auth'
        assert str(a.OVERSEAS_PATHS[unit]) not in body
        assert 'WorkingDirectory=' + str(target) in body
        if unit == d.u.UNITS[0]:
            assert str(target) + '/.venv/bin/python ' + str(target) + '/.venv/bin/celery' in body
            assert '--hostname=overseas@production --queues=overseas.cli' in body


def test_native_snapshots_use_distinct_paths_and_protect_broker(monkeypatch):
    monkeypatch.setattr(a, 'native_state', lambda unit, path: str(path))
    monkeypatch.setattr(a, 'broker_state', lambda: {'pid': 123, 'socket': 'stable'})
    result = a.domestic_native()
    assert result[a.BROKER]['pid'] == 123
    assert result['hengxin-vps-codex-worker'] != result['hengxin-retention']
    assert a.OVERSEAS_PATHS[d.u.UNITS[0]] != a.OVERSEAS_PATHS[d.u.UNITS[1]]


def test_package_contract():
    values = dict.fromkeys(p.REQUIRED, b'')
    values.update({'frontend/package.json': b'{"version":"0.2.42"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'})
    p.validate(values)
    for name in p.REQUIRED:
        assert p.selected(name if name.startswith('scripts/') else p.p.APP + name) == name or name.startswith('frontend/dist/')
        with pytest.raises(ValueError, match='Missing'):
            p.validate({key: value for key, value in values.items() if key != name})
    assert (p.p.DOMESTIC_MIGRATION, p.p.OVERSEAS_MIGRATION) == ('0030', 'overseas_0019')


@pytest.mark.parametrize('fault', [None, 'image', 'group', 'env', 'override', 'release'])
def test_preflight_preserves_auth_and_rejects_drift(tmp_path, monkeypatch, fault):
    app, systemd = tmp_path / 'app', tmp_path / 'systemd'
    (app / 'frontend').mkdir(parents=True)
    systemd.mkdir()
    (app / 'frontend/package.json').write_text('{"version":"0.2.41"}')
    for name in ('FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
        (app / name).write_text(json.dumps({'release': 'wrong' if fault == 'release' else a.BASE_RELEASE}))
    monkeypatch.setattr(d.m, 'APP', app)
    monkeypatch.setattr(a.c, 'SYSTEMD', systemd)
    monkeypatch.setattr(d.m, 'live', lambda _: {'Image': 'bad' if fault == 'image' else a.BASE_IMAGE,
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': d.resources.API_MEMORY, 'RestartPolicy': {'Name': 'unless-stopped'}}})
    monkeypatch.setattr(a, 'native_state', Mock())
    monkeypatch.setattr(a, 'domestic_native', Mock())
    monkeypatch.setattr(a, 'pointer', Mock())
    monkeypatch.setattr(a, 'settings', lambda _: {
        'SupplementaryGroups': '' if fault == 'group' else 'hengxin-codex-auth',
        'Environment': '' if fault == 'env' else 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(a.SOCKET)})
    monkeypatch.setattr(a, 'show', lambda *_: '/unit/zzzz-codex-auth-20261019.conf')
    for unit in d.u.UNITS:
        folder = systemd / (unit + '.service.d'); folder.mkdir()
        if fault == 'override': (folder / 'zzzzzz-other.conf').touch()
    edge = tmp_path / 'edge'; edge.write_text('safe proxy')
    monkeypatch.setattr(d.m, 'EDGE', edge)
    monkeypatch.setattr(d.proxy, 'inner', lambda _: edge)
    monkeypatch.setattr(a.c.a, 'proxy_baseline', Mock())
    if fault:
        with pytest.raises(AssertionError): a.preflight()
    else:
        a.preflight()


def test_prepare_accepts_split_worker_and_outbox_paths(tmp_path, monkeypatch):
    work = tmp_path / 'work'; work.mkdir()
    (work / 'UPLOAD_CAPACITY_IMAGE_ID').write_text('tested')
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text('{"version":"0.2.41"}')
    data = {'overseas': {'env': '/env'}, 'native': {k: str(v) for k, v in a.OVERSEAS_PATHS.items()}}
    monkeypatch.setattr(d.m, 'APP', tmp_path)
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'tested')
    monkeypatch.setattr(d.m, 'topology', lambda: data)
    monkeypatch.setattr(d.m, 'GROUPS', ())
    monkeypatch.setattr(d.m, 'private', lambda path, value: path.write_text(value if isinstance(value, str) else json.dumps(value)))
    for module, name in [(a, 'schemas'), (a, 'preflight'), (d.m, 'assets_safe'), (d.drain, 'idle'),
                          (d, 'prepared_settings'), (d.r, 'hashes'), (d.m.skills, 'verify'), (d.proxy, 'prepare')]:
        monkeypatch.setattr(module, name, Mock())
    monkeypatch.setattr(a, 'domestic_native', lambda: {'broker': 'unchanged'})
    monkeypatch.setattr(a, 'settings', lambda _: {'group': 'auth'})
    monkeypatch.setattr(d, 'evidence', lambda _: {'workers': {}})
    monkeypatch.setattr(d.u, 'prepare_native', lambda *_: tmp_path / 'new/backend')
    a.prepare(work, tmp_path, {'release': 'new', 'files': {}}, 'image')
    assert (work / 'PREPARED').read_text() == 'tested'
    assert json.loads((work / 'overseas-native-settings.json').read_text()) == {unit: {'group': 'auth'} for unit in d.u.UNITS}



def test_new_entrypoint_rejects_optimized_python():
    import os
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-O', str(Path(__file__).with_name('overseas-archive-deletion-deploy.py')),
        'overseas-20261019-abcdef0', 'build'], capture_output=True, text=True,
        env={**os.environ, 'PYTHONOPTIMIZE': '1'}, timeout=30)
    assert result.returncode != 0
    assert 'Python -O disables release safety assertions' in result.stderr


def test_all_deploy_imports_packaged():
    import ast
    folder = Path(__file__).parent
    seen, pending = set(), ['overseas-archive-deletion-deploy.py', 'release-retention.py']
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        assert p.selected('scripts/release/' + name) == 'scripts/release/' + name
        for node in ast.walk(ast.parse((folder / name).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute):
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    candidate = arg.value if node.func.attr == 'with_name' else arg.value + '.py' if node.func.attr == 'module' else ''
                    if candidate and (folder / candidate).is_file(): pending.append(candidate)
    assert {'overseas-studio-ux-deploy.py', 'overseas-upload-deploy.py', 'member-release-backup.py'} <= seen

