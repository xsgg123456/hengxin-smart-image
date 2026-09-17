"""Exercise real admission/materials/persistence; replace only CLI and object I/O."""
import hashlib
import base64
import json
from datetime import timedelta
from io import BytesIO
from uuid import UUID
from zipfile import ZipFile
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.execution import codex_runner as runner
from app.models import Job, utcnow
from app.modules.skills.models import SkillVersionRecord
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.modules.tasks.claims import sweep_expired
from app.modules.tasks.models import ExecutionGate, ImageVersion
from files_helpers import files_env, image_bytes, ObjectStream
from test_tasks import body, submit, job_for


def repaired_image_bytes():
    buffer = BytesIO()
    Image.new('RGB', (8, 6), '#abcdef').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def real_env(files_env, monkeypatch, tmp_path):
    settings = get_settings()
    auth = tmp_path / 'auth.json'
    auth.write_text('{"test": true}')
    for key, value in dict(enable_codex_executor=True, enable_fixture_executor=False, codex_version='0.153.4',
                           codex_execution_root=str(tmp_path / 'execution'),
                           codex_auth_file=str(auth)).items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(ObjectStream, 'read', lambda self, size: self.data[:size], raising=False)
    # The OS isolation boundary is independently exercised on Linux, not simulated here.
    monkeypatch.setattr(runner, 'sandbox_command', lambda workspace, binary, args, bwrap: args)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stdout='codex-cli 0.153.4\n'))
    with files_env[1].begin() as session:
        session.add(ExecutionGate(id=1))
    return files_env


def frozen_request(env, data=None):
    data = data or body(env)
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        archive.writestr('SKILL.md', '---\nname: test\ndescription: test\n---\nEdit image.')
    raw = buffer.getvalue()
    with env[1].begin() as session:
        version = session.get(SkillVersionRecord, UUID(data['skillVersionId']))
        version.version = '1.0.0'
        version.checksum = hashlib.sha256(raw).hexdigest()
        env[2].objects[version.object_key] = raw
    response = submit(env, data)
    assert response.status_code == 202, response.text
    return response.json()


def cli(monkeypatch, env, receipt, *, image=True, reason=None, during=None, crash=False):
    calls = []
    def execute(argv, prompt, control, timeout, should_stop, on_start):
        calls.append((argv, timeout))
        assert argv[argv.index('--model') + 1] == 'gpt-6-astra'
        assert argv[argv.index('-c') + 1] == 'model_reasoning_effort="high"'
        assert '/work/targets/00.png' in prompt
        assert prompt.startswith('使用 $') and '后台结果交付规则' not in prompt
        work = control.parents[1] / 'rounds' / receipt['roundId']
        assert list((work / 'skills').glob('*/SKILL.md'))
        assert json.loads((control / 'delivery.json').read_text()) == {'version': 'final-reply-v1'}
        on_start(1234, 'test-boot', '99')
        if during:
            during()
            assert should_stop()
        if crash:
            raise OSError('lost CLI boundary')
        session_id = 'test-session'
        events = [
            {'type': 'thread.started', 'thread_id': session_id},
        ]
        if image:
            output = control.parents[1] / 'home' / '.codex' / 'generated_images' / session_id
            output.mkdir(parents=True)
            (output / 'exec-new.png').write_bytes(image_bytes())
            logs = output.parent.parent / 'sessions' / '2026' / '09' / '10'
            logs.mkdir(parents=True)
            payloads = [{'type': 'task_started', 'turn_id': 't1'},
                {'type': 'item_completed', 'thread_id': session_id, 'turn_id': 't1', 'item': {
                    'type': 'Extension', 'kind': 'image_gen.generation', 'id': 'exec-new',
                    'status': 'completed', 'failure': None,
                    'savedPath': f'/home/runner/.codex/generated_images/{session_id}/exec-new.png',
                    'result': base64.b64encode(image_bytes()).decode()}}]
            (logs / f'rollout-test-{session_id}.jsonl').write_text(''.join(
                json.dumps({'type': 'event_msg', 'payload': value}) + '\n' for value in payloads))
            # The delivered image is a repaired file, not the native candidate.
            (work / 'final.png').write_bytes(repaired_image_bytes())
            events.append({'type': 'item.completed', 'item': {'type': 'agent_message',
                'text': '![主图1](/work/final.png)'}})
        events.append({'type': 'turn.completed', 'usage': {'input_tokens': 7, 'output_tokens': 2}})
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return {'exit_code': 0 if not reason else -15, 'reason': reason}
    monkeypatch.setattr(runner, 'execute', execute)
    return calls


def test_real_admission_frozen_timeout_session_usage_and_result(real_env, monkeypatch):
    receipt = frozen_request(real_env)
    calls = cli(monkeypatch, real_env, receipt)
    job_id = job_for(real_env[1], receipt)
    monkeypatch.setattr(get_settings(), 'codex_timeout_seconds', 10)
    runner.run_generation(job_id, real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 1 and calls[0][1] == 3600
    with real_env[1]() as session:
        attempt = session.scalar(select(ExecutionAttempt))
        assert attempt.status == 'finished' and attempt.process_id == 1234
        assert session.get(ExecutionSession, UUID(receipt['taskId'])).session_id == 'test-session'
        assert session.get(ExecutionUsage, attempt.id).data == {'input_tokens': 7, 'output_tokens': 2}
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.scalar(select(ImageVersion)) is not None
    response = real_env[0].get('/api/v1/tasks/' + receipt['taskId'])
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail['task']['executionSource'] == 'cli'
    for result in detail['task']['images']:
        assert real_env[0].get(result['url']).status_code == 200


def test_revision_explicitly_pins_model_and_effort(real_env, monkeypatch):
    from test_revisions import revise
    receipt = frozen_request(real_env)
    cli(monkeypatch, real_env, receipt)
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    response = revise(real_env, receipt)
    assert response.status_code == 202, response.text
    revision = response.json()
    calls = cli(monkeypatch, real_env, revision, image=False)
    runner.run_generation(job_for(real_env[1], revision), real_env[1], real_env[2])
    assert len(calls) == 1
    assert 'resume' in calls[0][0] and 'test-session' in calls[0][0]
    assert calls[0][0].index('--model') > calls[0][0].index('resume')
    assert calls[0][0][calls[0][0].index('--model') + 1] == 'gpt-6-astra'
    assert calls[0][0][calls[0][0].index('-c') + 1] == 'model_reasoning_effort="high"'


@pytest.mark.parametrize('outcome,expected', [('no_image', 'failed'), ('timeout', 'failed'),
                                            ('unknown', 'uncertain'), ('cancel', 'cancelled'),
                                            ('expired', 'uncertain')])
def test_failed_unknown_and_cancelled_invocations_never_publish(real_env, monkeypatch, outcome, expected):
    receipt = frozen_request(real_env)
    job_id = job_for(real_env[1], receipt)
    def during():
        if outcome == 'cancel':
            assert real_env[0].delete('/api/v1/tasks/' + receipt['taskId']).status_code == 200
        else:
            with real_env[1].begin() as session:
                session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
            sweep_expired(real_env[1])
    calls = cli(monkeypatch, real_env, receipt, image=outcome != 'no_image',
                reason='timeout' if outcome == 'timeout' else None,
                crash=outcome == 'unknown', during=during if outcome in ('cancel', 'expired') else None)
    runner.run_generation(job_id, real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 1
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == expected
        assert session.scalar(select(ImageVersion)) is None
        if outcome == 'timeout':
            assert session.scalar(select(ExecutionAttempt)).error == 'timeout'


@pytest.mark.parametrize('overrides', [dict(enable_fixture_executor=True),
    dict(codex_binary=''), dict(codex_auth_file=''), dict(queue_visibility_seconds=3600)])
def test_real_executor_rejects_unsafe_configuration(overrides):
    config = dict(enable_codex_executor=True, enable_fixture_executor=False,
                  codex_binary='/opt/codex', codex_auth_file='/private/auth.json')
    with pytest.raises(ValueError):
        Settings(**(config | overrides))


def test_corrupt_frozen_skill_prevents_cli_launch(real_env, monkeypatch):
    receipt = frozen_request(real_env)
    with real_env[1]() as session:
        version = session.scalar(select(SkillVersionRecord))
        real_env[2].objects[version.object_key] = b'tampered'
    calls = cli(monkeypatch, real_env, receipt)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert calls == []
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'failed'
        assert session.scalar(select(ExecutionAttempt)).process_id is None
        assert session.scalar(select(ImageVersion)) is None
