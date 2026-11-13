"""Protect frozen Skill objects for owned domestic Studio executions."""
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.overseas.management import installed_catalog as catalog
from app.worker.leases import TERMINAL
from .bindings import freeze_for_send
from .models import SkillExecutionReference
from .skill_state import freeze_enabled

JOB_KIND = 'domestic_studio'


def freeze_and_pin(session, job, workspace, installed, requested_skill_id=None):
    """Resolve the live binding under the gate and pin it in the job transaction."""
    if job.id is None or job.kind != JOB_KIND:
        raise ValueError('Invalid domestic Studio job')
    snapshot = freeze_for_send(session, workspace, requested_skill_id,
        lambda identity: freeze_enabled(session, installed, identity))
    skill = snapshot.get('skill') if isinstance(snapshot, dict) else None
    if (not isinstance(skill, dict)
            or not isinstance(skill.get('name'), str) or not catalog.NAME.fullmatch(skill['name'])
            or not isinstance(skill.get('installedRelease'), str) or not catalog.HASH.fullmatch(skill['installedRelease'])
            or not isinstance(skill.get('checksum'), str) or not catalog.HASH.fullmatch(skill['checksum'])
            or catalog.identity(skill['name']) != skill.get('id')):
        raise ValueError('Invalid domestic Studio Skill snapshot')
    row = SkillExecutionReference(job_id=job.id, name=skill['name'],
                                  release=skill['installedRelease'], checksum=skill['checksum'])
    session.add(row)
    session.flush()
    return snapshot


def pinned(session, store, names):
    """Recheck all ownership before cleanup; never guess when a job lacks a pin."""
    missing = session.scalar(select(Job.id).outerjoin(SkillExecutionReference,
        SkillExecutionReference.job_id == Job.id).where(Job.kind == JOB_KIND,
        SkillExecutionReference.job_id.is_(None)).limit(1))
    if missing is not None:
        raise HTTPException(503, '存在未核实的工作台 Skill 引用，请联系管理员')
    rows = session.execute(select(SkillExecutionReference, Job).join(
        Job, Job.id == SkillExecutionReference.job_id).where(SkillExecutionReference.name.in_(names))).all()
    retained, busy = set(), False
    for reference, job in rows:
        if (job.kind != JOB_KIND or not catalog.NAME.fullmatch(reference.name)
                or not catalog.HASH.fullmatch(reference.release) or not catalog.HASH.fullmatch(reference.checksum)):
            raise ValueError('Invalid domestic Studio Skill reference')
        directory, manifest = catalog.release_manifest(store.installed_root, reference.release, store.protected)
        item = next((item for item in manifest['items'] if item['name'] == reference.name), None)
        if item is None or item['checksum'] != reference.checksum:
            raise ValueError('Domestic Studio Skill reference does not match release')
        catalog.verify_package(directory, item, store.protected)
        retained.add((reference.name, reference.checksum))
        busy |= job.status not in TERMINAL
    return retained, busy
