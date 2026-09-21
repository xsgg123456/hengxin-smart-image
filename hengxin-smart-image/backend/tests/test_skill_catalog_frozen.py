from uuid import UUID

from sqlalchemy import select

from files_helpers import files_env
from test_skills import skills_env
from test_skill_catalog import catalog_env, publish, sync, BASE
from test_files import upload
from test_tasks import job_for
from test_revisions import revise
from app.core.config import get_settings
from app.execution.materials import prepare_materials
from app.execution.workspace import Workspace
from app.execution.fixture_runner import run_generation
from app.modules.skills.models import SkillVersionRecord
from app.modules.tasks.models import ExecutionGate, TaskRecord, RoundRecord


def test_new_tasks_latest_old_queued_and_revision_use_original_bytes_after_unregister(catalog_env, monkeypatch, tmp_path):
    client, factory, store, _, root = catalog_env
    from io import BytesIO
    class Stream(BytesIO):
        def stream(self, size):
            yield self.read()
        def release_conn(self):
            pass
    monkeypatch.setattr(store, 'open', lambda record: Stream(store.objects[record.object_key]))
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', True)
    monkeypatch.setattr(get_settings(), 'fixture_delay_seconds', 0)
    with factory.begin() as session:
        session.add(ExecutionGate(id=1))
    path = publish(root)
    row = sync(catalog_env)[0]
    source = upload(client).json()
    body = dict(mode='text', name='冻结测试', sources=[source], note='修改文字', skillVersionId=row['id'])
    first = client.post('/api/v1/tasks', json=body, headers={'Idempotency-Key': 'first'})
    assert first.status_code == 202, first.text
    first = first.json()
    path.joinpath('script.py').write_bytes(b'second')
    sync(catalog_env)
    second = client.post('/api/v1/tasks', json=body, headers={'Idempotency-Key': 'second'}).json()
    with factory() as session:
        old = session.get(TaskRecord, UUID(first['taskId']))
        new = session.get(TaskRecord, UUID(second['taskId']))
        assert old.skill_version_id != new.skill_version_id
    assert client.delete(BASE + '/' + row['id']).status_code == 204
    assert client.post('/api/v1/tasks', json=body, headers={'Idempotency-Key': 'third'}).status_code == 422
    # Exercise actual material preparation; the changed live tree and removed registration are irrelevant.
    def material(receipt, label, expected):
        with factory() as session:
            task = session.get(TaskRecord, UUID(receipt['taskId']))
            round = session.get(RoundRecord, UUID(receipt['roundId']))
            folder = tmp_path / label
            for name in ('home', 'work', 'control'):
                (folder / name).mkdir(parents=True)
            workspace = Workspace(folder / 'home', folder / 'work', folder / 'control')
            prepare_materials(session, store, task, round, workspace)
            skill_path = workspace.work / 'skills' / 'demo'
            assert (skill_path / 'script.py').read_bytes() == expected
            assert (skill_path / 'empty').is_dir()
    material(first, 'original', b'first')
    material(second, 'latest', b'second')
    run_generation(job_for(factory, first), factory, store)
    revision = revise(catalog_env[:4], first)
    assert revision.status_code == 202, revision.text
    material(revision.json(), 'revision', b'first')


def test_template_stable_binding_tracks_current_snapshot_and_blocks_removal(catalog_env):
    client, factory, _, _, root = catalog_env
    path = publish(root, mode='wallpaper')
    row = sync(catalog_env)[0]
    body = dict(name='模板', mode='wallpaper', images=[upload(client).json()],
        skillVersionId=row['id'], active=True, notes='')
    template = client.post('/api/v1/templates', json=body).json()
    assert template['skillVersionId'] == row['id']
    with factory() as session:
        first = session.scalar(select(SkillVersionRecord)).id
    path.joinpath('script.py').write_bytes(b'new')
    sync(catalog_env)
    from app.modules.skills.service import resolve_binding
    with factory() as session:
        assert resolve_binding(session, 'wallpaper', template['skillVersionId']).id != first
    assert client.get('/api/v1/templates/' + template['id']).json()['active']
    assert client.delete(BASE + '/' + row['id']).status_code == 409
    client.delete('/api/v1/templates/' + template['id'])
    assert client.delete(BASE + '/' + row['id']).status_code == 204


def test_missing_default_with_explicit_selection_rejects_without_attribute_error(catalog_env, monkeypatch):
    """A default disappearing between template validation and binding resolution is rejected."""
    import app.modules.tasks.snapshots as snapshots
    from app.contracts.business import CreateTaskInput
    from fastapi import HTTPException
    import pytest
    from types import SimpleNamespace
    client, factory, _, _, root = catalog_env
    publish(root, mode='wallpaper')
    row = sync(catalog_env)[0]
    source = upload(client).json()
    monkeypatch.setattr(snapshots, 'find_template', lambda *_args, **_kwargs: object())
    # Use a valid persisted picture so execution reaches binding resolution.
    from app.contracts.business import Picture
    monkeypatch.setattr(snapshots, 'read_current', lambda *_: SimpleNamespace(
        version=1, mode='wallpaper', active=True, images=[Picture(**source)], skillVersionId=None))
    body = CreateTaskInput(mode='wallpaper', name='默认消失', sources=[Picture(**source)], note='',
        templateId=row['id'], templateVersion=1, skillVersionId=row['id'])
    with factory() as session, pytest.raises(HTTPException) as error:
        snapshots.frozen_input(session, body)
    assert error.value.status_code == 409
