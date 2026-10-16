"""Offline checks for the one-shot inspected image-release recovery."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


rec = load('overseas-images-recover')
deploy = load('overseas-images-deploy')
RAW = ('{ path=/bin/python ; argv[]=/bin/python -m app.deletions ; ignore_errors=no ; '
       'start_time=[Fri 2026-10-16 08:00:00 UTC] ; stop_time=[n/a] ; pid=3925617 ; code=(null) ; status=0/0 }')
RESET = RAW.replace('Fri 2026-10-16 08:00:00 UTC', 'n/a').replace('pid=3925617', 'pid=0')


def test_normalization_is_identical_nonmutating_and_narrow():
    for raw in (RAW, RESET, RAW + ' ' + RESET, 'unknown', ''):
        assert rec.normalize_exec_start(raw) == deploy.normalize_exec_start(raw)
    before = {'worker': {'pid': 3925617, 'cwd': '/old', 'fields': {'ExecStart': RAW}, 'files': {'/unit': 'abc'}}}
    saved = copy.deepcopy(before)
    after = copy.deepcopy(before)
    after['worker']['fields']['ExecStart'] = RESET
    assert rec.normalize_native(before) == rec.normalize_native(after)
    assert before == saved
    for field, value in [('pid', 9), ('cwd', '/unexpected'), ('files', {'/unit': 'changed'})]:
        drift = copy.deepcopy(after)
        drift['worker'][field] = value
        assert rec.normalize_native(before) != rec.normalize_native(drift)
    for old, new in [('path=/bin/python', 'path=/bin/other'), ('app.deletions', 'app.other'), ('ignore_errors=no', 'ignore_errors=yes')]:
        assert rec.normalize_exec_start(RAW) != rec.normalize_exec_start(RESET.replace(old, new))
    unknown = RESET.replace('code=(null)', 'unknown=value')
    assert rec.normalize_exec_start(unknown) == unknown


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    work = tmp_path / 'work'; work.mkdir()
    source = work / 'src'; source.mkdir()
    backup = tmp_path / 'backups' / rec.RELEASE; backup.mkdir(parents=True)
    app = tmp_path / 'app'; app.mkdir()
    systemd = tmp_path / 'systemd'; systemd.mkdir()
    edge = tmp_path / 'edge'; edge.write_text('closed')
    inner = tmp_path / 'inner'; inner.write_text('old-inner')
    target = Path('/opt/hengxin-overseas-releases') / rec.RELEASE / 'backend'
    native = {'domestic': {'pid': 3925617, 'cwd': '/old', 'fields': {'ExecStart': RAW, 'User': 'codex'}, 'files': {'/unit': 'hash'}}}
    actual_native = copy.deepcopy(native); actual_native['domestic']['fields']['ExecStart'] = RESET
    data = {'overseas': {'ids': {'api': 'old'}, 'mounts': {'api': []}, 'files': {}}, 'nativeFiles': {}}
    manifest = {'release': rec.RELEASE, 'files': {'backend/app.py': 'hash'}}
    values = {'PHASE': 'verify-installed', 'FAILURE.json': json.dumps({'phase': 'verify-installed', 'errorType': 'AssertionError'}),
        'DEPLOY_STARTED': rec.RELEASE, 'EXECUTORS_STOPPED': 'ok', 'INSTALL_TEST_IMAGE_ID': 'tested',
        'PREPARED': 'tested', 'UPLOAD_CAPACITY_IMAGE_ID': 'tested', 'topology.json': json.dumps(data),
        'domestic-native.json': json.dumps(native), 'native-target': str(target), 'edge-before.conf': 'old-edge',
        'upload-inner-before.conf': 'old-inner', 'upload-inner-after.conf': 'old-inner',
        'upload-edge-before.conf': 'old-edge', 'upload-edge-after.conf': 'old-edge'}
    for name, value in values.items(): (work / name).write_text(value)
    for name, value in {'COMPLETE': 'ok', 'full-topology.json': json.dumps(data), 'overseas.dump': 'backup', 'edge.conf': 'old-edge'}.items():
        (backup / name).write_text(value)
    for name, value in {'OVERSEAS_RELEASE.json': '{"release":"overseas-20261015-726ede0"}',
        'FRONTEND_RELEASE.json': '{"release":"domestic-20261015-4c64c1a"}', 'frontend/package.json': '{"version":"0.2.37"}',
        'frontend/dist/index.html': 'old-html', 'frontend/dist/index.html.gz': 'old-gzip'}.items():
        for root in (app, backup):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value)
    events = []
    def event(name):
        return lambda *args, **kwargs: events.append(name)
    def image_id(work, image):
        assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == 'tested'
        return 'tested'
    units = ('worker', 'outbox')
    for unit in units:
        pointer = systemd / (unit + '.service.d') / '99-overseas-upload.conf'
        pointer.parent.mkdir(); pointer.write_text('candidate-pointer')
    def run(*args, **kwargs):
        if args[0] == 'systemctl': return str(systemd / (args[2] + '.service.d') / '99-overseas-upload.conf')
        events.append('web-reload')
    m = NS(APP=app, EDGE=edge, GROUPS=('overseas',), image_id=Mock(side_effect=image_id), digest=Mock(return_value='hash'),
        private=lambda p, v: p.write_text(v if isinstance(v, str) else json.dumps(v)),
        live=Mock(return_value={'State': {'Running': False}, 'Image': 'tested', 'HostConfig': {'Memory': 3 * 1024**3}, 'Mounts': []}),
        compose=Mock(side_effect=event('compose')), run=Mock(side_effect=run), assets_safe=Mock())
    u = NS(API='api', UNITS=units, DROP='99-overseas-upload.conf', wait_worker_ready=Mock(side_effect=event('worker-ready')),
        reload_edge=Mock(side_effect=event('open')))
    r = NS(PREFIX='web-', hashes=Mock(), publish=Mock(side_effect=event('publish')))
    verify = NS(proxy=Mock(side_effect=event('proxy')), frontend=Mock(), public=Mock(side_effect=event('public')))
    proxy = NS(inner=lambda m: inner, install_inner=Mock(side_effect=event('install-inner')), verify=Mock(side_effect=event('boundary')), restore_inner=Mock())
    d = NS(m=m, u=u, r=r, verify=verify, proxy=proxy, BACKUPS=tmp_path / 'backups', BASE_VERSION='0.2.37',
        DOMESTIC_MIGRATION='0029', TARGET_MIGRATION='overseas_0016', resources=NS(API_MEMORY=3 * 1024**3),
        schemas=Mock(), prepared_settings=Mock(), domestic_native=Mock(side_effect=lambda: rec.normalize_native(actual_native)),
        closed_config=lambda x: 'closed', closed=Mock(side_effect=event('closed')), close_edge=Mock(),
        wait_empty=Mock(side_effect=event('empty')), installed=Mock(side_effect=event('installed')), resources_unchanged=Mock())
    c = NS(d=d, BASE_RELEASE='overseas-20261015-726ede0', BASE_FRONTEND_RELEASE='domestic-20261015-4c64c1a',
        SYSTEMD=systemd, native_state=Mock(), a=NS(native_pointer=lambda *a: 'candidate-pointer', proxy_baseline=Mock()))
    return NS(c=c, d=d, work=work, source=source, backup=backup, manifest=manifest, events=events, actual_native=actual_native)


def recover(f):
    rec.recover(f.c, f.work, f.source, f.manifest, 'candidate-image')


def test_forward_recovery_checks_before_api_and_installed_before_publication(fixture):
    f = fixture
    before = (f.work / 'domestic-native.json').read_bytes()
    recover(f)
    events = f.events
    assert events.index('closed') < events.index('empty') < events.index('compose') < events.index('installed')
    assert events.index('installed') < events.index('install-inner') < events.index('publish') < events.index('open') < events.index('boundary')
    assert f.d.m.compose.call_count == 1
    assert '--no-build' in f.d.m.compose.call_args.args and '--no-deps' in f.d.m.compose.call_args.args
    assert f.d.r.hashes.call_args_list[0].args == (f.source, f.manifest)
    assert (f.work / 'domestic-native.json').read_bytes() == before
    assert (f.work / 'PHASE').read_text() == (f.work / 'RECOVERY_PHASE').read_text() == 'complete'
    assert not any(call.args[:2] == ('systemctl', 'stop') for call in f.d.m.run.call_args_list)
    assert not (f.work / 'RECOVERY_FAILURE.json').exists()


@pytest.mark.parametrize('guard', ['release', 'phase', 'failure', 'backup', 'dump', 'prepared', 'install', 'capacity',
    'replay', 'pid', 'cwd', 'argv', 'hash', 'user', 'manifest', 'frontend', 'api-running', 'image', 'memory', 'mounts',
    'pointer', 'source-hash', 'schema', 'queues', 'edge'])
def test_preflight_failure_never_restarts_api(fixture, guard):
    f = fixture
    files = {'phase': ('PHASE', 'switch'), 'failure': ('FAILURE.json', '{"phase":"verify-installed","errorType":"RuntimeError"}'),
        'prepared': ('PREPARED', 'bad'), 'install': ('INSTALL_TEST_IMAGE_ID', 'bad'), 'capacity': ('UPLOAD_CAPACITY_IMAGE_ID', 'bad'),
        'replay': ('RECOVERY_STARTED', 'old')}
    if guard in files:
        name, value = files[guard]; (f.work / name).write_text(value)
    elif guard == 'release': f.manifest['release'] = 'other'
    elif guard == 'backup': (f.backup / 'COMPLETE').unlink()
    elif guard == 'dump': (f.backup / 'overseas.dump').write_text('')
    elif guard in ('pid', 'cwd', 'hash', 'argv', 'user'):
        state = f.actual_native['domestic']
        if guard == 'pid': state['pid'] = 123
        elif guard == 'cwd': state['cwd'] = '/changed'
        elif guard == 'hash': state['files']['/unit'] = 'changed'
        else: state['fields']['ExecStart' if guard == 'argv' else 'User'] = 'changed'
    elif guard == 'manifest': (f.d.m.APP / 'OVERSEAS_RELEASE.json').write_text('{"release":"changed"}')
    elif guard == 'frontend': (f.d.m.APP / 'frontend/dist/index.html').write_text('changed')
    elif guard in ('api-running', 'image', 'memory', 'mounts'):
        actual = f.d.m.live.return_value
        if guard == 'api-running': actual['State']['Running'] = True
        elif guard == 'image': actual['Image'] = 'changed'
        elif guard == 'memory': actual['HostConfig']['Memory'] = 1
        else: actual['Mounts'] = ['changed']
    elif guard == 'pointer': next(f.c.SYSTEMD.rglob('*.conf')).write_text('changed')
    elif guard == 'edge': f.d.m.EDGE.write_text('open')
    else:
        target = {'source-hash': f.d.r.hashes, 'schema': f.d.schemas, 'queues': f.d.wait_empty}[guard]
        target.side_effect = AssertionError('guard')
    with pytest.raises(AssertionError): recover(f)
    f.d.m.compose.assert_not_called()
    f.d.r.publish.assert_not_called()
    if guard != 'replay': assert not (f.work / 'RECOVERY_STARTED').exists()


@pytest.mark.parametrize('failure', ['api', 'installed', 'public', 'boundary'])
def test_failure_closes_and_stops_only_api(fixture, failure):
    f = fixture
    target = {'api': f.d.m.compose, 'installed': f.d.installed, 'public': f.d.verify.public, 'boundary': f.d.proxy.verify}[failure]
    target.side_effect = [RuntimeError('failure'), None] if failure == 'api' else RuntimeError('failure')
    with pytest.raises(RuntimeError): recover(f)
    f.d.close_edge.assert_called_once()
    f.d.proxy.restore_inner.assert_called_once()
    assert f.d.m.compose.call_args.args[1:] == ('stop', '-t', '30', 'api')
    assert not any(call.args[:2] == ('systemctl', 'stop') for call in f.d.m.run.call_args_list)
    assert (f.work / 'RECOVERY_STARTED').exists()
    assert not (f.work / 'verification.json').exists()
    assert (f.work / 'PHASE').read_text() == 'verify-installed'
    assert json.loads((f.work / 'FAILURE.json').read_text())['errorType'] == 'AssertionError'
    assert json.loads((f.work / 'RECOVERY_FAILURE.json').read_text())['errorType'] == 'RuntimeError'


def test_cli_uses_original_source_and_managed_recovery(monkeypatch, tmp_path):
    work = tmp_path / 'work'; source = work / 'src'; source.mkdir(parents=True)
    monkeypatch.setattr(rec, 'WORK', work)
    monkeypatch.setattr(rec.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(rec.os, 'umask', Mock())
    retention = NS(managed=Mock())
    c = NS(validate=Mock(return_value=(source, {}, 'image')), d=NS(m=NS(module=Mock(return_value=retention))))
    loader = Mock(return_value=c); monkeypatch.setattr(rec, 'load', loader)
    monkeypatch.setattr(sys, 'argv', ['recovery', rec.RELEASE, 'recover', '--source', str(source)])
    rec.main()
    loader.assert_called_once_with(source)
    assert retention.managed.call_args.kwargs['argv'] == ['recovery', rec.RELEASE, 'recover']
    c.d.m.module.assert_called_once_with('release-retention')


def test_optimized_python_aborts():
    result = subprocess.run([sys.executable, '-O', rec.__file__], capture_output=True, text=True,
        env={**os.environ, 'PYTHONOPTIMIZE': '1'}, timeout=20)
    assert result.returncode != 0 and 'Python -O disables' in result.stderr
