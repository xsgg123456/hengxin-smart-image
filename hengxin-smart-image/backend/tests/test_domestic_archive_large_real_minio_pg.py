"""Confirm large archived attachments use bounded memory with real MinIO."""
import asyncio
from hashlib import sha256
from datetime import timedelta
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tracemalloc
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.capacity.models import CapacityGate, CapacityReservation
from app.db.timestamps import utcnow
from app.execution.workspace import prepare_workspace
from app.models import Job
from app.modules.domestic_studio import archive_router, archive_service
from app.modules.domestic_studio import delivery_context, runner, turn_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveFile
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Transcript, Turn, Upload
from app.overseas.studio import context_workspace
from app.overseas.studio.schemas import Send
from test_domestic_archive_pg import setup_archive
from test_domestic_late_outputs_real_minio_pg import storage
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


@pytest.mark.skipif(os.environ.get('TEST_DOMESTIC_MINIO_LARGE') != '1',
                    reason='requires an explicit large-file local MinIO test')
def test_large_archive_copy_streams_without_buffering_the_entire_attachment(context, database, tmp_path, monkeypatch, storage):
    factory, fake, actor, _, channel = setup_archive(context, database, monkeypatch)
    store, bucket, _, _ = storage
    for (_, key), raw in fake.objects.items():
        store.put(SimpleNamespace(bucket=bucket, object_key=key, content_type='application/octet-stream'), raw)
    path, size = tmp_path / 'large-archive.bin', 128 * 1024 * 1024
    with path.open('wb') as handle:
        handle.truncate(size)
    digest = sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    with factory.begin() as session:
        attachment = session.scalar(select(Upload))
        for model in (Upload, Picture):
            for row in session.scalars(select(model)):
                row.bucket = bucket
        attachment.size_bytes, attachment.checksum = size, digest.hexdigest()
        target = SimpleNamespace(bucket=bucket, object_key=attachment.object_key, content_type='application/octet-stream')
        with path.open('rb') as handle:
            store.put_stream(target, handle, size)
        archive_id = archive_service.prepare(session, actor, 'camera', channel,
            archive_service.ArchiveInput(productName='大文件'), 'archive-large').id
    tracemalloc.start()
    try:
        archive_service.complete(factory, store, archive_id, actor)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 96 * 1024 * 1024
    with factory() as session:
        assert session.get(Archive, archive_id).status == 'ready'
        attachment = next(row for row in session.scalars(
            select(ArchiveFile).where(ArchiveFile.archive_id == archive_id)) if row.size_bytes == size)
        attachment_id = attachment.id
    request = Request({'type': 'http', 'method': 'GET', 'headers': []})
    with factory() as session:
        tracemalloc.start()
        try:
            response = archive_router.content(archive_id, attachment_id, request, SimpleNamespace(id=actor),
                                              session, store=store)
            _, download_peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert download_peak < 32 * 1024 * 1024
    actual = sha256()
    async def consume():
        async for chunk in response.body_iterator:
            actual.update(chunk)
    try:
        asyncio.run(consume())
    finally:
        response.stream.close()
    assert actual.hexdigest() == digest.hexdigest()


@pytest.mark.skipif(os.environ.get('TEST_DOMESTIC_MINIO_LARGE') != '1',
                    reason='requires an explicit large-file local MinIO test')
def test_large_generated_file_is_delivered_to_real_minio_with_bounded_memory(context, database, tmp_path, monkeypatch, storage):
    store, bucket, _, _ = storage
    factory, catalog, skill, actor, _, channel, _ = context
    for model in (CapacityGate, CapacityReservation, Transcript, OutputFile):
        model.__table__.create(database)
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='处理'), 'large-output', catalog)
        turn = session.scalar(select(Turn))
        job = session.get(Job, turn.job_id)
        token = uuid4()
        job.status, job.claim_token, job.lease_until = 'running', token, utcnow() + timedelta(seconds=300)
        job_id, turn_id = job.id, turn.id
    with TemporaryDirectory(dir=tmp_path) as root:
        workspace = prepare_workspace(Path(root), channel, turn_id, None, copy_auth=False)
        context_workspace.prepare(workspace, [], [], lambda _: pytest.fail('unexpected input'))
        size, source = 64 * 1024 * 1024, workspace.work / 'large.bin'
        with source.open('wb') as handle:
            handle.truncate(size)
        summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1',
                                  final_text='[结果](/work/large.bin)')
        monkeypatch.setattr(delivery_context, 'success', lambda _: summary)
        monkeypatch.setattr(runner, 'close_native', lambda *_: None)
        owner = delivery_context.identity(job_id, actor, channel, turn_id)
        tracemalloc.start()
        try:
            assert runner.deliver(factory, job_id, token, workspace, owner, store,
                                  SimpleNamespace(minio_bucket=bucket))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 96 * 1024 * 1024
        with factory() as session:
            output = session.scalar(select(OutputFile))
            assert output and output.size_bytes == size and session.get(Job, job_id).status == 'succeeded'
            assert store.client.stat_object(bucket, output.object_key).size == size
