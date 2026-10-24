"""Standalone repair safeguards and release independence from cancelled restoration."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_studio_delivery_reliability_release import load, save, release


def repair_request():
    return dict(actor_id='10000000-0000-0000-0000-000000000001',
        turn_id='10000000-0000-0000-0000-000000000002', expected_sha256='a' * 64,
        expected_checksums={f'/mnt/data/original-{i}.png': 'b' * 64 for i in range(8)})


@pytest.fixture
def repair():
    return load('studio-delivery-release-repair')


@pytest.fixture
def repair_case(release, repair, monkeypatch, tmp_path):
    helper, events, failure = repair, [], {'at': None}
    body, baseline = repair_request(), {'paused': False, 'execution': {'executionCount': 1}}
    save(tmp_path / helper.REQUEST, body)
    (tmp_path / helper.REQUEST).chmod(0o600)
    tmp_path.chmod(0o700)
    helper.pin(tmp_path, release.m)
    save(tmp_path / 'INSTALLED_VERIFIED', 'verified')

    def call(work, target, context, packet, step, m):
        events.append(step)
        if step == failure['at']:
            raise AssertionError('injected ' + step)
        if step == 'inspect':
            return baseline
        if step == 'pause':
            assert json.loads((work / 'DELIVERY_REPAIR_BASELINE.private.json').read_text())['baseline'] == baseline
            assert (work / 'DELIVERY_REPAIR_STARTED').exists()
            return {'paused': True}
        if step == 'restore':
            assert (work / 'DELIVERY_REPAIR_VERIFIED.private.json').exists()
            return {'paused': packet['original_paused']}
        if step == 'failure-hold':
            return {'paused': True}
        if step.startswith('verify'):
            return {'execution': baseline['execution'], 'objects': list(body['expected_checksums'])}
        return dict(status={'dry-run': 'eligible', 'apply': 'succeeded', 'repeat': 'already_recovered'}[step],
            expected=8, saved=8 if step == 'repeat' else 0, checksums=body['expected_checksums'])

    monkeypatch.setattr(helper, 'invoke', call)
    monkeypatch.setattr(helper, 'worker_context', lambda *args: {})
    monkeypatch.setattr(release.d, 'closed', lambda: events.append('closed'))
    monkeypatch.setattr(release.d, 'wait_empty', lambda *args: events.append('idle'))
    return SimpleNamespace(release=release, helper=helper, work=tmp_path, events=events,
        failure=failure, baseline=baseline, target=Path('/installed/backend'))


def repair_run(case):
    case.helper.run(case.work, case.target, {'image': 'installed'}, case.release.m, case.release.d, case.release.u)


@pytest.mark.parametrize('original', [False, True])
def test_repair_restores_exact_original_gate_only_after_byte_verification_and_repeat(repair_case, original):
    case = repair_case
    case.baseline['paused'] = original
    repair_run(case)
    operations = [name for name in case.events if name not in ('closed', 'idle')]
    assert operations == ['inspect', 'pause', 'dry-run', 'apply', 'verify', 'repeat', 'verify-repeat', 'restore']
    assert (case.work / 'DELIVERY_REPAIR_GATE_RESTORED').read_text() == str(original)
    with pytest.raises(AssertionError, match='not replay'):
        repair_run(case)


@pytest.mark.parametrize('step', ['pause', 'dry-run', 'apply', 'verify', 'repeat', 'verify-repeat'])
def test_repair_failure_never_restores_gate_and_keeps_recovery_baseline(repair_case, step):
    case = repair_case
    case.failure['at'] = step
    with pytest.raises(AssertionError, match='injected'):
        repair_run(case)
    assert 'restore' not in case.events
    assert (case.work / 'DELIVERY_REPAIR_BASELINE.private.json').exists()
    assert (case.work / 'DELIVERY_REPAIR_STARTED').exists()
    assert not (case.work / 'DELIVERY_REPAIR_GATE_RESTORED').exists()


def test_repair_request_change_is_rejected_before_any_gate_operation(repair_case):
    case = repair_case
    body = repair_request()
    body['expected_sha256'] = 'c' * 64
    save(case.work / case.helper.REQUEST, body)
    with pytest.raises(AssertionError, match='changed after preparation'):
        repair_run(case)
    assert case.events == []


@pytest.mark.parametrize('change', ['secret', 'uuid', 'digest', 'seven', 'control'])
def test_private_repair_request_schema_is_narrow(release, repair, tmp_path, change):
    body = repair_request()
    if change == 'secret': body['password'] = 'must-not-be-accepted'
    if change == 'uuid': body['actor_id'] = 'invalid'
    if change == 'digest': body['expected_sha256'] = 'x' * 64
    if change == 'seven': body['expected_checksums'].pop('/mnt/data/original-7.png')
    if change == 'control': body['expected_checksums']['bad\npath'] = body['expected_checksums'].pop('/mnt/data/original-7.png')
    save(tmp_path / repair.REQUEST, body)
    (tmp_path / repair.REQUEST).chmod(0o600)
    tmp_path.chmod(0o700)
    with pytest.raises((AssertionError, ValueError)):
        repair.pin(tmp_path, release.m)


def test_private_repair_request_rejects_duplicate_json_keys(repair, tmp_path):
    save(tmp_path / repair.REQUEST, '{"actor_id":"a","actor_id":"b"}')
    (tmp_path / repair.REQUEST).chmod(0o600)
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError, match='Duplicate'):
        repair.request(tmp_path)


@pytest.mark.parametrize('request_state', ['absent', 'stale'])
def test_installed_verifies_preservation_then_reopens_without_original_repair(release, monkeypatch, tmp_path, request_state):
    work, source, target, events = tmp_path, tmp_path / 'src', Path('/installed/backend'), []
    request = work / 'delivery-repair-request.private.json'
    if request_state == 'stale':
        save(request, 'deleted task; not a valid restoration request')
    save(source / 'release.json', '{}')
    save(work / 'native-target', str(target))
    save(work / 'delivery-skill-states.private.json', 'original')
    save(work / 'NATIVE_INSTALL_TESTS.json', release.s.receipt(work, source, 'image', target))
    monkeypatch.setattr(release, '_installed', lambda *args: events.append('installed'))
    monkeypatch.setattr(release, 'skill_states', lambda: 'original')
    monkeypatch.setattr(release.m, 'image_id', lambda *args: 'image')

    def inherited(*args):
        release.d.installed(work, {}, 'image', {}, {}, target)
        assert (work / 'DELIVERY_PRESERVATION_VERIFIED').exists()
        events.append('open')

    monkeypatch.setattr(release.s, '_deploy', inherited)
    release.d.deploy(work, source, {}, 'image')
    assert events == ['installed', 'open']
    assert not list(work.glob('DELIVERY_REPAIR_*'))
    assert request.exists() is (request_state == 'stale')
    if request.exists():
        assert request.read_text() == 'deleted task; not a valid restoration request'


def test_inherited_deploy_failure_handler_keeps_edge_closed_on_skill_drift(release, monkeypatch, tmp_path):
    work, source, d, m, u = tmp_path, tmp_path / 'src', release.d, release.m, release.u
    target, events = Path('/installed/backend'), []
    save(source / 'release.json', '{}')
    for name in ('PREPARED', 'UPLOAD_CAPACITY_IMAGE_ID'): save(work / name, 'image')
    save(work / 'native-target', str(target))
    save(work / 'delivery-skill-states.private.json', 'original')
    save(work / 'NATIVE_INSTALL_TESTS.json', release.s.receipt(work, source, 'image', target))
    data = {'overseas': {}}
    save(work / 'topology.json', data)
    save(work / 'domestic-native.json', {})
    edge = work / 'edge.conf'
    save(edge, 'closed')
    monkeypatch.setattr(m, 'EDGE', edge)
    monkeypatch.setattr(d, 'BACKUPS', work / 'backups')
    monkeypatch.setattr(m, 'image_id', lambda *a: 'image')
    monkeypatch.setattr(m, 'topology', lambda: data)
    monkeypatch.setattr(d, 'domestic_native', lambda: {})
    for name in ('schemas', 'preflight', 'prepared_settings', 'drain_and_stop', 'before_switch'):
        monkeypatch.setattr(d, name, lambda *a: None)
    monkeypatch.setattr(m, 'assets_safe', lambda *a: None)
    monkeypatch.setattr(d.r, 'hashes', lambda *a: None)
    monkeypatch.setattr(d.proxy, 'unchanged', lambda *a: None)
    monkeypatch.setattr(d, 'closed_config', lambda value: value)
    monkeypatch.setattr(d, 'close_edge', lambda *a: events.append('close-edge'))
    monkeypatch.setattr(d, 'closed', lambda: events.append('closed'))
    monkeypatch.setattr(d.proxy, 'restore_inner', lambda *a: events.append('restore-inner'))
    monkeypatch.setattr(m, 'compose', lambda *a, **kw: events.append('compose-' + a[1]))
    monkeypatch.setattr(m, 'run', lambda *a, **kw: None)
    monkeypatch.setattr(u, 'switch_native', lambda *a: None)
    monkeypatch.setattr(u, 'backup', lambda work, destination, data: save(destination / 'COMPLETE', 'verified'))
    monkeypatch.setattr(u, 'reload_edge', lambda: events.append('open'))
    monkeypatch.setattr(release, '_installed', lambda *a: None)
    monkeypatch.setattr(release, 'skill_states', lambda: 'changed')
    with pytest.raises(AssertionError, match='Installed Skill states drift'):
        d.deploy(work, source, {'release': 'fixture', 'files': {}}, 'image')
    assert 'open' not in events
    assert events[-1] == 'compose-stop'
    assert events.count('close-edge') == 2
    assert json.loads((work / 'FAILURE.json').read_text())['phase'] == 'verify-installed'
    assert not (work / 'DELIVERY_PRESERVATION_VERIFIED').exists()
    assert not list(work.glob('DELIVERY_REPAIR_*'))


def test_release_failure_never_handles_unrelated_repair_markers(release, monkeypatch, tmp_path):
    failure = RuntimeError('frontend verification failed')
    source, manifest = tmp_path / 'src', {'files': {}}

    def later_failure(*args):
        assert args == (tmp_path, source, manifest, 'image')
        save(tmp_path / 'DELIVERY_REPAIR_STARTED', 'unrelated standalone operation')
        raise failure

    monkeypatch.setattr(release.s, 'deploy', later_failure)
    with pytest.raises(RuntimeError, match='frontend verification failed') as raised:
        release.deploy(tmp_path, source, manifest, 'image')
    assert raised.value is failure
    assert {path.name for path in tmp_path.iterdir()} == {'DELIVERY_REPAIR_STARTED'}
    assert (tmp_path / 'DELIVERY_REPAIR_STARTED').read_text() == 'unrelated standalone operation'


def test_runtime_transport_keeps_request_and_secrets_off_command_line(release, repair, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(repair.subprocess, 'run', lambda args, **kw:
        calls.append((args, kw)) or SimpleNamespace(returncode=0, stdout='{"paused":true}'))
    packet = {'request': repair_request(), 'action': 'pause'}
    context = dict(cwd=Path('/installed/backend'), env={'EXISTING_SECRET': 'opaque'}, user=1002, group=1002, extra_groups=[986], umask=0o077)
    assert repair.invoke(tmp_path, Path('/installed/backend'), context, packet, 'pause', release.m) == {'paused': True}
    args, kwargs = calls[0]
    assert args[:3] == [str(Path('/installed/backend/.venv/bin/python')), '-B', '-c']
    assert packet['request']['actor_id'] not in str(args) and 'opaque' not in str(args)
    assert json.loads(kwargs['input']) == packet and kwargs['timeout'] == 600
    assert kwargs['user'] == 1002 and kwargs['extra_groups'] == [986]
