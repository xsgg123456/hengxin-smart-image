"""Exercise actual runner orchestration with a simulated CLI, never bill a model."""
import json
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.execution import codex_runner as runner
from app.execution.output_collector import OutputCollectionError
from files_helpers import files_env  # noqa: F401
from test_tasks import task_env, submit, job_for  # noqa: F401


@pytest.fixture
def observed_run(task_env, tmp_path, monkeypatch):
    settings = get_settings()
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    for key, value in {'enable_fixture_executor': False, 'enable_codex_executor': True,
        'codex_binary': '/test/codex', 'codex_auth_file': str(auth),
        'codex_execution_root': str(tmp_path / 'execution')}.items():
        monkeypatch.setattr(settings, key, value)
    receipt = submit(task_env).json()
    assert 'taskId' in receipt, receipt
    def materials(session, store, task, round, ws):
        return {'mode': task.mode, 'skillPath': '/work/skills/demo/SKILL.md',
                'targets': [{'slot': 0, 'path': '/work/targets/00.png', 'taskSlot': 0}], 'inputs': []}
    monkeypatch.setattr(runner, 'prepare_materials', materials)
    monkeypatch.setattr(runner, 'sandbox_command', lambda *args: ['fake'])
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(a, 0, stdout='codex-cli ' + settings.codex_version))
    def execute(argv, prompt, control, timeout, monitor, on_start):
        on_start(123, 'test-boot', 'test-birth')
        (control / 'events.jsonl').write_text(json.dumps({'type': 'thread.started', 'thread_id': 'test-session'}) +
            '\n' + json.dumps({'type': 'turn.completed'}) + '\n')
        monitor()
        return {'exit_code': 0, 'reason': None, 'elapsed_seconds': 1}
    monkeypatch.setattr(runner, 'execute', execute)
    def invoke():
        runner.run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
        return task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()
    return invoke, receipt, task_env, tmp_path


def test_runner_preserves_skill_failure_before_extra_output_mismatch(observed_run, monkeypatch):
    invoke, receipt, env, root = observed_run
    original = runner.prepare_materials
    def materials(session, store, task, round, ws):
        manifest = original(session, store, task, round, ws)
        (ws.work / 'manifest.json').write_text(json.dumps({'outputs': [{'slot': 0,
            'error': '原生输出1254×1254，与模板800×800不符，禁止缩放修正'}]}))
        return manifest
    monkeypatch.setattr(runner, 'prepare_materials', materials)
    monkeypatch.setattr(runner, 'collect_outputs', lambda *a, **k: pytest.fail('all-failed Skill must retain its diagnosis'))
    view = invoke()
    assert view['status'] == 'failed'
    assert view['failure']['slotErrors'][0]['slot'] == 0
    assert '尺寸' in view['failure']['slotErrors'][0]['message']
    assert view['failure']['stage'] == 'validating'
    assert [e['stage'] for e in view['events']][:3] == ['preparing', 'starting', 'generating']


def test_runner_distinguishes_storage_failure_without_leaking_exception(observed_run, monkeypatch):
    invoke, _, _, _ = observed_run
    monkeypatch.setattr(runner, 'collect_outputs', lambda *a, **k: [object()])
    monkeypatch.setattr(runner, 'verify_provenance', lambda *a: None)
    monkeypatch.setattr(runner, 'save_upload', lambda *a: (_ for _ in ()).throw(OSError('secret password=/private/path')))
    view = invoke()
    assert view['failure']['code'] == 'STORAGE_FAILED' and view['failure']['stage'] == 'storing'
    assert 'secret' not in json.dumps(view) and '/private' not in json.dumps(view)


def test_runner_output_error_is_not_mislabeled_as_storage(observed_run, monkeypatch):
    invoke, _, _, _ = observed_run
    monkeypatch.setattr(runner, 'collect_outputs', lambda *a, **k: (_ for _ in ()).throw(
        OutputCollectionError('invalid_output_manifest')))
    view = invoke()
    assert view['failure']['code'] == 'OUTPUT_MANIFEST_INVALID'
    assert view['failure']['stage'] == 'validating'


def test_pre_attempt_startup_failure_keeps_known_safe_reason(observed_run, monkeypatch):
    invoke, _, _, _ = observed_run
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(a, 1, stdout='secret /private/path'))
    view = invoke()
    assert view['status'] == 'failed' and view['diagnosticId'] is None
    assert view['failure']['code'] == 'STARTUP_FAILED'
    assert view['failure']['stage'] == 'starting'
    assert view['events'] == [] and view['legacy']
    assert 'secret' not in json.dumps(view) and '/private' not in json.dumps(view)
