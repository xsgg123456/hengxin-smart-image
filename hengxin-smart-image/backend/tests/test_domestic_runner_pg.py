"""Exercise the domestic runner with a fake CLI and private test storage."""
from contextlib import nullcontext
import json
from types import SimpleNamespace

from sqlalchemy import select

from app.capacity.models import CapacityGate, CapacityReservation
from app.models import Job, Outbox
from app.modules.domestic_studio import recovery, runner, runtime, turn_service
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Transcript, Turn
from app.overseas.studio.schemas import Send
from files_helpers import image_bytes
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def prepare(context, database, tmp_path, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    for model in (CapacityGate, CapacityReservation, Transcript, OutputFile):
        model.__table__.create(database)
    settings = SimpleNamespace(enable_codex_executor=True, generation_concurrency=1, job_lease_seconds=30,
        codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=str(tmp_path / 'auth.json'),
        codex_auth_broker_socket='', codex_binary='fake-codex', codex_bwrap_binary='fake-bwrap',
        codex_version='test', worker_node_name='isolated-test', minio_bucket='private')
    monkeypatch.setattr(runtime, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner, 'heartbeat', lambda *args: nullcontext())
    monkeypatch.setattr(runner, 'sync_credentials', lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, 'sandbox_command', lambda _workspace, _binary, args, _bwrap: args)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='codex-cli test'))
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='真实输入'), 'send', catalog)
        identity = session.scalar(select(Turn.job_id))
    return factory, catalog, identity


def fake_cli(calls):
    def run(_command, prompt, control, _timeout, monitor, started):
        calls.append(prompt)
        started(123, 'boot-id', 'birth-id')
        work = control.parents[1] / 'persistent' / 'work'
        (work / 'final.png').write_bytes(image_bytes())
        events = [dict(type='thread.started', thread_id='session-1'),
                  dict(type='item.completed', item=dict(id='reply', type='agent_message', text='![图片](/work/final.png)')),
                  dict(type='turn.completed')]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in events) + '\n', encoding='utf-8')
        (control / 'exit.json').write_text('{"exit_code": 0, "reason": null}', encoding='utf-8')
        assert not monitor()
        return {'exit_code': 0, 'reason': None}
    return run


def test_runner_saves_verified_picture_and_never_repeats_cli(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls, store = [], Store()
    monkeypatch.setattr(runner, 'execute', fake_cli(calls))
    runner.run_turn(str(job_id), factory, store=store, catalog=catalog)
    runner.run_turn(str(job_id), factory, store=store, catalog=catalog)
    assert len(calls) == 1 and '真实输入' in calls[0]
    with factory() as session:
        job = session.get(Job, job_id)
        turn = session.scalar(select(Turn))
        picture = session.scalar(select(Picture))
        assert job.status == 'succeeded' and job.execution_count == 1
        assert turn.reply == '![图片](/work/final.png)' and turn.dispatched
        assert session.get(Outbox, job_id).completed_at is not None
        assert picture and store.objects[(picture.bucket, picture.object_key)] == image_bytes()


def test_ambiguous_process_failure_is_uncertain_and_not_automatically_retried(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls = []
    def failing(_command, _prompt, _control, _timeout, _monitor, started):
        calls.append(1)
        started(123, 'boot-id', 'birth-id')
        raise OSError('simulated interrupted invocation')
    monkeypatch.setattr(runner, 'execute', failing)
    runner.run_turn(job_id, factory, store=Store(), catalog=catalog)
    runner.run_turn(job_id, factory, store=Store(), catalog=catalog)
    assert len(calls) == 1
    with factory() as session:
        job = session.get(Job, job_id)
        assert job.status == 'uncertain' and job.execution_count == 1
        assert session.scalar(select(Turn)).dispatched


def test_failed_file_write_can_be_recovered_without_another_model_call(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(runner, 'execute', fake_cli(calls))
    monkeypatch.setattr(recovery, 'same_process', lambda *_: False)
    monkeypatch.setattr(recovery, 'group_alive', lambda *_: False)
    monkeypatch.setattr(recovery, 'heartbeat', lambda *args: nullcontext())

    store = Store()
    real_deliver = runner.deliver
    def interrupted(*_args, **_kwargs):
        raise OSError('interrupted before file collection')
    monkeypatch.setattr(runner, 'deliver', interrupted)
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    with factory.begin() as session:
        job = session.get(Job, job_id)
        turn = session.scalar(select(Turn))
        assert job.status == 'uncertain' and job.execution_count == 1
        turn_service.request_recovery(session, turn.actor_id, 'camera', turn.conversation_id, turn.id, turn.version)
        assert session.get(Outbox, job_id).completed_at is None
    monkeypatch.setattr(runner, 'deliver', real_deliver)
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    assert len(calls) == 1
    with factory() as session:
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.get(Job, job_id).execution_count == 1
        picture = session.scalar(select(Picture))
        assert picture and store.objects[(picture.bucket, picture.object_key)] == image_bytes()


def test_completed_model_with_storage_failure_keeps_reply_and_allows_manual_receipt(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(runner, 'execute', fake_cli(calls))
    class FailingStore(Store):
        def put(self, row, data):
            raise OSError('temporary storage failure')
    runner.run_turn(job_id, factory, store=FailingStore(), catalog=catalog)
    with factory() as session:
        job = session.get(Job, job_id)
        turn = session.scalar(select(Turn))
        assert job.status == 'partial' and job.execution_count == 1
        assert turn.reply and '取回文件' in turn.error
    assert len(calls) == 1


def test_uncertain_stop_waits_for_original_process_proof(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls = []
    def failing(_command, _prompt, _control, _timeout, _monitor, started):
        calls.append(1)
        started(123, 'boot-id', 'birth-id')
        raise OSError('simulated interrupted invocation')
    monkeypatch.setattr(runner, 'execute', failing)
    runner.run_turn(job_id, factory, store=Store(), catalog=catalog)
    with factory.begin() as session:
        turn = session.scalar(select(Turn))
        turn_service.cancel(session, turn.actor_id, 'camera', turn.conversation_id, turn.id, turn.version)
        assert session.get(Outbox, job_id).completed_at is None
    monkeypatch.setattr(recovery, 'stopped', lambda *_: False)
    runner.run_turn(job_id, factory, store=Store(), catalog=catalog)
    with factory() as session:
        assert session.get(Job, job_id).status == 'uncertain'
    monkeypatch.setattr(recovery, 'stopped', lambda *_: True)
    runner.run_turn(job_id, factory, store=Store(), catalog=catalog)
    assert len(calls) == 1
    with factory() as session:
        assert session.get(Job, job_id).status == 'cancelled'


def test_recovery_does_not_collect_files_while_child_is_alive(monkeypatch):
    monkeypatch.setattr(recovery, 'same_process', lambda *_: False)
    monkeypatch.setattr(recovery, 'group_alive', lambda *_: True)
    def must_not_restore(*_):
        raise AssertionError('files may still be changing')
    monkeypatch.setattr(recovery.delivery_context, 'restore', must_not_restore)
    settings = SimpleNamespace(worker_node_name='test-node', codex_execution_root='unused')
    process = {'node': 'test-node', 'pid': 123, 'boot': 'boot', 'birth': 'birth'}
    assert recovery.recover(None, None, settings, None, {}, process, None)
