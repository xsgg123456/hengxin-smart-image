"""Recovery helper must fail before application of unverified historical work."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('context_recovery',
    Path(__file__).with_name('overseas-context-recovery.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
IDENTITY = '0b8feaa4-f302-4cc5-8cec-767004f0086d'


@pytest.fixture
def setup(tmp_path, monkeypatch):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    (backup / 'COMPLETE').write_text('verified')
    (work / 'EXECUTORS_STOPPED').write_text('verified')
    raw = json.dumps(dict(conversationIds=[IDENTITY])).encode()
    (work / 'context-targets.json').write_bytes(raw)
    (work / 'CONTEXT_TARGETS_SHA256').write_text(hashlib.sha256(raw).hexdigest())
    runtime = SimpleNamespace(u=SimpleNamespace(UNITS=['worker', 'outbox'],
        pending=Mock(return_value=0), sql=Mock(return_value='0')),
        run=Mock(return_value='inactive'),
        private=lambda path, value: path.write_text(json.dumps(value)))
    monkeypatch.setattr(r, 'runtime', lambda: runtime)
    before = dict(conversationId=IDENTITY, sessionId='unchanged',
        plan={'digest': 'source-sha', 'files': [{}, {}], 'inputFiles': 1})
    probe = dict(threeRounds=[dict(derived=True, readonly=True, isolated=True)] * 3)
    reads = dict(independentSandboxReads=[dict(allHashesMatch=True, readableFiles=191)] * 3,
        sourceDigest='source-sha', sourceFilesVerified=2, sourceInputsVerified=1)
    invoke = Mock(side_effect=[probe, before, {**before, 'status': 'restored'}, reads])
    monkeypatch.setattr(r, 'invoke', invoke)
    return work, backup, runtime, invoke


@pytest.mark.parametrize('fault', ['backup', 'drain', 'active', 'pending', 'deleting', 'targets'])
def test_ineligible_recovery_never_invokes_worker(setup, fault):
    work, backup, runtime, invoke = setup
    if fault == 'backup': (backup / 'COMPLETE').unlink()
    if fault == 'drain': (work / 'EXECUTORS_STOPPED').unlink()
    if fault == 'active': runtime.run.return_value = 'active'
    if fault == 'pending': runtime.u.pending.return_value = 1
    if fault == 'deleting': runtime.u.sql.return_value = '1'
    if fault == 'targets': (work / 'context-targets.json').write_text('{}')
    with pytest.raises(ValueError): r.recover_contexts(work, work, work, {}, backup)
    invoke.assert_not_called()
    assert not (work / 'CONTEXT_RECOVERY_VERIFIED').exists()


@pytest.mark.parametrize('fault', ['sandbox', 'apply', 'session', 'reads', 'source-coverage'])
def test_failed_proof_never_marks_verified(setup, fault):
    work, backup, _, invoke = setup
    results = list(invoke.side_effect)
    if fault == 'sandbox': results[0]['threeRounds'][0]['isolated'] = False
    if fault == 'apply': results[2] = RuntimeError('restore failed')
    if fault == 'session': results[2]['sessionId'] = 'changed'
    if fault == 'reads': results[3]['independentSandboxReads'][0]['allHashesMatch'] = False
    if fault == 'source-coverage': results[3]['sourceFilesVerified'] = 1
    invoke.side_effect = results
    with pytest.raises((ValueError, RuntimeError)): r.recover_contexts(work, work, work, {}, backup)
    assert not (work / 'CONTEXT_RECOVERY_VERIFIED').exists()
    if fault != 'sandbox': assert (work / 'CONTEXT_RECOVERY_FAILURE').is_file()


def test_same_session_verified_only_after_three_real_sandbox_reads(setup):
    work, backup, _, invoke = setup
    r.recover_contexts(work, work, work, {}, backup)
    assert invoke.call_args_list[2].args[1] == ['-m', 'app.overseas.studio.restore_context',
        IDENTITY, '--apply', '--expected-digest', 'source-sha']
    result = json.loads((work / 'CONTEXT_RECOVERY_VERIFIED').read_text())
    assert result == dict(conversations=[IDENTITY], sessionIds=['unchanged'], sandboxReads=3)


def test_invocation_uses_installed_venv_worker_identity_and_private_environment(tmp_path, monkeypatch):
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='{}'))
    monkeypatch.setattr(r.subprocess, 'run', run)
    r.invoke(tmp_path, ['tests/studio_context_probe.py'])
    command = run.call_args.args[0]
    assert command[-2:] == [str(tmp_path / '.venv/bin/python'), 'tests/studio_context_probe.py']
    assert '--property=User=hengxin-overseas' in command
    assert '--property=EnvironmentFile=/etc/hengxin-overseas/worker.env' in command
    assert '--property=RuntimeMaxSec=300' in command
