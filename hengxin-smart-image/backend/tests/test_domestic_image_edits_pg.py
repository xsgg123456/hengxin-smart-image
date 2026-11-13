"""Domestic image edits preserve per-image inputs and conversation privacy."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select

from app.models import Job
from app.modules.domestic_studio import execution_workspace, file_service, turn_service
from app.modules.domestic_studio.turn_models import Picture, Turn
from app.overseas.studio.schemas import Send
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def image(color):
    stream = BytesIO()
    Image.new('RGB', (8, 6), color).save(stream, format='PNG')
    return stream.getvalue()


def previous_pictures(factory, store, actor, channel, colors):
    job_id, turn_id = uuid4(), uuid4()
    identities = [uuid4() for _ in colors]
    with factory.begin() as session:
        session.add(Job(id=job_id, kind='domestic-studio', idempotency_key=str(job_id),
                        payload_hash='a' * 64, value=str(turn_id), status='succeeded'))
        session.flush()
        session.add(Turn(id=turn_id, conversation_id=channel, job_id=job_id, actor_id=actor,
                         text='原始要求', snapshot={'inputs': []}))
        session.flush()
        for index, (identity, color) in enumerate(zip(identities, colors)):
            data = image(color)
            row = Picture(id=identity, turn_id=turn_id, name=f'图片{index + 1}.png',
                          content_type='image/png', size_bytes=len(data), checksum=sha256(data).hexdigest(),
                          bucket='private', object_key=f'picture/{identity}', width=8, height=6)
            session.add(row)
            store.put(row, data)
    return identities


@pytest.mark.parametrize('count', [1, 2])
def test_single_and_batch_edits_reach_private_execution_workspace(context, tmp_path, monkeypatch, count):
    factory, catalog, skill, actor, _, channel, _ = context
    store = Store()
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    originals = [image('red'), image('blue')][:count]
    pictures = previous_pictures(factory, store, actor, channel, ['red', 'blue'][:count])
    marks = [image('green'), image('yellow')][:count]
    mark_ids = [file_service.upload(factory, store, actor, 'camera', channel, data, f'标注{index}.png')['id']
                for index, data in enumerate(marks)]
    reference_data = image('purple')
    reference_id = file_service.upload(factory, store, actor, 'camera', channel, reference_data, '参考.png')['id']
    edits = [dict(pictureId=identity, annotationId=mark_ids[index], text=f'第{index + 1}张的修改',
                  references=[dict(attachmentId=reference_id, kind='effect', note='参考颜色')] if index == 0 else [])
             for index, identity in enumerate(pictures)]
    body = Send(conversationId=channel, attachmentIds=[*mark_ids, reference_id],
                referencePictureIds=pictures, imageEdits=edits)
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, body, 'edit', catalog)
        job_id = session.scalar(select(Turn.job_id).where(Turn.text.like('修改%')))
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    workspace, payload = execution_workspace.prepare(factory, job_id, settings, catalog, store)
    prompt = execution_workspace.prompt(workspace, payload)
    instructions = json.loads(prompt.split('不得跨图套用。\n', 1)[1].split('\n\n附件文件：', 1)[0])
    assert len(instructions) == count
    def sandbox_bytes(path):
        return (workspace.inputs_root / Path(path).relative_to('/work/inputs')).read_bytes()
    for index, item in enumerate(instructions):
        assert item['pictureId'] == str(pictures[index])
        assert item['text'] == f'第{index + 1}张的修改'
        assert sandbox_bytes(item['originalPath']) == originals[index]
        assert sandbox_bytes(item['annotationPath']) == marks[index]
        assert len(item['references']) == (1 if index == 0 else 0)
    assert sandbox_bytes(instructions[0]['references'][0]['path']) == reference_data
    assert instructions[0]['references'][0]['note'] == '参考颜色'


def test_edit_rejects_other_members_pictures_and_annotations(context, monkeypatch):
    factory, catalog, skill, actor, other, channel, other_channel = context
    store = Store()
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    own = previous_pictures(factory, store, actor, channel, ['red'])[0]
    foreign = previous_pictures(factory, store, other, other_channel, ['blue'])[0]
    own_mark = file_service.upload(factory, store, actor, 'camera', channel, image('green'), '标注.png')['id']
    foreign_mark = file_service.upload(factory, store, other, 'camera', other_channel, image('yellow'), '标注.png')['id']
    with factory.begin() as session:
        bind(session, skill['id'])
    for picture_id, annotation_id in ((foreign, own_mark), (own, foreign_mark)):
        body = Send(attachmentIds=[annotation_id], referencePictureIds=[picture_id],
                    imageEdits=[dict(pictureId=picture_id, annotationId=annotation_id, text='调整')])
        with pytest.raises(HTTPException) as error:
            with factory.begin() as session:
                turn_service.send(session, actor, 'camera', channel, body, str(uuid4()), catalog)
        assert error.value.status_code == 404
    with factory() as session:
        assert len(list(session.scalars(select(Job).where(Job.status == 'queued')))) == 0
