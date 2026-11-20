from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.overseas.execution.materials import prepare
from app.overseas.execution.models import Job
from app.overseas.studio.execution import HANDLER
from test_overseas_materials import materials
from test_overseas_plans import post
from test_overseas_studio import finish, output, send
from test_overseas_tasks import HEADERS, ROOT, overseas


def custom_task(client):
    created = client.post(ROOT + '/tasks/custom', json={'productNameSku': '吊灯 + SKU-L'},
                          headers={**HEADERS, 'Idempotency-Key': 'create-custom'})
    assert created.status_code == 201, created.text
    return created.json()


def test_custom_studio_reference_image_revision_conversations_and_archive(materials, monkeypatch):
    client, factory, _, _, store = materials
    def catalog_forbidden(*args):
        pytest.fail('Custom task accessed the installed skills catalog')
    monkeypatch.setattr('app.overseas.studio.queries.enabled_listing', catalog_forbidden)
    monkeypatch.setattr('app.overseas.management.settings.selected', catalog_forbidden)
    task = custom_task(client)
    path = ROOT + '/tasks/' + task['id'] + '/studio'
    initial = client.get(path).json()
    channel = initial['conversationId']
    assert channel and len(initial['conversations']) == 1 and initial['skills'] == []
    rejected = send(client, task, skillId=str(uuid4()), conversationId=channel)
    assert rejected.status_code == 422 and '自定义' in rejected.text
    image = output(store)
    reference = client.post(path + '/files', params={'conversationId': channel},
        files={'file': ('reference.png', store.data[image['object_key']], 'image/png')}, headers=HEADERS)
    assert reference.status_code == 200, reference.text
    body = dict(conversationId=channel, attachmentIds=[reference.json()['id']])
    first = send(client, task, **body).json()['turns'][0]
    assert first['skillName'] is None
    assert send(client, task, **body).json()['turns'][0]['jobId'] == first['jobId']
    finish(factory, first, [image])
    revised = send(client, task, key='revise', referencePictureIds=[image['id']], **body,
        imageEdits=[{'pictureId': image['id'], 'text': '灯光调暖', 'references': [
            {'attachmentId': reference.json()['id'], 'kind': 'effect', 'note': '参考色温'}]}])
    assert revised.status_code == 200, revised.text
    turn = revised.json()['turns'][-1]
    assert turn['skillName'] is None and turn['referencePictures'][0]['id'] == image['id']
    finish(factory, turn)
    archived = post(client, task, '/studio/archive', {'pictureIds': [image['id']], 'sku': 'SKU-L',
                    'conversationId': channel}, 'archive')
    assert archived.status_code == 200 and archived.json()['archiveId']
    other = post(client, task, '/studio/conversations', {}, 'new')
    assert other.status_code == 200, other.text
    assert other.json()['conversationId'] != channel and other.json()['turns'] == []
    assert send(client, task, key='second-channel', conversationId=other.json()['conversationId']).status_code == 200
    with factory() as session:
        jobs = list(session.scalars(select(Job)))
        assert len(jobs) == 3 and all(job.payload['skill'] is None for job in jobs)


def test_custom_worker_accepts_plain_round_and_rejects_persisted_skill_before_materials(materials, tmp_path):
    client, factory, _, _, _ = materials
    task = custom_task(client)
    turn = send(client, task).json()['turns'][0]
    settings = SimpleNamespace(codex_execution_root=tmp_path, codex_auth_file='unused')
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        workspace = HANDLER.workspace(factory, job, None, settings)
        prepare(job, workspace)
        assert not workspace.use_skill and workspace.local_skill is None
        assert not list(tmp_path.rglob('SKILL.md'))
        assert workspace.disable_skills and 'skills.bundled.enabled=false' in HANDLER.arguments(workspace)
        assert HANDLER.prepare(job, workspace).endswith('设计产品')
        job.payload = {**job.payload, 'skill': {'name': 'retired', 'files': {'SKILL.md': 'old'}}}
        session.commit()
        with pytest.raises(ValueError, match='cannot execute a frozen Skill'):
            HANDLER.workspace(factory, job, None, settings)
