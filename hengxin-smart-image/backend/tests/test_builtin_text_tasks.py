"""New text tasks: real routes, persistence, materials and runner; no paid CLI."""
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.execution import codex_runner as runner, text_prompt
from app.execution.prompts import prompt_for
from app.modules.skills.models import SkillRecord
from app.modules.tasks.models import TaskRecord, RoundRecord, TaskSource, ResultSlotRecord
from app.resource_models import FileRecord, UserRecord
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env, repaired_image_bytes  # noqa: F401
from test_files import upload
from test_single_revision_materials import prepared
from test_tasks import task_env, submit, job_for  # noqa: F401


def text_input(env, annotation=False):
    data = dict(mode='text', name='标题改字', sources=[upload(env[0]).json()],
                note='将防窥钢化膜改成张帅钢化膜，保留28°')
    if annotation:
        data['annotationFileId'] = upload(env[0]).json()['fileId']
    return data


@pytest.mark.parametrize('annotation', [False, True])
def test_create_freezes_no_skill_prompt_and_distinct_annotation(task_env, tmp_path, monkeypatch, annotation):
    data = text_input(task_env, annotation)
    response = submit(task_env, data)
    assert response.status_code == 202, response.text
    receipt = response.json()
    assert submit(task_env, data).json() == receipt
    assert submit(task_env, {**data, 'annotationFileId': str(uuid4())}).status_code == 409
    with task_env[1]() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        assert task.skill_version_id is None and task.skill_snapshot == {}
        assert task.builtin_prompt == text_prompt.snapshot()
        assert session.scalar(select(SkillRecord)) is None
        assert len(session.scalars(select(TaskSource)).all()) == 1
        assert len(session.scalars(select(ResultSlotRecord)).all()) == 1
    # Later deployments must not rewrite a pending task's system instructions.
    monkeypatch.setattr(text_prompt, 'INSTRUCTIONS', 'new deployment instructions')
    manifest, work = prepared(task_env, receipt, tmp_path, monkeypatch)
    prompt = prompt_for(manifest, data['note'])
    assert 'new deployment instructions' not in prompt
    assert '字距、行距' in prompt and '图片尺寸保持不变' in prompt
    assert '/work/targets/00.png' in prompt and data['note'] in prompt
    assert ('/work/annotation/reference.png' in prompt) == annotation
    assert manifest['inputs'] == [] and 'skillPath' not in manifest
    assert not (work / 'skills').exists()
    detail = task_env[0].get('/api/v1/tasks/' + receipt['taskId']).json()
    assert not detail['task'].get('skillSnapshot') and not detail['task'].get('skillVersionId')
    assert bool(detail['rounds'][0].get('annotation')) == annotation
    assert task_env[0].get('/api/v1/tasks?mode=text').json()['total'] == 1


@pytest.mark.parametrize('fault', ['two_originals', 'no_note', 'bad_id', 'missing', 'failed',
                                   'deleted', 'foreign_owner', 'too_large', 'wrong_type'])
def test_create_validates_original_and_annotation(task_env, fault):
    data = text_input(task_env, True)
    if fault == 'two_originals':
        data['sources'] *= 2
    elif fault == 'no_note':
        data['note'] = ' '
    elif fault in ('bad_id', 'missing'):
        data['annotationFileId'] = 'invalid' if fault == 'bad_id' else str(uuid4())
    else:
        from app.models import utcnow
        with task_env[1].begin() as session:
            file = session.get(FileRecord, UUID(data['annotationFileId']))
            if fault == 'failed':
                file.status = 'failed'
            elif fault == 'deleted':
                file.deleted_at = utcnow()
            elif fault == 'too_large':
                file.size_bytes = 11 * 1024**2
            elif fault == 'wrong_type':
                file.content_type = 'text/plain'
            else:
                other = UserRecord(id=uuid4(), name='他人', role='operator', status='active', identity_source='development')
                session.add(other)
                file.owner_id = other.id
    response = submit(task_env, data)
    assert response.status_code == (403 if fault == 'foreign_owner' else 422), response.text
    with task_env[1]() as session:
        assert session.scalar(select(TaskRecord)) is None


def mock_text_cli(monkeypatch, receipt, *, revised=False):
    def sandbox(workspace, binary, args, bwrap):
        assert workspace.use_skill is False
        assert workspace.local_skill is None
        assert not (workspace.work / 'skills').exists()
        return args

    def execute(args, prompt, control, timeout, stop, start):
        assert '使用 $' not in prompt and '字体风格' in prompt
        assert ('resume' in args) == revised
        assert ('/work/current/00.png' in prompt) == revised
        assert '/work/annotation/reference.png' in prompt
        start(123, 'boot', 'birth')
        work = control.parents[1] / 'rounds' / receipt['roundId']
        (work / 'final.png').write_bytes(repaired_image_bytes())
        history = control.parents[1] / 'home' / '.codex' / 'sessions'
        history.mkdir(exist_ok=True)
        (history / 'rollout-text-session.jsonl').touch()
        events = [{'type': 'thread.started', 'thread_id': 'text-session'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message',
                   'text': '![成品](/work/final.png)'}}, {'type': 'turn.completed'}]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return {'exit_code': 0, 'reason': None}
    monkeypatch.setattr(runner, 'sandbox_command', sandbox)
    monkeypatch.setattr(runner, 'execute', execute)


def test_real_orchestration_accepts_new_text_and_same_session_revision(real_env, monkeypatch):
    data = text_input(real_env, True)
    receipt = submit(real_env, data).json()
    mock_text_cli(monkeypatch, receipt)
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    path = '/api/v1/tasks/' + receipt['taskId']
    detail = real_env[0].get(path).json()
    assert detail['task']['state'] == '待查看', detail
    version = detail['slots'][0]['versions'][0]
    body = dict(taskId=receipt['taskId'], target=0, note='仅改标题',
                baseVersionId=version['id'], annotationFileId=data['annotationFileId'])
    response = real_env[0].post(path + '/rounds', json=body, headers={'Idempotency-Key': 'revise'})
    assert response.status_code == 202, response.text
    revised = response.json()
    mock_text_cli(monkeypatch, revised, revised=True)
    runner.run_generation(job_for(real_env[1], revised), real_env[1], real_env[2])
    after = real_env[0].get(path).json()
    assert after['task']['state'] == '待查看', after
    assert len(after['slots'][0]['versions']) == 2
    assert after['task']['sessionId'] == 'text-session'


def test_failed_initial_retry_keeps_annotation_and_frozen_prompt(real_env, monkeypatch, tmp_path):
    data = text_input(real_env, True)
    receipt = submit(real_env, data).json()
    # A material read fails before spawning, allowing a known-safe retry.
    real_env[2].fail_open = True
    monkeypatch.setattr(runner, 'execute', lambda *args: pytest.fail('must not launch'))
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    real_env[2].fail_open = False
    body = dict(taskId=receipt['taskId'], target=None, retry=True,
                sourceRoundId=receipt['roundId'], note=data['note'], annotationFileId=data['annotationFileId'])
    path = '/api/v1/tasks/' + receipt['taskId'] + '/rounds'
    bad = {**body, 'annotationFileId': None}
    assert real_env[0].post(path, json=bad, headers={'Idempotency-Key': 'bad'}).status_code == 409
    response = real_env[0].post(path, json=body, headers={'Idempotency-Key': 'retry'})
    assert response.status_code == 202, response.text
    manifest, _ = prepared(real_env, response.json(), tmp_path, monkeypatch)
    assert manifest['annotationFileId'] == data['annotationFileId']
    assert manifest['builtinPrompt'] == text_prompt.snapshot()
