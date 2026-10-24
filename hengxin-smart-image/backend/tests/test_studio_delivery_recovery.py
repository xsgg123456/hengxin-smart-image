"""One-pass automatic receipt, explicit retry, and stopped-worker recovery."""
from hashlib import sha256
import json

import pytest
from PIL import Image
from sqlalchemy import event

from app.overseas.execution import reconcile, runner
from app.overseas.studio import delivery_context, delivery_snapshot as snapshots, execution
from app.overseas.studio.models import Picture
from app.overseas.tasks.models import ExecutionObject
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas, send, reply_only_process
from studio_receipt_regression_helpers import WorkerInterrupted, interrupted, partial, take, recoverable


def test_one_upload_failure_settles_partial_and_manual_retry_is_idempotent(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path)
    calls = []

    def fail_second(record, data):
        calls.append(record.object_key)
        if len(calls) == 2:
            raise OSError('storage temporarily unavailable')
        case.put(record, data)

    monkeypatch.setattr(case.store, 'put', fail_second)
    case.run()
    partial(case, 3, 2)
    assert [row['sourcePath'] for row in case.current()['pictures']] == ['/work/output0.png', '/work/output2.png']
    assert len(case.downloaded()) == 2 and case.count() == 2
    assert case.count(ExecutionObject) == 3
    before = dict(case.store.data)
    token = case.job().claim_token
    reconcile.reconcile_once(case.factory)  # A settled partial result never auto-retries.
    assert case.job().claim_token == token and case.store.data == before
    monkeypatch.setattr(case.store, 'put', case.put)
    case.recover()
    partial(case, 3, 2)
    selection = recoverable(case)
    saved = take(case, selection)
    assert take(case, selection) == saved
    case.complete()
    assert [p['sourcePath'] for p in case.current()['pictures']] == [f'/work/output{i}.png' for i in range(3)]
    assert len(case.puts) == 3 and len(set(case.puts)) == 3
    before = dict(case.store.data)
    for _ in range(3):
        reconcile.reconcile_once(case.factory)
        case.run()
    case.complete()
    assert case.store.data == before and case.count() == case.count(ExecutionObject) == 3
    assert send(case.client, case.task, key='next-after-partial').status_code == 200


def test_unknown_upload_result_reads_existing_object_without_uploading_again(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)

    def timeout_after_write(record, data):
        case.put(record, data)
        raise TimeoutError('upload response lost')

    monkeypatch.setattr(case.store, 'put', timeout_after_write)
    case.run()
    partial(case, 1, 0)
    assert case.count() == 0
    assert case.count(ExecutionObject) == 1 and len(case.puts) == 1
    before = dict(case.store.data)
    case.recover()
    partial(case, 1, 0)
    take(case)  # The still-failing put proves manual receipt reads the existing bytes.
    case.complete(expected=1)
    assert case.store.data == before and len(case.puts) == 1


def test_database_commit_failure_keeps_uploaded_object_for_recovery(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    failed = []

    def remember_picture_write(session, *_args):
        if any(isinstance(row, Picture) for row in session.new):
            session.info['picture_write'] = True

    def fail_picture_commit(session):
        if not failed and session.info.get('picture_write'):
            failed.append(True)
            raise OSError('database commit unavailable')

    event.listen(case.factory, 'before_flush', remember_picture_write)
    event.listen(case.factory, 'before_commit', fail_picture_commit)
    try:
        case.run()
    finally:
        event.remove(case.factory, 'before_flush', remember_picture_write)
        event.remove(case.factory, 'before_commit', fail_picture_commit)
    assert failed
    partial(case, 1, 0)
    assert case.count() == 0 and case.count(ExecutionObject) == 1
    before = dict(case.store.data)
    case.recover()
    partial(case, 1, 0)
    take(case)
    case.complete(expected=1)
    assert case.store.data == before and len(case.puts) == 1


def test_snapshot_bytes_survive_work_file_overwrite_before_recovery(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)

    def unavailable(*_args):
        raise OSError('storage unavailable')

    monkeypatch.setattr(case.store, 'put', unavailable)
    case.run()
    source = case.workspace.work / 'output0.png'
    original = source.read_bytes()
    assert snapshots.load(case.workspace.control / 'delivery')['ready']
    Image.new('RGB', (24, 24), 'red').save(source)
    assert sha256(source.read_bytes()).digest() != sha256(original).digest()
    monkeypatch.setattr(case.store, 'put', case.put)
    case.recover()
    partial(case, 1, 0)
    take(case)
    case.complete(expected=1)
    assert case.downloaded() == [original]


@pytest.mark.parametrize('boundary', ['receipt_copy', 'exit_state', 'transcript'])
def test_completion_persistence_failure_retains_success_for_reconciliation(studio, monkeypatch, tmp_path, boundary):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    original = runner.execute

    def process(*args):
        receipt = original(*args)
        # Production execute writes exit.json before returning its receipt.
        (args[2] / 'exit.json').write_text(json.dumps(receipt))
        return receipt

    owner, name = {'receipt_copy': (delivery_context, 'exited'),
                   'exit_state': (runner, '_exit'),
                   'transcript': (execution.HANDLER, 'final_poll')}[boundary]
    original_write, failed = getattr(owner, name), []

    def write_failed(*args, **kwargs):
        if not failed:
            failed.append(True)
            raise OSError('completion persistence interrupted')
        return original_write(*args, **kwargs)

    monkeypatch.setattr(runner, 'execute', process)
    with monkeypatch.context() as patch:
        patch.setattr(owner, name, write_failed)
        case.run()
    assert failed
    partial(case, None, 0)
    case.recover()
    partial(case, None, 0)
    take(case, source='work')
    assert case.count() == 1 and len(case.downloaded()) == 1
    assert send(case.client, case.task, key='next-after-persistence-fault').status_code == 200


@pytest.mark.parametrize('boundary', ['before_capture', 'second_snapshot'])
def test_capture_failure_settles_and_manual_receipt_reads_only_remaining_originals(studio, monkeypatch, tmp_path, boundary):
    case = DeliveryCase(studio, monkeypatch, tmp_path)
    name = 'begin' if boundary == 'before_capture' else 'capture'
    original, calls = getattr(snapshots, name), []

    def unavailable(*args, **kwargs):
        calls.append(True)
        if len(calls) == (1 if boundary == 'before_capture' else 2):
            raise OSError('snapshot unavailable')
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(snapshots, name, unavailable)
        case.run()
    expected, saved = (None, 0) if boundary == 'before_capture' else (3, 2)
    partial(case, expected, saved)
    assert len(case.current()['pictures']) == saved
    case.recover()
    partial(case, expected, saved)
    take(case, source='work')
    assert case.count() == 3 and len(case.downloaded()) == 3
    assert len(case.commands) == 1
    assert send(case.client, case.task, key='next-after-capture-fault').status_code == 200


@pytest.mark.parametrize('boundary', ['before_capture', 'second_snapshot'])
def test_worker_crash_recovery_uses_only_captured_bytes_and_never_recaptures(studio, monkeypatch, tmp_path, boundary):
    case = DeliveryCase(studio, monkeypatch, tmp_path)
    name = 'begin' if boundary == 'before_capture' else 'capture'
    original, calls = getattr(snapshots, name), []

    def crash(*args, **kwargs):
        calls.append(True)
        if len(calls) == (1 if boundary == 'before_capture' else 2):
            interrupted()
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(snapshots, name, crash)
        with pytest.raises(WorkerInterrupted):
            case.run()
    assert case.current()['status'] == 'collecting' and case.job().completed_at is None
    assert send(case.client, case.task, key='wait-crashed-worker').status_code == 409
    original_bytes = (case.workspace.work / 'output0.png').read_bytes()
    for source in case.workspace.work.glob('output*.png'):
        source.unlink()
    case.recover()
    expected, saved = (None, 0) if boundary == 'before_capture' else (3, 1)
    partial(case, expected, saved)
    assert case.downloaded() == ([original_bytes] if saved else [])
    assert recoverable(case, source='work') == []
    before = dict(case.store.data)
    for _ in range(2):
        case.recover()
        case.run()
    partial(case, expected, saved)
    assert case.store.data == before and len(case.commands) == 1
    assert send(case.client, case.task, key='next-after-restart').status_code == 200


def test_same_historical_file_is_delivered_in_both_turns_without_image_generation(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    case.run()
    case.complete(expected=1)
    first = case.current()['pictures'][0]
    original = case.downloaded()[0]
    source = case.workspace.work / 'output0.png'
    stat = source.stat()
    reply = '这一张继续给你。\n[下载图片](/work/output0.png)'
    monkeypatch.setattr(runner, 'execute', reply_only_process(case, reply))
    second = send(case.client, case.task, key='redeliver').json()['turns'][-1]
    runner.run(case.factory, second['jobId'])
    turns = case.view()['turns']
    assert [turn['status'] for turn in turns] == ['succeeded', 'succeeded']
    assert [len(turn['pictures']) for turn in turns] == [1, 1]
    latest = turns[1]['pictures'][0]
    assert first['id'] != latest['id'] and first['sourcePath'] == latest['sourcePath']
    assert case.client.get(latest['url']).content == case.client.get(first['url']).content == original
    assert source.stat().st_mtime_ns == stat.st_mtime_ns
    assert len(case.commands) == 2 and len(case.puts) == len(set(case.puts)) == 2
    assert case.count() == case.count(ExecutionObject) == 2


@pytest.mark.parametrize('receipt', [{'exit_code': 1}, {'exit_code': 0, 'reason': 'timeout'}])
def test_recovery_releases_proven_failed_invocation_without_collecting_or_rerunning(studio, monkeypatch, tmp_path, receipt):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    with monkeypatch.context() as patch:
        patch.setattr(snapshots, 'begin', interrupted)
        with pytest.raises(WorkerInterrupted):
            case.run()
    assert case.current()['status'] == 'collecting' and case.job().completed_at is None
    (case.workspace.control / 'delivery-exit.json').write_text(json.dumps(receipt))
    case.recover()
    assert case.current()['status'] == 'failed' and case.count() == 0
    assert len(case.commands) == 1
