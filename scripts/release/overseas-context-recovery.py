"""Recover explicitly listed idle conversations under the installed worker identity."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import UUID, uuid4


def runtime():
    spec = importlib.util.spec_from_file_location('context_runtime',
        Path(__file__).with_name('member-release-runtime.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def invoke(target, arguments, *, source_plan=None):
    command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
        '--unit=hx-context-' + uuid4().hex,
        '--property=User=hengxin-overseas', '--property=Group=hengxin-overseas',
        '--property=EnvironmentFile=/etc/hengxin-overseas/worker.env',
        '--property=Environment=HX_BUSINESS_CONTEXT=overseas',
        '--property=WorkingDirectory=' + str(target), '--property=UMask=0077',
        '--property=RuntimeMaxSec=300', str(target / '.venv/bin/python'), *arguments]
    result = subprocess.run(command, capture_output=True, text=True, timeout=330,
        input=json.dumps(source_plan) if source_plan is not None else None)
    if result.returncode:
        # Diagnostics stay in the root-private release directory, not application UI.
        raise RuntimeError('Context maintenance failed: ' + result.stderr[-2000:])
    return json.loads(result.stdout)


def recover_contexts(work, source, target, data, destination):
    m = runtime()
    if not (destination / 'COMPLETE').is_file() or not (work / 'EXECUTORS_STOPPED').is_file():
        raise ValueError('Verified backup and drained executors required')
    for unit in m.u.UNITS:
        state = m.run('systemctl', 'show', unit, '-p', 'ActiveState', '--value', capture=True)
        if state != 'inactive':
            raise ValueError('Execution services must remain stopped during recovery')
    if m.u.pending() or int(m.u.sql("SELECT count(*) FROM overseas_task_deletions WHERE status='deleting'")):
        raise ValueError('Business work appeared before context recovery')
    target_file = work / 'context-targets.json'
    if target_file.is_symlink() or not target_file.is_file():
        raise ValueError('Regular frozen recovery target file required')
    raw_targets = target_file.read_bytes()
    if hashlib.sha256(raw_targets).hexdigest() != (work / 'CONTEXT_TARGETS_SHA256').read_text():
        raise ValueError('Recovery targets changed since prepare')
    targets = json.loads(raw_targets)['conversationIds']
    if not targets or len(targets) != len(set(targets)) or any(str(UUID(value)) != value for value in targets):
        raise ValueError('Explicit unique conversation identities required')
    # Exercise the exact installed filesystem boundaries before touching existing work.
    probe = invoke(target, ['tests/studio_context_probe.py'])
    if len(probe.get('threeRounds', [])) != 3 or not all(
            row.get('derived') and row.get('readonly') and row.get('isolated')
            for row in probe['threeRounds']):
        raise ValueError('Three-round installed sandbox verification failed')
    m.private(work / 'context-sandbox-tests.json', probe)
    results = []
    try:
        for identity in targets:
            args = ['-m', 'app.overseas.studio.restore_context', identity]
            inspected = invoke(target, args)
            m.private(work / ('context-before-' + identity + '.json'), inspected)
            restored = invoke(target, [*args, '--apply', '--expected-digest', inspected['plan']['digest']])
            if restored['sessionId'] != inspected['sessionId']:
                raise ValueError('Conversation session changed during restoration')
            readable = invoke(target, ['tests/studio_context_probe.py', '--conversation', identity,
                '--source-plan-stdin'], source_plan=inspected['plan'])
            if (readable.get('sourceDigest') != inspected['plan']['digest']
                    or readable.get('sourceFilesVerified') != len(inspected['plan']['files'])
                    or readable.get('sourceInputsVerified') != inspected['plan']['inputFiles']):
                raise ValueError('Restored source coverage verification failed')
            if len(readable.get('independentSandboxReads', [])) != 3 or not all(
                    row.get('allHashesMatch') and row.get('readableFiles', 0) > 0
                    for row in readable['independentSandboxReads']):
                raise ValueError('Restored files are not readable through the production sandbox')
            results.append(dict(restored=restored, verification=readable))
            m.private(work / ('context-after-' + identity + '.json'), results[-1])
    except Exception as exc:
        m.private(work / 'CONTEXT_RECOVERY_FAILURE', dict(errorType=type(exc).__name__,
            completed=[value['restored']['conversationId'] for value in results]))
        raise
    m.private(work / 'CONTEXT_RECOVERY_VERIFIED', dict(conversations=targets,
        sessionIds=[value['restored']['sessionId'] for value in results], sandboxReads=3))
