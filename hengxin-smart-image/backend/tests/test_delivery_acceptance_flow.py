"""Real admission/collection/publication with only CLI and object IO replaced."""
import json
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.execution import codex_runner as runner
from app.models import Job
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.models import ImageVersion
from app.worker import reconcile
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env  # noqa: F401
from test_tasks import job_for
from intervention_helpers import create_set, scripted_cli


def final_call(env, monkeypatch, receipt, path='normal', change=None):
    calls = scripted_cli(monkeypatch, env, receipt,
                         ('no_delivery', 'success') if path == 'intervention' else ('success',))
    execute = runner.execute
    def wrapped(*args):
        result = execute(*args)
        control = calls[-1]['control']
        if path != 'intervention' or len(calls) == 2:
            events = [json.loads(line) for line in (control / 'events.jsonl').read_text().splitlines()]
            if change:
                change(events, result)
            (control / 'events.jsonl').write_text('\n'.join(map(json.dumps, events)), encoding='utf-8')
            (control / 'exit.json').write_text(json.dumps(result))
            if path == 'recovery':
                raise OSError('Worker lost after child stopped')
        return result
    monkeypatch.setattr(runner, 'execute', wrapped)
    monkeypatch.setattr(reconcile, 'same_process', lambda *a: False)
    return calls


@pytest.mark.parametrize('path', ['normal', 'intervention', 'recovery'])
@pytest.mark.parametrize('case', ['reset', 'usage', 'duplicate', 'nonzero', 'reference', 'list'])
def test_valid_delivery_survives_diagnostics_in_every_path(real_env, monkeypatch, path, case):
    receipt = create_set(real_env)
    def mutate(events, result):
        if case == 'reset':
            events.insert(1, {'type': 'error', 'message': 'Reconnecting... 4/5 (stream disconnected before completion: WebSocket protocol error: Connection reset without closing handshake)'})
        elif case == 'usage':
            events[-1]['usage']['new_counter'] = None
        elif case == 'duplicate':
            events.append(events[-1])
        elif case == 'nonzero':
            result['exit_code'] = 1
            events.append({'type': 'error', 'message': 'process teardown failed'})
        else:
            a = '/home/runner/.codex/generated_images/intervention-session/kept-first.png'
            b = '/work/second.png'
            events[-2]['item']['text'] = (
                f'![图片1][a]\n![图片2][b]\n\n[a]: {a}\n[b]: {b}' if case == 'reference'
                else f'1.  成品\n\n    ![图片1]({a})\n\n2.  成品\n\n    ![图片2]({b})')
    calls = final_call(real_env, monkeypatch, receipt, path, mutate)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    reconcile.reconcile_once(real_env[1], real_env[2])
    reconcile.reconcile_once(real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 2
    assert len(calls) == (2 if path == 'intervention' else 1)
    detail = real_env[0].get('/api/v1/tasks/' + receipt['taskId']).json()
    for image in detail['task']['images']:
        assert real_env[0].get(image['url']).status_code == 200


@pytest.mark.parametrize('case', ['unfinished', 'failed', 'missing', 'corrupt', 'mismatch'])
def test_delivery_guards_still_reject(real_env, monkeypatch, case):
    receipt = create_set(real_env, mode='text')  # No automatic intervention.
    def mutate(events, result):
        if case == 'unfinished':
            events.append({'type': 'turn.started'})
        elif case == 'failed':
            events[-1] = {'type': 'turn.failed'}
        elif case == 'missing':
            events[-2]['item']['text'] = '没有成品'
        elif case == 'corrupt':
            events[-2]['item']['text'] = '![图片1](/work/not-there.png)'
        else:
            events.insert(1, {'type': 'thread.started', 'thread_id': 'foreign-session'})
    calls = final_call(real_env, monkeypatch, receipt, change=mutate)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == ('uncertain' if case == 'unfinished' else 'failed')
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0
    assert len(calls) == 1
