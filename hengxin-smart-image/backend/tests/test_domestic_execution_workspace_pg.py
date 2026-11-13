"""Prepare real private workspaces without calling a model."""
from types import SimpleNamespace
from hashlib import sha256
import json
from tempfile import TemporaryDirectory
import tracemalloc
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.domestic_studio import execution_workspace, file_service, turn_service
from app.modules.domestic_studio.models import SkillExecutionReference
from app.modules.domestic_studio.turn_models import Turn, Upload
from app.overseas.studio.schemas import Send
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def test_workspace_uses_frozen_domestic_skill_and_only_owned_inputs(context, tmp_path, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    store = Store()
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    attachment = file_service.upload(factory, store, actor, 'camera', channel, b'owned bytes', '资料.txt')
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel,
                          Send(text='用户的实际要求', attachmentIds=[attachment['id']]), 'send', catalog)
        job_id = session.scalar(select(Turn.job_id))
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    workspace, payload = execution_workspace.prepare(factory, job_id, settings, catalog, store)
    prompt = execution_workspace.prompt(workspace, payload)
    assert workspace.use_skill and workspace.skill_name == skill['name']
    assert prompt.startswith('$' + skill['name'] + '\n\n用户的实际要求')
    assert json.loads((workspace.control / 'input.json').read_text(encoding='utf-8'))['text'] == '用户的实际要求'
    assert '附件文件：' in prompt and '资料.txt' in prompt
    assert any(path.is_file() and path.read_bytes() == b'owned bytes' for path in workspace.inputs_root.rglob('*'))
    assert workspace.home.parent.name == str(channel)


def test_workspace_refuses_changed_skill_pin_before_creating_files(context, tmp_path):
    factory, catalog, skill, actor, _, channel, _ = context
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='处理'), 'send', catalog)
        job_id = session.scalar(select(Turn.job_id))
        session.get(SkillExecutionReference, job_id).checksum = '0' * 64
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    with pytest.raises(ValueError, match='snapshot identity mismatch'):
        execution_workspace.prepare(factory, job_id, settings, catalog, Store())
    assert not (tmp_path / 'execution').exists()


def test_workspace_streams_multiple_large_inputs_with_bounded_memory(context, tmp_path):
    factory, catalog, skill, actor, _, channel, _ = context
    size, block = 64 * 1024 * 1024, b'\0' * (1024 * 1024)
    digest = sha256()
    for _ in range(size // len(block)):
        digest.update(block)
    identities = [uuid4(), uuid4()]
    with factory.begin() as session:
        bind(session, skill['id'])
        for identity in identities:
            session.add(Upload(id=identity, conversation_id=channel, name=f'{identity}.bin',
                content_type='application/octet-stream', size_bytes=size, checksum=digest.hexdigest(),
                bucket='private', object_key=f'test/{identity}', status='ready'))
        session.flush()
        turn_service.send(session, actor, 'camera', channel,
            Send(text='处理', attachmentIds=['upload:' + str(identity) for identity in identities]), 'large', catalog)
        job_id = session.scalar(select(Turn.job_id))

    class Source:
        def __init__(self):
            self.remaining, self.closed, self.released = size, False, False
        def read(self, count):
            assert 0 < count <= 1024 * 1024
            count = min(count, self.remaining)
            self.remaining -= count
            return b'\0' * count
        def close(self):
            self.closed = True
        def release_conn(self):
            self.released = True

    opened = []
    def open_source(_row):
        stream = Source()
        opened.append(stream)
        return stream
    with TemporaryDirectory(dir=tmp_path) as root:
        settings = SimpleNamespace(codex_execution_root=root, codex_auth_file=None)
        tracemalloc.start()
        try:
            workspace, _ = execution_workspace.prepare(factory, job_id, settings, catalog,
                                                        SimpleNamespace(open=open_source))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 16 * 1024 * 1024
        assert len(opened) == 2 and all(stream.closed and stream.released for stream in opened)
        assert sorted(path.stat().st_size for path in workspace.inputs_root.rglob('*') if path.is_file()) == [size, size]
