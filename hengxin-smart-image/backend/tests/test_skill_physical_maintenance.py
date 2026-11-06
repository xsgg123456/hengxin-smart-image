"""Whole-library schema migration on real isolated legacy trees and historical owners."""
import json
import shutil
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.execution.workspace import prepare_workspace
from app.overseas.execution import materials, skill_history
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.management import installed_catalog as catalog, skill_maintenance as maintenance
from app.overseas.management.installed_tree import digest
from app.overseas.management.skill_transfer_store import atomic_json
from app.overseas.studio import context_workspace
from app.overseas.studio.models import Turn
from test_skill_physical_history import history, owned_job, transfers, overseas, fingerprint


def legacy(h):
    root = h.store.installed_root
    release, items = catalog.read_catalog(root)
    for index in range(3):
        manifest = dict(schema=1, items=items, legacyGeneration=index)
        identity = digest(manifest)
        folder = root / 'releases' / identity
        folder.mkdir()
        for item in items:
            shutil.copytree(root / 'packages' / item['name'] / item['checksum'], folder / item['name'])
        atomic_json(folder / 'manifest.json', manifest)
    atomic_json(root / 'current.json', {'release': identity})
    shutil.rmtree(root / 'packages')
    # Same frozen Skill keeps its original schema2 manifest; it resolves once promoted.
    return identity, items


def pause(h):
    with h.factory.begin() as session:
        session.get(ExecutionGate, 1).paused = True


def same_owner_release_jobs(h):
    first = owned_job(h)
    materials.prepare(first, first.workspace)
    release, _ = legacy(h)
    body = deepcopy(first.payload)
    body['skill']['installedRelease'] = release
    job_id, turn_id = uuid4(), uuid4()
    with h.factory.begin() as session:
        session.add(Job(id=job_id, task_id=h.task, kind='studio', dedupe_key=str(job_id),
                        payload=body, status='succeeded', process_exited=True))
        session.flush()
        session.add(Turn(id=turn_id, task_id=h.task, conversation_id=first.conversation,
                         job_id=job_id, actor_id=h.actor, text='下一轮原始消息',
                         skill_name=body['skill']['name']))
    workspace = prepare_workspace(h.root / 'studio', first.conversation, turn_id, None, copy_auth=False)
    context_workspace.prepare(workspace, [], [], lambda _: pytest.fail('No remote calls'))
    second = SimpleNamespace(id=job_id, payload=body, workspace=workspace)
    materials.prepare(second, workspace)
    pause(h)
    return first, second, release


def test_same_owner_content_across_releases_preserves_all_frozen_inputs(history):
    h = history
    first, second, release = same_owner_release_jobs(h)
    old_files = {p: p.read_bytes() for p in first.owner.rglob('*') if p.is_file()}
    for dry_run in (True, False):
        with h.factory() as session:
            result = maintenance.reclaim(h.store, session, h.actor, release, dry_run)
        assert result['historyContents'] == result['existingHistoryContents'] == 1
        assert result['jobs'] == 2 and result['frozenInputs'] == 4
        assert result['dryRun'] == dry_run
        assert all(p.read_bytes() == content for p, content in old_files.items())
        with h.factory() as session:
            assert session.get(Job, first.id).payload == first.payload
            assert session.get(Job, second.id).payload == second.payload
    assert result['cleanupComplete'] and result['targets'] == 3
    assert all(set(p.name for p in folder.iterdir()) == {'manifest.json'}
               for folder in (h.store.installed_root / 'releases').iterdir())
    for job in (first, second):
        item = catalog.frozen_item(job.payload['skill'])[1]
        assert skill_history.find(first.owner, item)[1] == h.files
    assert result['historyBytes'] == 0  # Existing verified owner copies need no extra content.


@pytest.mark.parametrize('dry_run', [True, False])
def test_same_content_unowned_release_still_blocks_gc(history, dry_run):
    h = history
    first, second, release = same_owner_release_jobs(h)
    owned_releases = {job.payload['skill']['installedRelease'] for job in (first, second)}
    unowned = next(path.name for path in (h.store.installed_root / 'releases').iterdir()
                   if path.name not in owned_releases)
    # This is a valid release of identical bytes, but no Job owns its disk reference.
    path = second.workspace.control / 'input.json'
    body = deepcopy(second.payload)
    body['skill']['installedRelease'] = unowned
    assert catalog.frozen_package(body['skill']).files == h.files
    path.write_text(json.dumps(body), encoding='utf-8')
    before = fingerprint(h.store.installed_root)
    old_files = {p: p.read_bytes() for p in first.owner.rglob('*') if p.is_file()}
    with h.factory() as session, pytest.raises(ValueError, match='Unaccounted'):
        maintenance.reclaim(h.store, session, h.actor, release, dry_run)
    assert fingerprint(h.store.installed_root) == before
    assert all(p.read_bytes() == content for p, content in old_files.items())


def test_full_migration_preserves_history_catalog_and_reports_actual_net_bytes(history):
    h = history
    job = owned_job(h)
    materials.prepare(job, job.workspace)
    old_files = {p: p.read_bytes() for p in job.owner.rglob('*') if p.is_file()}
    release, items = legacy(h)
    pause(h)
    with h.factory() as session:
        summary = maintenance.reclaim(h.store, session, h.actor, release)
    assert summary['dryRun'] and summary['historyContents'] == summary['existingHistoryContents'] == 1
    assert summary['frozenInputs'] == 2
    assert catalog.read_catalog(h.store.installed_root)[0] == release
    with h.factory() as session:
        result = maintenance.reclaim(h.store, session, h.actor, release, False)
    with h.factory() as session:
        assert maintenance.reclaim(h.store, session, h.actor, release, False) == result
    assert result['cleanupComplete'] and result['targets'] == 3
    assert result['reclaimedBytes'] == max(0, result['centralBytes'] - result['afterBytes'] - result['historyBytes'])
    assert catalog.read_catalog(h.store.installed_root)[1] == items
    assert all(p.read_bytes() == value for p, value in old_files.items())
    assert all(set(p.name for p in folder.iterdir()) == {'manifest.json'}
               for folder in (h.store.installed_root / 'releases').iterdir())
    with h.factory() as session:
        assert session.get(Job, job.id).payload == job.payload
    frozen_item = catalog.frozen_item(h.frozen)[1]
    assert skill_history.find(job.owner, frozen_item) is not None


def test_maintenance_refuses_unpaused_and_changed_release(history):
    h = history
    with h.factory() as session, pytest.raises(HTTPException) as failure:
        maintenance.reclaim(h.store, session, h.actor, h.package['release'], False)
    assert failure.value.status_code == 409
    pause(h)
    with h.factory() as session, pytest.raises(HTTPException) as failure:
        maintenance.reclaim(h.store, session, h.actor, 'a' * 64, False)
    assert failure.value.status_code == 409


def test_unaccounted_input_blocks_gc_before_pointer_or_files_change(history):
    h = history
    job = owned_job(h)
    materials.prepare(job, job.workspace)
    path = job.workspace.control / 'input.json'
    body = json.loads(path.read_bytes())
    body['skill']['checksum'] = 'a' * 64
    path.write_text(json.dumps(body), encoding='utf-8')
    pause(h)
    before = catalog.read_catalog(h.store.installed_root)
    with h.factory() as session, pytest.raises(ValueError, match='Unaccounted'):
        maintenance.reclaim(h.store, session, h.actor, before[0], False)
    assert catalog.read_catalog(h.store.installed_root) == before
    assert catalog.frozen_package(h.frozen).files == h.files
