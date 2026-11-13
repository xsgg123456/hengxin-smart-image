"""One disposable MinIO-to-workspace large-input integration test."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import tracemalloc

import pytest
from sqlalchemy import select

from app.modules.domestic_studio import execution_workspace, file_service, turn_service
from app.modules.domestic_studio.turn_models import Turn
from app.overseas.studio import context_fs
from app.overseas.studio.schemas import Send
from test_domestic_late_outputs_real_minio_pg import storage
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


@pytest.mark.skipif(os.environ.get('TEST_DOMESTIC_MINIO_LARGE') != '1',
                    reason='requires an explicit large-file local MinIO test')
def test_real_minio_to_domestic_workspace_is_bounded(context, database, storage, monkeypatch, tmp_path):
    factory, catalog, skill, actor, _, channel, _ = context
    store, bucket, _, _ = storage
    size = 128 * 1024 * 1024
    with TemporaryDirectory(dir=tmp_path) as root:
        path = Path(root) / 'original.bin'
        with path.open('wb') as stream:
            stream.truncate(size)
        settings = SimpleNamespace(app_env='test', minio_bucket=bucket, codex_execution_root=root, codex_auth_file=None)
        monkeypatch.setattr(file_service, 'get_settings', lambda: settings)
        with path.open('rb') as stream:
            attachment = file_service.upload(factory, store, actor, 'camera', channel, stream, 'original.bin')
        with factory.begin() as session:
            bind(session, skill['id'])
            turn_service.send(session, actor, 'camera', channel,
                              Send(text='处理', attachmentIds=[attachment['id']]), 'large-input', catalog)
            job_id = session.scalar(select(Turn.job_id))
        tracemalloc.start()
        try:
            workspace, payload = execution_workspace.prepare(factory, job_id, settings, catalog, store)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        files = [item for item in workspace.inputs_root.rglob('*') if item.is_file()]
        assert len(files) == 1 and files[0].stat().st_size == size
        assert context_fs.digest(files[0])[0] == payload['inputs'][0]['checksum']
        assert peak < 32 * 1024 * 1024
        print('REAL_WORKSPACE_128M_PEAK_BYTES=' + str(peak), flush=True)
