"""Archived edit history must remain useful after its private source is deleted."""
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_session
from app.main import app
from app.models import Job
from app.modules.auth.dependencies import get_identity_id
from app.modules.domestic_studio import (archive_edits, archive_queries, archive_service, conversation_cleanup,
                                         conversation_deletion, file_service, turn_service)
from app.modules.domestic_studio.archive_models import Archive
from app.modules.domestic_studio.conversation_models import Conversation
from app.modules.domestic_studio.turn_models import Picture, Transcript, Turn
from app.overseas.studio.schemas import Send
from app.overseas.tasks import cleanup_files
from app.storage.minio_store import get_store
from test_domestic_archive_pg import setup_archive
from test_domestic_image_edits_pg import image
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


def prepared(context, database, monkeypatch):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    catalog = context[1]
    with factory.begin() as session:
        first_picture = session.scalar(select(Picture.id))
        first_turn = session.scalar(select(Turn.id))
        data, identity = image('blue'), uuid4()
        second_picture = Picture(id=identity, turn_id=first_turn, name='第二张.png', content_type='image/png',
            size_bytes=len(data), checksum=sha256(data).hexdigest(), bucket='private',
            object_key=f'domestic-studio/outputs/{first}/camera/{channel}/{first_turn}/{identity}', width=8, height=6)
        store.put(second_picture, data)
        session.add(second_picture)
    marks = [image('green'), image('yellow')]
    examples = [image('purple'), image('orange')]
    mark_ids = [file_service.upload(factory, store, first, 'camera', channel, data, f'标注{i}.png')['id']
                for i, data in enumerate(marks)]
    ref_ids = [file_service.upload(factory, store, first, 'camera', channel, data, f'参考{i}.png')['id']
               for i, data in enumerate(examples)]
    body = Send(attachmentIds=[*mark_ids, *ref_ids], referencePictureIds=[first_picture, identity],
        imageEdits=[dict(pictureId=first_picture, annotationId=mark_ids[0], text='修改第一张',
                         references=[dict(attachmentId=ref_ids[0], kind='custom',
                                          customPurpose='背景材质', note='参考纹理')]),
                    dict(pictureId=identity, annotationId=mark_ids[1], text='修改第二张',
                         references=[dict(attachmentId=ref_ids[1], kind='effect', note='参考灯光')])])
    with factory.begin() as session:
        turn_service.send(session, first, 'camera', channel, body, 'edit', catalog)
        turn = session.scalar(select(Turn).where(Turn.text.like('修改%')))
        turn.reply = '修改完成'
        session.get(Job, turn.job_id).status = 'succeeded'
        session.add_all([
            Transcript(turn_id=turn.id, item_id='source-private-progress', kind='message', text='旧进度', state='running'),
            Transcript(turn_id=turn.id, item_id='source-private-progress', kind='message', text='中途公开消息', state='completed'),
            Transcript(turn_id=turn.id, item_id='source-private-final', kind='message', text='修改完成', state='completed'),
        ])
    with factory.begin() as session:
        archive_id = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='归档测试'), 'archive').id
    archive_service.complete(factory, store, archive_id, first)
    return factory, store, first, second, channel, archive_id, marks, examples, [first_picture, identity], mark_ids + ref_ids


def test_archived_batch_edits_are_shared_after_source_is_deleted(context, database, monkeypatch, tmp_path):
    factory, store, first, second, channel, archive_id, marks, examples, old_pictures, old_uploads = prepared(
        context, database, monkeypatch)
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private',
                               worker_node_name='test-worker')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    with factory.begin() as session:
        conversation_deletion.request(session, first, 'camera', channel, session.get(Conversation, channel).version)
    assert conversation_cleanup.process(factory, store, channel)
    with factory() as session:
        assert session.get(Conversation, channel) is None

    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: second
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.get(f'/api/v1/domestic-studio/archives/{archive_id}')
            assert response.status_code == 200
            turn = next(row for row in response.json()['turns'] if row['imageEdits'])
            assert turn['status'] == 'succeeded' and turn['error'] is None
            assert [entry['text'] for entry in turn['transcript']] == ['旧进度', '中途公开消息', '修改完成']
            assert [entry['itemId'] for entry in turn['transcript']] == ['event-1', 'event-1', 'event-2']
            assert 'source-private' not in str(turn['transcript'])
            assert len(turn['imageEdits']) == 2
            assets = {'upload:' + item['id']: item for item in turn['attachments']}
            pictures = {item['id']: item for item in turn['referencePictures']}
            for index, edit in enumerate(turn['imageEdits']):
                assert edit['pictureId'] in pictures and UUID(edit['pictureId']) not in old_pictures
                assert edit['annotationId'] not in old_uploads and edit['text'] == ['修改第一张', '修改第二张'][index]
                assert client.get(assets[edit['annotationId']]['url']).content == marks[index]
                reference = edit['references'][0]
                assert reference['attachmentId'] not in old_uploads
                assert client.get(assets[reference['attachmentId']]['url']).content == examples[index]
                assert reference['note'] == ['参考纹理', '参考灯光'][index]
            assert turn['imageEdits'][0]['references'][0]['customPurpose'] == '背景材质'
            assert [item['references'][0]['kind'] for item in turn['imageEdits']] == ['custom', 'effect']
            for source in old_pictures:
                assert client.get(f'/api/v1/domestic-studio/workspaces/camera/pictures/{source}/content').status_code == 404
    finally:
        for dependency in (get_session, get_identity_id, get_store):
            app.dependency_overrides.pop(dependency, None)


def test_archive_rejects_forged_or_unreferenced_edit_files(context, database, monkeypatch):
    factory, _, _, _, _, archive_id, *_ = prepared(context, database, monkeypatch)
    with factory.begin() as session:
        record = session.get(Archive, archive_id)
        snapshot = dict(record.snapshot)
        turns = [dict(turn) for turn in snapshot['turns']]
        turn = next(turn for turn in turns if turn['imageEdits'])
        edits = [dict(edit) for edit in turn['imageEdits']]
        edits[0]['pictureId'] = str(uuid4())
        turn['imageEdits'] = edits
        snapshot['turns'] = turns
        snapshot['checksum'] = archive_service.seal({'turns': turns, 'files': snapshot['files']})
        record.snapshot = snapshot
    with factory() as session, pytest.raises(HTTPException) as error:
        archive_queries.detail(session, archive_id)
    assert error.value.status_code == 503


def test_legacy_archive_without_image_edit_field_remains_readable(context, database, monkeypatch):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        archive_id = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='旧归档'), 'legacy').id
    archive_service.complete(factory, store, archive_id, first)
    with factory.begin() as session:
        record = session.get(Archive, archive_id)
        snapshot = dict(record.snapshot)
        turns = [{key: value for key, value in turn.items() if key not in ('imageEdits', 'status', 'error')}
                 for turn in snapshot['turns']]
        snapshot['turns'] = turns
        snapshot['checksum'] = archive_service.seal({'turns': turns, 'files': snapshot['files']})
        record.snapshot = snapshot
    with factory() as session:
        turn = archive_queries.detail(session, archive_id)['turns'][0]
        assert turn['imageEdits'] == [] and turn['status'] is None and turn['error'] is None


def test_many_valid_edits_may_have_a_longer_display_message_than_the_input_limit():
    pictures = [{'id': str(uuid4())} for _ in range(26)]
    edits = [dict(pictureId=item['id'], annotationId=None, text='x' * 4000, references=[])
             for item in pictures]
    archive_edits.validate(edits, [], pictures, 'x' * 104000)


@pytest.mark.parametrize('status', ['failed', 'cancelled', 'partial'])
def test_archive_preserves_actual_terminal_status_and_error(context, database, monkeypatch, status):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        turn = session.scalar(select(Turn))
        session.get(Job, turn.job_id).status = status
        turn.error = '原执行状态提示'
    with factory.begin() as session:
        archive_id = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='状态'), status).id
    archive_service.complete(factory, store, archive_id, first)
    with factory() as session:
        turn = archive_queries.detail(session, archive_id)['turns'][0]
        assert turn['status'] == status and turn['error'] == '原执行状态提示'
