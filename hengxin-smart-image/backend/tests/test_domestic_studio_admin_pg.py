"""Real HTTP + disposable PostgreSQL proofs for domestic admin observation."""
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select

from app.models import Job, Outbox
from app.modules.auth.application_models import MemberAudit
from app.modules.domestic_studio import queries, skill_state
from app.execution.models import ExecutionGate
from app.modules.domestic_studio.models import SkillExecutionReference, WorkspaceBinding
from app.modules.domestic_studio.skill_state import DomesticSkillState
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion, Workspace
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Transcript, Turn, Upload
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.main import app
from domestic_task_fixtures import create
from app.overseas.studio.schemas import NewConversation
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context
from test_domestic_studio_http_pg import client_env

ROOT = '/api/v1/management/domestic-studio/sessions'


@pytest.fixture
def monitor(client_env, database, monkeypatch):
    client, factory, _, identity, owner, admin, channel, other = client_env
    MemberAudit.__table__.create(database)
    def forbidden(*args, **kwargs):
        raise AssertionError('Admin observation must not acquire Skill/admission state')
    monkeypatch.setattr(queries, 'available_skills', forbidden)
    monkeypatch.setattr(skill_state, 'freeze_enabled', forbidden)
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'super_admin'
        session.get(UserRecord, owner).name = '真实成员'
        session.get(Conversation, channel).name = '相机会话'
        channels = [channel]
        for workspace in ('case', 'product', 'scene', 'phone'):
            session.add(Workspace(owner_id=owner, workspace=workspace))
            session.flush()
            item = create(session, owner, workspace, NewConversation(name=workspace), 'fixture-' + workspace)
            session.add(item)
            session.flush()
            channels.append(item.id)
        for number, (conversation_id, status) in enumerate(zip(channels, ('running', 'queued', 'partial', 'failed', 'cancelled'))):
            job = Job(idempotency_key=str(uuid4()), payload_hash='a' * 64, value='{}',
                      kind='domestic_studio', status=status)
            session.add(job)
            session.flush()
            turn = Turn(conversation_id=conversation_id, job_id=job.id, actor_id=owner,
                text=f'完整用户输入{number}', snapshot={'skill': {'name': '实际Skill'}, 'token': 'secret-runtime-token'},
                reply='公开回复', process_identity={'path': '/private/runtime'}, error='token=unsafe' if status == 'failed' else None)
            session.add(turn)
            session.flush()
            session.add(Transcript(turn_id=turn.id, item_id=f'event-{number}', kind='message', text='公开回复', state='completed'))
    identity['id'] = admin
    return client, factory, identity, owner, admin, channels, other


def business_snapshot(factory):
    with factory() as session:
        return {model.__tablename__: [dict(row) for row in session.execute(select(model.__table__)).mappings()]
                for model in (UserRecord, Job, Outbox, Workspace, Conversation, ConversationDeletion,
                              Turn, Transcript, Upload, Picture, OutputFile, ExecutionGate,
                              WorkspaceBinding, DomesticSkillState, SkillExecutionReference)}


def test_list_filters_counts_pages_and_live_updates(monitor):
    client, factory, _, owner, _, channels, _ = monitor
    result = client.get(ROOT, params={'ownerId': str(owner), 'pageSize': 2})
    assert result.status_code == 200
    data = result.json()
    assert data['total'] == data['counters']['total'] == 5
    assert len(data['items']) == 2
    assert data['counters'] == dict(total=5, empty=0, queued=1, running=1, succeeded=1, failed=1, cancelled=1, unknown=0)
    assert {row['workspace'] for page in (1, 2, 3) for row in client.get(ROOT,
        params={'ownerId': str(owner), 'pageSize': 2, 'page': page}).json()['items']} == {'camera', 'case', 'product', 'scene', 'phone'}
    assert {'id': str(owner), 'name': '真实成员'} in data['members']
    filtered = client.get(ROOT, params={'ownerId': str(owner), 'workspace': 'camera', 'status': 'running', 'search': '相机'}).json()
    assert filtered['total'] == filtered['counters']['running'] == 1
    assert client.get(ROOT, params={'search': '%'}).json()['total'] == 0
    assert client.get(ROOT, params={'workspace': 'amazon'}).status_code == 422
    assert client.get(ROOT, params={'page': 0}).status_code == 422
    with factory.begin() as session:
        turn = session.scalar(select(Turn).where(Turn.conversation_id == channels[0]))
        session.get(Job, turn.job_id).status = 'succeeded'
    assert client.get(ROOT, params={'status': 'running'}).json()['total'] == 0
    assert client.get(ROOT, params={'status': 'succeeded'}).json()['total'] == 2


def test_complete_turn_history_and_transcripts_never_mix_sessions(monitor):
    client, factory, _, owner, _, channels, _ = monitor
    with factory.begin() as session:
        first = session.scalar(select(Turn).where(Turn.conversation_id == channels[0]))
        session.get(Job, first.job_id).status = 'succeeded'
        job = Job(idempotency_key=str(uuid4()), payload_hash='a' * 64, value='{}', status='running')
        session.add(job)
        session.flush()
        second = Turn(conversation_id=channels[0], job_id=job.id, actor_id=owner,
            text='第二轮完整输入', snapshot={'skill': None}, reply=None)
        session.add(second)
        session.flush()
        session.add(Transcript(turn_id=second.id, item_id='second-progress', kind='tool', text='网页搜索', state='running'))
        first_id, second_id = str(first.id), str(second.id)
    data = client.get(f'{ROOT}/{channels[0]}').json()
    assert data['session']['turnCount'] == 2 and data['session']['status'] == 'running'
    assert [row['id'] for row in data['workspace']['turns']] == [first_id, second_id]
    assert data['workspace']['turns'][1]['skillName'] is None
    progress = client.get(f'{ROOT}/{channels[0]}/transcript').json()['items']
    assert {row['turnId'] for row in progress} == {first_id, second_id}
    other = client.get(f'{ROOT}/{channels[1]}/transcript').json()['items']
    assert not ({row['turnId'] for row in other} & {first_id, second_id})


def test_details_transcript_pagination_are_readonly_and_audited(monitor):
    client, factory, _, owner, admin, channels, _ = monitor
    with factory.begin() as session:
        turn = session.scalar(select(Turn).where(Turn.conversation_id == channels[0]))
        session.add_all(Transcript(turn_id=turn.id, item_id=str(number), kind='tool', text='命令执行', state='running')
                        for number in range(501))
    before = business_snapshot(factory)
    for channel in channels:
        response = client.get(f'{ROOT}/{channel}')
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        data = response.json()
        assert data['session']['ownerName'] == '真实成员'
        assert len(data['siblingSessions']) == 1
        assert data['siblingSessions'][0]['taskId'] == data['workspace']['taskId']
        assert data['workspace']['turns'][0]['skillName'] == '实际Skill'
        assert data['workspace']['turns'][0]['canRecover'] is False
        assert 'secret-runtime-token' not in response.text and '/private/runtime' not in response.text
        assert 'unsafe' not in response.text
    first = client.get(f'{ROOT}/{channels[0]}/transcript').json()
    assert first['hasMore'] and len(first['items']) == 500
    second = client.get(f'{ROOT}/{channels[0]}/transcript', params={'after': first['cursor']}).json()
    assert not second['hasMore'] and len(second['items']) == 2
    assert not ({item['id'] for item in first['items']} & {item['id'] for item in second['items']})
    assert before == business_snapshot(factory)
    with factory() as session:
        audits = list(session.scalars(select(MemberAudit)))
        assert len(audits) == 7
        assert all(row.actor_id == admin and row.member_id == owner for row in audits)
        assert all(set(row.after) == {'conversationId'} for row in audits)
    assert client.post(f'{ROOT}/{channels[0]}/turns', json={}).status_code in (404, 405)
    assert client.delete(f'{ROOT}/{channels[0]}').status_code == 405


def test_permissions_are_rechecked_on_every_endpoint(monitor):
    client, factory, identity, owner, admin, channels, _ = monitor
    urls = [ROOT, f'{ROOT}/{channels[0]}', f'{ROOT}/{channels[0]}/transcript',
            f'{ROOT}/{channels[0]}/files/{uuid4()}/content']
    for role in ('designer', 'operator', 'design_manager'):
        with factory.begin() as session:
            session.get(UserRecord, owner).role = role
        identity['id'] = owner
        assert [client.get(url).status_code for url in urls] == [403] * 4
    identity['id'] = admin
    assert client.get(ROOT).status_code == 200
    # Same browser, next request sees revocation from a separate committed transaction.
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'designer'
    assert [client.get(url).status_code for url in urls] == [403] * 4
    identity['id'] = uuid4()
    assert client.get(ROOT).status_code == 401


def test_all_files_are_bound_to_conversation_and_deletion(monitor):
    client, factory, identity, owner, admin, channels, other = monitor
    store = app.dependency_overrides[get_store]()
    image = BytesIO()
    Image.new('RGB', (3, 2)).save(image, format='PNG')
    paths = []
    with factory.begin() as session:
        turn = session.scalar(select(Turn).where(Turn.conversation_id == channels[0]))
        for model, kind in ((Upload, 'files'), (Picture, 'pictures'), (OutputFile, 'outputs')):
            blob = image.getvalue() if kind == 'pictures' else b'private original'
            identity_value = uuid4()
            values = dict(id=identity_value, name='原件.png' if kind == 'pictures' else '原件.txt',
                content_type='image/png' if kind == 'pictures' else 'text/plain', size_bytes=len(blob),
                checksum=sha256(blob).hexdigest(), bucket='private', object_key=str(identity_value))
            values.update({'conversation_id': channels[0]} if model is Upload else {'turn_id': turn.id})
            if model is Picture:
                values.update(width=3, height=2, source_path='/work/private.png')
            if model is OutputFile:
                values['source_path'] = '/work/private.txt'
            if model is Upload:
                turn.snapshot = {**turn.snapshot, 'attachmentIds': ['upload:' + str(identity_value)]}
            session.add(model(**values))
            store.objects[('private', str(identity_value))] = blob
            paths.append((f'{ROOT}/{channels[0]}/{kind}/{identity_value}/content', blob))
    for path, blob in paths:
        assert client.get(path).content == blob
        assert client.head(path).status_code == 200
        assert client.get(path.replace(str(channels[0]), str(other))).status_code == 404
        assert client.get(path.replace(str(channels[0]), str(uuid4()))).status_code == 404
    image_path = paths[1][0]
    preview = client.get(image_path, params={'preview': True})
    assert preview.status_code == 200 and preview.headers['content-type'] == 'image/png'
    assert preview.headers['cache-control'] == 'private, no-store'
    assert client.head(image_path).headers['cache-control'] == 'private, no-store'
    assert client.get(image_path, params={'thumbnail': True}).status_code == 200
    unavailable_path = paths[2][0]
    missing_key = unavailable_path.split('/')[-2]
    del store.objects[('private', missing_key)]
    missing = client.get(unavailable_path)
    assert missing.status_code == 503 and '原件不存在' in missing.text
    response = client.get(f'{ROOT}/{channels[0]}')
    assert 'sourcePath' not in response.text and '/work/private' not in response.text
    # The existing private owner endpoint remains private even to the super-admin.
    assert client.get('/api/v1/domestic-studio/workspaces/camera',
                      params={'conversationId': str(channels[0])}).status_code == 404
    with factory.begin() as session:
        session.add(ConversationDeletion(conversation_id=channels[0], owner_id=owner,
            workspace='camera', status='pending', manifest={}))
    assert client.get(f'{ROOT}/{channels[0]}').status_code == 404
    assert client.get(f'{ROOT}/{channels[0]}/transcript').status_code == 404
    assert all(client.get(path).status_code == 404 for path, _ in paths)
    assert str(channels[0]) not in [row['id'] for row in client.get(ROOT).json()['items']]


def test_unsubmitted_upload_is_private_until_a_turn_references_it(monitor):
    client, factory, _, _, _, channels, _ = monitor
    store = app.dependency_overrides[get_store]()
    upload_id = uuid4()
    with factory.begin() as session:
        session.add(Upload(id=upload_id, conversation_id=channels[0], name='未提交附件.txt',
            content_type='text/plain', size_bytes=5, checksum=sha256(b'draft').hexdigest(),
            bucket='private', object_key=str(upload_id), status='ready'))
    store.objects[('private', str(upload_id))] = b'draft'
    url = f'{ROOT}/{channels[0]}/files/{upload_id}/content'
    assert client.get(url).status_code == client.head(url).status_code == 404
    assert str(upload_id) not in client.get(f'{ROOT}/{channels[0]}').text
    with factory.begin() as session:
        turn = session.scalar(select(Turn).where(Turn.conversation_id == channels[0]))
        turn.snapshot = {**turn.snapshot, 'attachmentIds': ['upload:' + str(upload_id)]}
    assert client.get(url).content == b'draft'
    assert client.head(url).status_code == 200
    assert client.get(f'{ROOT}/{channels[0]}').json()['workspace']['materials'][0]['id'] == 'upload:' + str(upload_id)
