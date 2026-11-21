from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.config import get_settings
from app.overseas.execution.materials import prepare
from app.overseas.execution.models import Job
from app.overseas.management.models import Audit
from app.overseas.studio.execution import HANDLER
from app.overseas.tasks.creative_tools import TOOL_KEYS
from overseas_installed_helpers import install_sample
from test_overseas_assignment import change_roles
from test_overseas_management import MANAGE
from test_overseas_skill_availability import toggle
from test_overseas_studio import finish, send
from test_overseas_tasks import HEADERS, ROOT, overseas, setup

URL = MANAGE + '/skills/tool-bindings'


def replace(client, key, expected, desired, headers=HEADERS):
    return client.put(URL + '/' + key, json={'expectedSkillIds': expected, 'skillIds': desired}, headers=headers)


def test_empty_defaults_multiple_installs_stale_edits_idempotency_and_permissions(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    ids = [install_sample(name)['id'] for name in ('one', 'two')]
    assert client.get(URL).json()['bindings'] == {key: [] for key in TOOL_KEYS}
    assert replace(client, 'not-a-tool', [], ids).status_code == 404
    assert replace(client, 'outon', [], ids, headers={}).status_code == 403
    assert replace(client, 'outon', [], ids + [str(uuid4())]).status_code == 422
    assert replace(client, 'outon', [], ids + ids).status_code == 422
    for key in TOOL_KEYS:
        result = replace(client, key, [], ids)
        assert result.status_code == 200, result.text
        assert set(result.json()['bindings'][key]) == set(ids)
    assert replace(client, 'outon', [], ids).status_code == 200
    assert replace(client, 'outon', [], [ids[0]]).status_code == 409
    assert replace(client, 'outon', ids, []).status_code == 200
    current = client.get(URL).json()['bindings']
    assert current['outon'] == [] and set(current['outonlife']) == set(ids)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Audit)) == len(TOOL_KEYS) + 1
    change_roles(factory, actor, ('designer',))
    assert client.get(URL).status_code == 403
    assert replace(client, 'outon', [], ids).status_code == 403


def create_tool(client, key):
    fields = {'productNameSku': '台灯 + SKU1'} if key == 'custom-size' else {
        'productName': '台灯', 'sku': 'SKU1', 'language': 'en'}
    response = client.post(ROOT + '/tasks/creative-tools', json={'toolKey': key, **fields},
                           headers={**HEADERS, 'Idempotency-Key': 'create-' + key})
    assert response.status_code == 201, response.text
    return response.json()


def test_task_bound_options_admission_immutable_replay_and_custom_size_worker(overseas, tmp_path):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    skill = install_sample()
    skill_id = skill['id']
    custom, amazon, other = [create_tool(client, key) for key in ('custom-size', 'outon', 'outonlife')]
    path = lambda task: ROOT + '/tasks/' + task['id'] + '/studio'
    for key in ('custom-size', 'outon'):
        assert replace(client, key, [], [skill_id]).status_code == 200
    assert client.get(path(custom)).json()['skills'] == []
    assert send(client, custom, skillId=skill_id).status_code == 422
    assert toggle(client, skill, headers=HEADERS).status_code == 200
    assert client.get(path(custom)).json()['skills'] == [skill]
    assert client.get(path(amazon)).json()['skills'] == [skill]
    assert client.get(path(other)).json()['skills'] == []
    assert send(client, other, skillId=skill_id).status_code == 422
    first = send(client, custom, skillId=skill_id)
    assert first.status_code == 200, first.text
    turn = first.json()['turns'][0]
    assert turn['skillName'] == skill['displayName']
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        config = SimpleNamespace(codex_execution_root=tmp_path, codex_auth_file='unused')
        workspace = HANDLER.workspace(factory, job, None, config)
        prepare(job, workspace)
        assert not workspace.disable_skills and workspace.skill_name == skill['name']
    assert replace(client, 'custom-size', [skill_id], []).status_code == 200
    replay = send(client, custom, skillId=skill_id)
    assert replay.json()['turns'] == first.json()['turns'] and replay.json()['skills'] == []
    finish(factory, turn)
    assert send(client, custom, key='stale-selection', skillId=skill_id).status_code == 422
    assert toggle(client, skill, enabled=False, version=2, headers=HEADERS).status_code == 200
    assert client.get(path(amazon)).json()['skills'] == []
    assert send(client, amazon, skillId=skill_id).status_code == 422
    plain = send(client, other)
    assert plain.status_code == 200, plain.text
    with factory() as session:
        job = session.get(Job, UUID(plain.json()['turns'][0]['jobId']))
        assert HANDLER.workspace(factory, job, None, config).disable_skills
