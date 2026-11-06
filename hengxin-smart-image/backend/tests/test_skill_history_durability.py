"""A successful central GC must be preceded by a durable owner-local copy."""
from pathlib import Path
import pytest

from app.overseas.execution import materials, skill_history
from app.overseas.management import skill_cleanup
from test_skill_physical_history import history, owned_job, transfers, overseas
from test_overseas_skill_transfers import deletion


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure', ['owner', 'file'])
def test_durability_failure_blocks_gc_and_retry_syncs_existing_copy(history, monkeypatch, existing, failure):
    h = history
    job = owned_job(h, kind='analysis')
    if existing:
        materials.prepare(job, job.workspace)
    owner = skill_history.fs.checked(job.owner, directory=True)
    central = h.store.installed_root / 'packages' / h.item['name'] / h.package['checksum']
    original_sync, original_file = skill_history.fs.sync, skill_history.durable_file
    calls, blocked = [], [True]
    def sync(path):
        path = skill_history.fs.checked(Path(path), directory=True)
        calls.append(('dir', path))
        if blocked[0] and failure == 'owner' and path == owner:
            raise OSError('injected owner fsync failure')
        return original_sync(path)
    def file(path):
        calls.append(('file', Path(path)))
        if blocked[0] and failure == 'file' and path.name == 'SKILL.md':
            raise OSError('injected file fsync failure')
        return original_file(path)
    monkeypatch.setattr(skill_history.fs, 'sync', sync)
    monkeypatch.setattr(skill_history, 'durable_file', file)
    assert deletion(h.client, h.item, h.package).status_code == 503
    assert central.is_dir()
    assert (h.store.installed_root / '.preparing.json').exists()
    blocked[0] = False
    calls.clear()
    original_remove = skill_cleanup.shutil.rmtree
    def remove(path, *args, **kwargs):
        if path == central:
            assert ('dir', owner) in calls
            assert ('dir', owner.parent) in calls
            assert any(kind == 'file' and p.name == 'SKILL.md' for kind, p in calls)
        return original_remove(path, *args, **kwargs)
    monkeypatch.setattr(skill_cleanup.shutil, 'rmtree', remove)
    response = deletion(h.client, h.item, h.package)
    assert response.status_code == 200, response.text
    assert not central.exists()
    assert ('dir', owner) in calls and ('dir', owner.parent) in calls


def test_durable_snapshot_syncs_studio_and_execution_ancestors(history, monkeypatch):
    h = history
    job = owned_job(h)
    original, paths = skill_history.fs.sync, []
    def sync(path):
        paths.append(skill_history.fs.checked(path, directory=True))
        return original(path)
    monkeypatch.setattr(skill_history.fs, 'sync', sync)
    assert deletion(h.client, h.item, h.package).status_code == 200
    assert all(skill_history.fs.checked(path, directory=True) in paths
               for path in (job.owner, job.owner.parent, h.root))
