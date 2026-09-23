import pytest

from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.claims import end
from app.modules.tasks.models import RoundRecord
from app.models import Job
from app.worker import reconcile, repair_delivery
from test_execution_reconcile import recovery, final_reply_evidence, state  # noqa: F401
from test_tasks import task_env  # noqa: F401
from files_helpers import files_env  # noqa: F401


def failed(recovery, monkeypatch):
    final_reply_evidence(recovery)
    monkeypatch.setattr(repair_delivery, 'same_process', lambda *a: False)
    with recovery[0].begin() as session:
        end(session, session.get(RoundRecord, recovery[5]), session.get(Job, recovery[2]), 'failed', 'old')
        attempt = session.get(ExecutionAttempt, recovery[7])
        attempt.status, attempt.error = 'finished', 'cli_error'
        attempt.observation = {'failure': {'code': 'CLI_ERROR'}}


def test_backfill_uses_fenced_collection_and_preserves_audit(recovery, monkeypatch):
    failed(recovery, monkeypatch)
    assert repair_delivery.prepare_recollection(recovery[0], recovery[7])['images'] == 1
    reconcile.reconcile_once(recovery[0], recovery[1])
    job, round, attempt, count = state(recovery)
    assert job.status == round.status == 'succeeded' and count == 1
    assert attempt.error is None and attempt.observation['failure'] is None
    assert attempt.observation['recollection']['previousFailure']['code'] == 'CLI_ERROR'
    with pytest.raises(ValueError):
        repair_delivery.prepare_recollection(recovery[0], recovery[7])
    assert state(recovery)[3] == 1


@pytest.mark.parametrize('reason', ['cancelled', 'live', 'missing', 'nonzero', 'generic_error'])
def test_backfill_refuses_invalid_evidence(recovery, monkeypatch, reason):
    failed(recovery, monkeypatch)
    if reason == 'cancelled':
        with recovery[0].begin() as session:
            session.get(RoundRecord, recovery[5]).cancel_requested = True
    elif reason == 'live':
        monkeypatch.setattr(repair_delivery, 'same_process', lambda *a: True)
    elif reason == 'missing':
        (recovery[6] / 'exit.json').unlink()
    elif reason == 'nonzero':
        (recovery[6] / 'exit.json').write_text('{"exit_code":1}')
    else:
        (recovery[6] / 'events.jsonl').write_text('{"type":"error","message":"terminal"}')
    with pytest.raises((ValueError, OSError)):
        repair_delivery.prepare_recollection(recovery[0], recovery[7])
    assert state(recovery)[0].status == 'failed' and state(recovery)[3] == 0
