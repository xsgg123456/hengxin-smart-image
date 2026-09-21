"""Catalog HTTP/state/object bytes; real permissions and bwrap have separate tests."""
import io
import json
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from files_helpers import files_env
from test_skills import skills_env
from app.core.config import get_settings
from app.models import Job, Outbox
from app.modules.skills.models import SkillRecord, SkillVersionRecord, ModuleSkillBinding
from app.modules.skills.service import resolve_binding
from app.resource_models import UserRecord
from app.worker.skill_sync import run_sync

BASE = '/api/v1/management/skill-catalog'


@pytest.fixture
def catalog_env(skills_env, monkeypatch, tmp_path):
    import app.modules.skills.local_tree as tree
    import app.worker.skill_sync as worker
    root = tmp_path / 'published'
    root.mkdir()
    monkeypatch.setenv('LOCAL_SKILL_ROOT', str(root))
    get_settings.cache_clear()
    # Windows unit tests cannot assert Linux ownership: dedicated opt-in Linux tests do.
    monkeypatch.setattr(tree, 'protected', lambda *_: None)
    monkeypatch.setattr(worker, 'protected', lambda *_: None)
    monkeypatch.setattr(worker, 'probe_tree', lambda *_: None)
    yield (*skills_env, root)
    get_settings.cache_clear()


def publish(root, name='demo', *, mode='text', description='完整描述', content=b'first'):
    path = root / name
    path.mkdir(exist_ok=True)
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {description}\n---\nInstructions', encoding='utf-8')
    (path / 'script.py').write_bytes(content)
    (path / 'empty').mkdir(exist_ok=True)
    if mode:
        (path / 'hengxin-skill.json').write_text(json.dumps({'mode': mode, 'version': '7.8.9'}))
    return path


def sync(env):
    client, factory, store, _, _ = env
    result = client.post(BASE + '/sync')
    assert result.status_code == 202, result.text
    job_id = result.json()['jobId']
    run_sync(job_id, factory, store)
    return client.get(BASE).json()


def test_sync_metadata_complete_snapshot_repeat_and_disable(catalog_env):
    client, factory, store, _, root = catalog_env
    path = publish(root, description='长描述' * 1000)
    assert client.get(BASE + '/sync').json() == dict(jobId=None, status='idle', error=None)
    first_request = client.post(BASE + '/sync').json()
    assert client.post(BASE + '/sync').json() == first_request
    run_sync(first_request['jobId'], factory, store)
    row = client.get(BASE).json()[0]
    assert row['status'] == 'available' and row['description'] == '长描述' * 1000
    assert row['mode'] == 'text' and set(row) == {'id', 'name', 'description', 'mode', 'status', 'isDefault', 'error', 'updatedAt', 'referenced'}
    assert client.get('/api/v1/skill-catalog').json() == [row]
    with factory() as session:
        first = resolve_binding(session, 'text', row['id'])
        first_id, first_key = first.id, first.object_key
    raw = store.objects[first_key]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.read('script.py') == b'first'
        assert archive.read('hengxin-skill.json') == (path / 'hengxin-skill.json').read_bytes()
        assert 'empty/' in archive.namelist()
    sync(catalog_env)
    with factory() as session:
        assert len(session.scalars(select(SkillVersionRecord)).all()) == 1
    assert len(store.objects) == 1
    client.put(BASE + '/' + row['id'] + '/status', json={'status': 'disabled'})
    (path / 'script.py').write_bytes(b'second')
    updated = sync(catalog_env)[0]
    assert updated['status'] == 'disabled'
    assert client.get('/api/v1/skill-catalog').json() == []
    assert client.get('/api/v1/skills').json() == []
    assert client.put('/api/v1/management/skills/' + str(first_id) + '/status', json={'status': 'available'}).status_code == 409
    assert store.objects[first_key] == raw
    client.put(BASE + '/' + row['id'] + '/status', json={'status': 'available'})
    with factory() as session:
        assert resolve_binding(session, 'text', row['id']).id != first_id
        assert resolve_binding(session, 'text', first_id).id != first_id


def test_unknown_type_mode_selection_and_failure_isolated(catalog_env):
    client, _, _, _, root = catalog_env
    publish(root, mode=None)
    publish(root, 'broken').joinpath('SKILL.md').write_text('broken')
    rows = {r['name']: r for r in sync(catalog_env)}
    assert rows['demo']['status'] == 'needs_type' and rows['demo']['mode'] is None
    assert rows['broken']['status'] == 'invalid'
    route = BASE + '/' + rows['demo']['id']
    assert client.put(route + '/status', json={'status': 'available'}).status_code == 409
    result = client.put(route + '/mode', json={'mode': 'text'})
    assert result.status_code == 200 and result.json()['status'] == 'syncing'
    rows = {r['name']: r for r in sync(catalog_env)}
    assert rows['demo']['status'] == 'available'
    assert client.put(route + '/mode', json={'mode': 'wallpaper'}).status_code == 409


def test_missing_storage_failure_defaults_remove_and_rediscover(catalog_env):
    client, factory, store, _, root = catalog_env
    path = publish(root)
    row = sync(catalog_env)[0]
    defaults = dict(wallpaper=None, product=None, text=row['id'])
    assert client.put(BASE + '/defaults', json=defaults).json() == defaults
    assert client.get('/api/v1/management/settings').json()['defaultSkillIds'] == defaults
    assert client.delete(BASE + '/' + row['id']).status_code == 409
    path.joinpath('script.py').write_bytes(b'changed')
    store.fail_put = True
    assert sync(catalog_env)[0]['status'] == 'invalid'
    assert client.get('/api/v1/skill-catalog').json() == []
    store.fail_put = False
    assert sync(catalog_env)[0]['status'] == 'available'
    path.rename(root / 'moved')
    assert {r['name']: r for r in sync(catalog_env)}['demo']['status'] == 'invalid'
    path = root / 'moved'
    path.rename(root / 'demo')
    sync(catalog_env)
    client.put(BASE + '/defaults', json={**defaults, 'text': None})
    assert client.delete(BASE + '/' + row['id']).status_code == 204
    assert (root / 'demo' / 'SKILL.md').is_file()
    assert all(r['id'] != row['id'] for r in client.get(BASE).json())
    assert any(r['id'] == row['id'] for r in sync(catalog_env))


def test_permissions_and_lease_fence(catalog_env, monkeypatch):
    import app.worker.skill_sync as worker
    client, factory, store, identity, root = catalog_env
    publish(root)
    job_id = client.post(BASE + '/sync').json()['jobId']
    original = worker.inspect_one
    def steal(*args):
        result = original(*args)
        with factory.begin() as session:
            session.get(Job, UUID(job_id)).claim_token = uuid4()
        return result
    monkeypatch.setattr(worker, 'inspect_one', steal)
    run_sync(job_id, factory, store)
    with factory() as session:
        assert session.scalar(select(SkillVersionRecord)) is None
        assert session.get(Outbox, UUID(job_id)).completed_at is None
    row = client.get(BASE).json()[0]
    for role in ('operator', 'designer', 'design_manager'):
        with factory.begin() as session:
            session.get(UserRecord, identity[0]).role = role
        assert client.post(BASE + '/sync').status_code == 403
        assert client.get(BASE).status_code == 403
        assert client.put(BASE + '/' + row['id'] + '/mode', json={'mode': 'text'}).status_code == 403
        assert client.delete(BASE + '/' + row['id']).status_code == 403


def test_root_failure_rejects_new_admission(catalog_env, monkeypatch):
    import app.worker.skill_sync as worker
    client, _, _, _, root = catalog_env
    publish(root)
    sync(catalog_env)
    monkeypatch.setattr(worker, 'scan_names', lambda *_: (_ for _ in ()).throw(PermissionError()))
    assert sync(catalog_env)[0]['status'] == 'invalid'
    assert client.get(BASE + '/sync').json()['status'] == 'failed'


@pytest.mark.parametrize('problem', ['metadata', 'wrong_name', 'wrong_mode', 'oversize', 'dependency', 'drift', 'object_missing'])
def test_invalid_sync_never_republishes_previous_snapshot(catalog_env, monkeypatch, problem):
    import app.worker.skill_sync as worker
    import app.modules.skills.local_tree as tree_module
    client, factory, store, _, root = catalog_env
    path = publish(root)
    row = sync(catalog_env)[0]
    with factory() as session:
        original = session.get(SkillRecord, UUID(row['id'])).current_version_id
    if problem == 'metadata':
        path.joinpath('SKILL.md').write_text('---\nname: demo\ndescription: [oops]\n---\n')
    elif problem == 'wrong_name':
        path.joinpath('SKILL.md').write_text('---\nname: other\ndescription: demo\n---\n')
    elif problem == 'wrong_mode':
        path.joinpath('hengxin-skill.json').write_text('{"mode":"wallpaper"}')
    elif problem == 'oversize':
        monkeypatch.setattr(tree_module, 'MAX_ZIP', 4)
    elif problem == 'dependency':
        monkeypatch.setattr(worker, 'probe_tree', lambda *_: (_ for _ in ()).throw(ValueError('缺少隔离环境依赖')))
    elif problem == 'drift':
        monkeypatch.setattr(worker, 'probe_tree', lambda *_: path.joinpath('script.py').write_bytes(b'changed-during-probe'))
    else:
        store.objects.clear()
    assert sync(catalog_env)[0]['status'] == 'invalid'
    assert client.get('/api/v1/skill-catalog').json() == []
    with factory() as session:
        assert session.get(SkillRecord, UUID(row['id'])).current_version_id == original


@pytest.mark.parametrize('stage', ['queued', 'running_after_skill'])
def test_mode_selection_during_global_sync_cannot_strand_skill(catalog_env, monkeypatch, stage):
    import app.worker.skill_sync as worker
    client, factory, store, _, root = catalog_env
    publish(root, 'aaa', mode=None)
    publish(root, 'zzz')
    row = next(r for r in sync(catalog_env) if r['name'] == 'aaa')
    assert row['status'] == 'needs_type'
    route = BASE + '/' + row['id'] + '/mode'
    job_id = client.post(BASE + '/sync').json()['jobId']
    responses = []
    original = worker.inspect_one
    def inspect(*args):
        if args[1] == 'zzz':
            # The running job has already committed aaa's needs_type result.
            responses.append(client.put(route, json={'mode': 'text'}))
        return original(*args)
    if stage == 'queued':
        responses.append(client.put(route, json={'mode': 'text'}))
    else:
        monkeypatch.setattr(worker, 'inspect_one', inspect)
    run_sync(job_id, factory, store)
    assert len(responses) == 1 and responses[0].status_code == 409
    with factory() as session:
        skill = session.get(SkillRecord, UUID(row['id']))
        assert skill.mode == '' and skill.catalog_status == 'needs_type'
    monkeypatch.setattr(worker, 'inspect_one', original)
    assert client.put(route, json={'mode': 'text'}).json()['status'] == 'syncing'
    assert next(r for r in sync(catalog_env) if r['name'] == 'aaa')['status'] == 'available'
