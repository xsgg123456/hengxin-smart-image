from uuid import UUID

import pytest
from sqlalchemy import select, func

from app.execution import codex_runner as runner
from app.models import Job
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionUsage
from app.modules.tasks.models import ImageVersion, RoundRecord
from app.worker import reconcile
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env  # noqa: F401
from test_revisions import revise
from test_tasks import job_for
from intervention_helpers import create_set, scripted_cli


@pytest.mark.parametrize('kind', ['whole_revision', 'single_revision', 'manual_retry'])
def test_user_requested_later_rounds_never_auto_continue(real_env, monkeypatch, kind):
    receipt = create_set(real_env)
    first_outcomes = ('no_delivery', 'no_delivery') if kind == 'manual_retry' else ('success',)
    scripted_cli(monkeypatch, real_env, receipt, first_outcomes)
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    changes = {'target': 0} if kind == 'single_revision' else {}
    if kind == 'manual_retry':
        changes.update(retry=True, sourceRoundId=receipt['roundId'], note='修改文字')
    response = revise(real_env, receipt, **changes)
    assert response.status_code == 202, response.text
    revision = response.json()
    calls = scripted_cli(monkeypatch, real_env, revision, ('no_delivery',))
    runner.run_generation(job_for(real_env[1], revision), real_env[1], real_env[2])
    assert len(calls) == 1 and 'resume' in calls[0]['args']
    with real_env[1]() as session:
        current = session.get(RoundRecord, UUID(revision['roundId']))
        assert current.status == 'failed' and not current.execution_config.get('autoInterventionCount')


def test_text_first_round_is_not_a_template_set(real_env, monkeypatch):
    receipt = create_set(real_env, 'text')
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery',))
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    assert len(calls) == 1


@pytest.mark.parametrize('crash', ['crash_before_events', 'crash_after_delivery'])
def test_recovery_uses_second_process_and_logs_never_replays_cli(real_env, monkeypatch, crash):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery', crash))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'uncertain'
        attempt = session.scalar(select(ExecutionAttempt))
        assert attempt.process_id == 1002 and attempt.workspace == str(calls[1]['control'])
    monkeypatch.setattr(reconcile, 'same_process', lambda *args: True)
    reconcile.reconcile_once(real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'uncertain'
    def stopped(pid, boot, start):
        assert (pid, boot, start) == (1002, 'boot', '102')
        return False
    monkeypatch.setattr(reconcile, 'same_process', stopped)
    reconcile.reconcile_once(real_env[1], real_env[2])
    reconcile.reconcile_once(real_env[1], real_env[2])
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 2
    with real_env[1]() as session:
        success = crash == 'crash_after_delivery'
        assert session.get(Job, job_id).status == ('succeeded' if success else 'uncertain')
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == (2 if success else 0)
        usage = session.get(ExecutionUsage, attempt.id).data
        assert usage['input_tokens'] == (14 if success else 7)


def test_unknown_second_spawn_clears_first_process_evidence(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt)
    execute = runner.execute
    def interrupted(*args):
        if calls:
            raise OSError('lost worker before registering second child')
        return execute(*args)
    monkeypatch.setattr(runner, 'execute', interrupted)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    monkeypatch.setattr(reconcile, 'same_process', lambda *args: False)
    reconcile.reconcile_once(real_env[1], real_env[2])
    with real_env[1]() as session:
        attempt = session.scalar(select(ExecutionAttempt))
        assert session.get(Job, job_id).status == 'uncertain'
        assert attempt.process_id is None and attempt.boot_id is None and attempt.process_start is None
        assert attempt.workspace.endswith('-intervention-1')
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0


def test_cancel_at_intervention_admission_does_not_start_second_child(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery',))
    prepare = runner.prepare_continuation
    def cancelled(*args):
        real_env[0].delete('/api/v1/tasks/' + receipt['taskId'])
        return prepare(*args)
    monkeypatch.setattr(runner, 'prepare_continuation', cancelled)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 1
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'cancelled'


def test_intervention_cannot_silently_change_session(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, ('no_delivery', 'wrong_session'))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert len(calls) == 2
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'failed'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0


def test_intervention_only_receives_remaining_total_time(real_env, monkeypatch):
    receipt = create_set(real_env)
    clock = [0.0]
    monkeypatch.setattr(runner.time, 'monotonic', lambda: clock[0])
    def elapsed(index, stop):
        if index == 0:
            clock[0] = 120.0
    calls = scripted_cli(monkeypatch, real_env, receipt, hook=elapsed)
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    assert [call['timeout'] for call in calls] == [3600, 3480]


def test_storage_failure_does_not_regenerate_images(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = scripted_cli(monkeypatch, real_env, receipt, ('success',))
    def failed(*args):
        raise OSError('store unavailable')
    monkeypatch.setattr(runner, 'save_upload', failed)
    runner.run_generation(job_for(real_env[1], receipt), real_env[1], real_env[2])
    assert len(calls) == 1
