import json
from uuid import UUID

import pytest
from sqlalchemy import select, func

from app.execution import codex_runner as runner
from app.execution.intervention import PROMPT
from app.models import Job, utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.modules.tasks.models import RoundRecord, ImageVersion
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env  # noqa: F401
from test_tasks import job_for
from intervention_helpers import create_set, scripted_cli


@pytest.mark.parametrize('failure', ['no_delivery', 'incomplete', 'invalid_file', 'network', 'nonzero'])
def test_first_set_continues_once_with_same_session_files_and_baseline(real_env, monkeypatch, failure):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, (failure, 'success'))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 2
    assert 'resume' not in calls[0]['args']
    assert calls[1]['args'][calls[1]['args'].index('resume') + 3] == 'intervention-session'
    assert calls[1]['prompt'] == PROMPT
    assert calls[0]['control'] != calls[1]['control']
    assert calls[0]['control'].parent == calls[1]['control'].parent
    assert 0 < calls[1]['timeout'] <= calls[0]['timeout'] == 3600
    for call in calls:
        assert json.loads((call['control'] / 'baseline.json').read_text()) == {}
        assert (call['control'] / 'events.jsonl').exists()
    with real_env[1]() as session:
        attempt = session.scalar(select(ExecutionAttempt))
        assert session.scalar(select(func.count()).select_from(ExecutionAttempt)) == 1
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.get(Job, job_id).execution_count == 1
        assert session.get(RoundRecord, UUID(receipt['roundId'])).execution_config['autoInterventionCount'] == 1
        assert attempt.process_id == 1002 and attempt.workspace == str(calls[1]['control'])
        assert session.get(ExecutionUsage, attempt.id).data == {'input_tokens': 14, 'output_tokens': 4}
        assert session.get(ExecutionSession, UUID(receipt['taskId'])).session_id == 'intervention-session'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 2
    view = real_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()
    assert any('自动继续处理（1/1）' in e['message'] for e in view['events'])


def test_second_failure_ends_without_third_invocation(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery', 'no_delivery'))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 2
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'failed'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0


@pytest.mark.parametrize('outcome', ['success', 'auth', 'quota', 'limited', 'chinese_quota',
                                    'stderr_quota', 'missing_session', 'timeout', 'crash_before_events', 'session_change'])
def test_non_intervention_cases_do_not_launch_again(real_env, monkeypatch, outcome):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, (outcome,))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 1
    with real_env[1]() as session:
        expected = 'succeeded' if outcome == 'success' else 'uncertain' if outcome == 'crash_before_events' else 'failed'
        assert session.get(Job, job_id).status == expected
        assert not session.get(RoundRecord, UUID(receipt['roundId'])).execution_config.get('autoInterventionCount')


@pytest.mark.parametrize('action', ['cancel', 'expire', 'exhaust_budget'])
def test_cancellation_lease_loss_and_total_budget_block_continuation(real_env, monkeypatch, action):
    from datetime import timedelta
    from app.modules.tasks.claims import sweep_expired
    receipt = create_set(real_env)
    job_id = job_for(real_env[1], receipt)
    clock = [10.0]
    monkeypatch.setattr(runner.time, 'monotonic', lambda: clock[0])
    def hook(index, stop):
        if action == 'cancel':
            assert real_env[0].delete('/api/v1/tasks/' + receipt['taskId']).status_code == 200
            assert stop()
        elif action == 'expire':
            with real_env[1].begin() as session:
                session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
            sweep_expired(real_env[1])
            assert stop()
        else:
            clock[0] += 3601
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery',), hook)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 1
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == {'cancel': 'cancelled', 'expire': 'uncertain', 'exhaust_budget': 'failed'}[action]
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0
