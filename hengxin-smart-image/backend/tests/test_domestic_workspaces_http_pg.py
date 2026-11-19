"""Exercise new domestic menu identities through the existing authenticated HTTP routes."""
from uuid import UUID

import pytest

from app.main import app
from app.models import Job
from app.modules.auth.application_models import MemberAudit
from app.modules.auth.dingtalk import safe_return_path
from app.modules.domestic_studio import archive_service, recovery_transport
from app.modules.domestic_studio.turn_models import Turn
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from test_domestic_studio_bindings_pg import database
from test_domestic_studio_http_pg import client_env
from test_domestic_tasks_pg import HEADERS, ROOT, new, studio
from test_domestic_turns_pg import context

ENTRIES = {
    'general': '/new-product/general',
    'film': '/new-product/screen-protector', 'cable': '/new-product/data-cable',
    'earbud': '/new-product/earbud-case', 'accessory': '/new-product/creative-accessories',
    'edit': '/product-replace/general-edit',
}
ADMIN = '/api/v1/management/domestic-studio'


@pytest.mark.parametrize('path', ENTRIES.values())
def test_login_can_return_to_each_new_workspace(path):
    assert safe_return_path(path + '?task=mine') == path + '?task=mine'
    assert safe_return_path(path + '/unknown') != path + '/unknown'


def test_new_menu_entities_remain_isolated_across_bindings_studio_admin_and_archives(client_env, database, monkeypatch):
    client, factory, skill, actor, owner, admin, _, _ = client_env
    MemberAudit.__table__.create(database)
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'super_admin'
    actor['id'] = admin
    empty = client.get(ADMIN + '/bindings').json()['bindings']
    old = empty | {'camera': skill['id']}
    updated = old | dict.fromkeys(ENTRIES, skill['id'])
    for previous, proposed in ((empty, old), (old, updated)):
        result = client.put(ADMIN + '/bindings', headers=HEADERS, json={'bindings': proposed, 'expected': previous})
        assert result.status_code == 200, result.text
    assert client.get(ADMIN + '/bindings').json()['bindings'] == updated

    store = app.dependency_overrides[get_store]()
    monkeypatch.setattr(recovery_transport, 'request_archive',
                        lambda member, archive, channel: archive_service.complete(factory, store, archive, member))
    actor['id'] = owner
    created = {}
    for key in ENTRIES:
        task = new(client, '新品测试', key)
        root = studio(task)
        view = client.post(root + '/conversations', headers=HEADERS, json={'name': key}).json()
        channel = view['conversationId']
        assert [s['id'] for s in view['skills']] == [skill['id']]
        assert [row['id'] for row in client.get(ROOT, params={'workspace': key}).json()['items']] == [task['id']]
        upload = client.post(root + '/files', headers=HEADERS, params={'conversationId': channel},
                             files={'file': (key + '.txt', key.encode(), 'text/plain')}).json()
        sent = client.post(root + '/turns', headers=HEADERS, json={'conversationId': channel,
                           'text': key, 'skillId': skill['id'], 'attachmentIds': [upload['id']]})
        assert sent.status_code == 200, sent.text
        turn = sent.json()['turns'][0]
        assert turn['attachments'][0]['id'] == upload['id']
        with factory.begin() as session:
            record = session.get(Turn, UUID(turn['id']))
            record.reply = '已完成'
            session.get(Job, record.job_id).status = 'succeeded'
        archive = client.post(root + '/conversations/' + channel + '/archive', headers=HEADERS,
                              json={'productName': key})
        archives = client.get('/api/v1/domestic-studio/archives', params={'workspace': key})
        if key == 'edit':
            assert archive.status_code == 403 and archives.status_code == 422
        else:
            assert archive.status_code == 200, archive.text
            assert archive.json()['workspace'] == key
            assert [row['id'] for row in archives.json()['items']] == [archive.json()['id']]
        created[key] = task['id'], channel

    actor['id'] = admin
    for key, (task_id, channel) in created.items():
        assert client.get(ROOT + '/' + task_id).status_code == 404
        query = {'workspace': key, 'ownerId': str(owner)}
        tasks = client.get(ADMIN + '/tasks', params=query).json()['items']
        sessions = client.get(ADMIN + '/sessions', params=query).json()['items']
        assert [(row['id'], row['workspace']) for row in tasks] == [(task_id, key)]
        assert [(row['id'], row['workspace']) for row in sessions] == [(channel, key)]
