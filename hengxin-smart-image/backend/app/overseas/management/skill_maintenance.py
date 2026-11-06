"""Operator-only whole-library reclamation through the private publisher socket."""
import json

from fastapi import HTTPException
from sqlalchemy import select

from app.overseas.execution.models import Job
from app.overseas.execution.queue import lock_gate
from app.overseas.execution import skill_history
from . import installed_catalog as catalog, skill_cleanup as cleanup
from . import skill_references as references, skill_publication as publication
from . import skill_preparation as preparation
from .installed_tree import read_file
from .models import Audit


def names_in_library(store):
    names = set()
    releases = store.installed_root / 'releases'
    for path in releases.iterdir():
        if catalog.HASH.fullmatch(path.name):
            _, manifest = catalog.release_manifest(store.installed_root, path.name, store.protected)
            names.update(item['name'] for item in manifest['items'])
    return names


def verify_inputs(session, jobs):
    """Reject unaccounted frozen disk inputs rather than silently dropping their only source."""
    owners = references.owners(session, jobs)
    expected = {(str(owner), skill['installedRelease'], skill['name'], skill['checksum'])
                for _, owner, skill in owners}
    root = references.execution_root()
    count = 0
    for pattern in ('studio/*/control/*/input.json', 'studio/*/rounds/*/input.json',
                    '*/control/*/input.json', '*/rounds/*/input.json'):
        for path in root.glob(pattern):
            document = json.loads(read_file(path))
            skill = document.get('skill')
            if not isinstance(skill, dict) or not skill.get('installedRelease'):
                continue
            owner = path.parent.parent.parent
            key = (str(owner), skill['installedRelease'], skill['name'], skill['checksum'])
            if key not in expected:
                raise ValueError('Unaccounted historical Skill input; reclamation refused')
            count += 1
    return owners, count


def reclaim(store, session, actor_id, expected_release, dry_run=True):
    actor = publication.authorize(session, actor_id)
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    if release != expected_release:
        if not dry_run:
            for audit in session.scalars(select(Audit).where(Audit.action == 'skill.reclaim', Audit.actor_id == actor.id)
                                         .order_by(Audit.created_at.desc())):
                if (audit.before.get('release') == expected_release and audit.after.get('release') == release
                        and audit.after.get('cleanupComplete')):
                    return audit.after
        raise HTTPException(409, '安装目录已变化，请重新核对清理清单')
    names = names_in_library(store)
    preparation.guard(store, names)
    jobs = references.locked(session, names, deleting=True)
    if not lock_gate(session).paused or any(references.busy(job) for job in session.scalars(select(Job))):
        raise HTTPException(409, '全量回收仅允许停止接纳并排空全部任务后执行')
    owners, input_count = verify_inputs(session, jobs)
    present = 0
    for _, owner, skill in owners:
        _, item, _ = catalog.frozen_item(skill)
        if owner.exists() and skill_history.find(owner, item):
            present += 1
        else:
            catalog.frozen_package(skill)  # Must have a verified source before attempting preservation.
    before = cleanup.footprint(store)
    summary = dict(release=release, libraryBytes=cleanup.library_footprint(store),
                   centralBytes=before, skills=len(items), historyContents=len(owners),
                   existingHistoryContents=present, frozenInputs=input_count, jobs=len(jobs))
    if dry_run:
        return dict(summary, dryRun=True)
    baseline = preparation.begin(store, session, jobs, names)
    summary['centralBytes'] = baseline['beforeBytes']
    references.preserve(session, jobs)
    history_bytes = preparation.history_bytes(baseline)
    # Preserve original catalog metadata byte-for-byte; read_catalog derives display titles.
    _, original_manifest = catalog.release_manifest(store.installed_root, release, store.protected)
    updated = publication.prepare_release(store, original_manifest['items'])
    retained = {(item['name'], item['checksum']) for item in items}
    cleanup_plan = cleanup.plan(store, names, retained, baseline['beforeBytes'], history_bytes)
    after = dict(summary, release=updated, historyBytes=history_bytes, dryRun=False, targets=len(cleanup_plan['targets']))
    result = publication.switch(store, session, actor, 'skill.reclaim', 'installed-library', summary,
                                after, updated, cleanup_plan)
    # Re-read all frozen content from its actual owner after central removal.
    for _, owner, skill in owners:
        _, item, _ = catalog.frozen_item(skill)
        if skill_history.find(owner, item) is None:
            raise ValueError('Historical Skill did not survive reclamation')
    current, verified = catalog.read_catalog(store.installed_root, store.protected)
    if verified != items or current != updated:
        raise ValueError('Current Skill catalog changed during reclamation')
    return result
