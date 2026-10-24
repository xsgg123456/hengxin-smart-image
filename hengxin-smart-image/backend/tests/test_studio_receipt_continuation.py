"""Partial receipt releases the chat while preserving the old frozen original."""
from uuid import UUID

from PIL import Image

from app.overseas.execution import runner, reconcile
from app.overseas.execution.models import Job
from app.overseas.tasks.models import ExecutionObject
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas, send, reply_only_process
from studio_receipt_regression_helpers import partial, take


def test_next_turn_runs_after_partial_and_old_snapshot_remains_manually_recoverable(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)

    def unavailable(*_args):
        raise OSError('storage unavailable')

    monkeypatch.setattr(case.store, 'put', unavailable)
    case.run()
    partial(case, 1, 0)
    source = case.workspace.work / 'output0.png'
    original = source.read_bytes()
    process = reply_only_process(case, '已经完成第二轮说明。')

    def overwrite_in_next_turn(*args):
        Image.new('RGB', (24, 24), 'red').save(source)
        return process(*args)

    monkeypatch.setattr(runner, 'execute', overwrite_in_next_turn)
    response = send(case.client, case.task, key='continue-before-receipt')
    assert response.status_code == 200, response.text
    second = response.json()['turns'][-1]
    runner.run(case.factory, second['jobId'])
    assert source.read_bytes() != original
    turns = case.view()['turns']
    assert [turn['status'] for turn in turns] == ['succeeded', 'succeeded']
    assert [turn['deliveryStatus'] for turn in turns] == [
        dict(state='partial', expected=1, saved=0), dict(state='complete', expected=0, saved=0)]
    assert case.view()['activeTurnId'] is None and len(case.commands) == 2

    monkeypatch.setattr(case.store, 'put', case.put)
    saved = take(case)
    assert take(case) == saved
    assert case.downloaded() == [original]
    assert case.current()['deliveryStatus'] == dict(state='complete', expected=1, saved=1)
    assert case.count() == case.count(ExecutionObject) == len(case.puts) == 1
    reconcile.reconcile_once(case.factory)
    case.run()
    with case.factory() as session:
        assert session.get(Job, UUID(second['jobId'])).execution_count == 1
    assert case.job().execution_count == 1 and len(case.commands) == 2
