"""Output publication verifies frozen bytes and never overwrites another result."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.capacity.models import CapacityGate, CapacityReservation
from app.db.timestamps import utcnow
from app.models import Job
from app.modules.domestic_studio import delivery_capture, execution_workspace, output_store, runtime, turn_service
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Turn
from app.overseas.studio.schemas import Send
from files_helpers import image_bytes
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def test_output_publish_is_retryable_but_cannot_overwrite_frozen_result(context, database, tmp_path, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    for model in (CapacityGate, CapacityReservation, OutputFile):
        model.__table__.create(database)
    monkeypatch.setattr(runtime, 'get_settings', lambda: SimpleNamespace(generation_concurrency=1, job_lease_seconds=30))
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='处理'), 'send', catalog)
        job_id = session.scalar(select(Turn.job_id))
    token = runtime.claim(factory, job_id)
    store = Store()
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    workspace, _ = execution_workspace.prepare(factory, job_id, settings, catalog, store)
    original = image_bytes()
    (workspace.work / 'final.png').write_bytes(original)
    summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1', final_text='![图片](/work/final.png)')
    identity = dict(jobId=str(job_id), taskId=str(actor), turnId=workspace.control.name, conversationId=str(channel))
    _, files, issues = delivery_capture.capture(workspace, summary, identity)
    files = list(files)
    assert not issues and len(files) == 1
    target, data, item = files[0]
    first = output_store.save(factory, job_id, token, store, 'private', target, data, item)
    monkeypatch.setattr(store, 'put', lambda *_: pytest.fail('must not repeat the stored output PUT'))
    assert output_store.save(factory, job_id, token, store, 'private', target, data, item) == first
    with factory() as session:
        record = session.get(Picture, first)
        assert record and record.checksum == data.checksum and record.size_bytes == len(original)
        key = record.bucket, record.object_key
    assert store.objects[key] == original
    changed = replace(data, checksum='a' * 64)
    changed_item = item | {'checksum': changed.checksum, 'sizeBytes': changed.size_bytes}
    with pytest.raises(ValueError, match='identity conflict'):
        output_store.save(factory, job_id, token, store, 'private', target, changed, changed_item)
    assert store.objects[key] == original
    with factory.begin() as session:
        session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
    with pytest.raises(ValueError, match='ownership lost'):
        output_store.save(factory, job_id, token, store, 'private', target, data, item)
