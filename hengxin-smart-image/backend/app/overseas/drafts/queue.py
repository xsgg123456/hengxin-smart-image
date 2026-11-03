"""Short, fenced transactions around durable job ownership."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import and_, or_, select, update
from app.db.timestamps import utcnow
from app.overseas.auth.models import Member
from app.overseas.permissions import authorize_member
from app.overseas.materials.models import Material
from .models import DraftImport, DraftMaterial, RequirementDraft

LEASE_SECONDS = 90


def claim(factory):
    with factory.begin() as session:
        now = utcnow()
        row = session.scalar(select(DraftImport).where(or_(
            and_(DraftImport.state == 'queued', DraftImport.available_at <= now),
            and_(DraftImport.state == 'running', DraftImport.lease_until < now)))
            .order_by(DraftImport.available_at, DraftImport.id).limit(1).with_for_update(skip_locked=True))
        if row is None:
            return None
        row.state, row.lease_token = 'running', uuid4()
        row.lease_until, row.attempts, row.error = now + timedelta(seconds=LEASE_SECONDS), row.attempts + 1, None
        session.flush()
        return SimpleNamespace(**{key: getattr(row, key) for key in
            ('id', 'draft_id', 'epoch', 'owner_id', 'sku', 'requirement_id', 'source_file_id',
             'filename', 'size', 'kind', 'lease_token', 'attempts')})


def renew(factory, job, progress):
    with factory.begin() as session:
        changed = session.execute(update(DraftImport).where(DraftImport.id == job.id,
            DraftImport.lease_token == job.lease_token, DraftImport.state == 'running')
            .values(lease_until=utcnow() + timedelta(seconds=LEASE_SECONDS), progress=progress))
        return changed.rowcount == 1


def complete(factory, job, record):
    with factory.begin() as session:
        # Same lock order as user edits: member -> draft -> import.
        actor = session.scalar(select(Member).where(Member.id == job.owner_id).with_for_update())
        draft = session.scalar(select(RequirementDraft).where(RequirementDraft.id == job.draft_id)
                               .with_for_update())
        row = session.scalar(select(DraftImport).where(DraftImport.id == job.id).with_for_update())
        if (not actor or not draft or draft.epoch != job.epoch or not row
                or row.lease_token != job.lease_token or row.state != 'running'):
            return False
        authorize_member(session, actor, 'task.create')
        material = Material(id=record.id, owner_id=job.owner_id, kind=job.kind, name=job.filename,
            bucket=record.bucket, object_key=record.object_key, content_type=record.content_type,
            checksum=record.checksum, size_bytes=record.size_bytes, status='ready', version=0)
        session.add(material)
        session.flush()
        session.add(DraftMaterial(draft_id=draft.id, epoch=job.epoch, material_id=material.id))
        row.state, row.progress, row.material_id = 'ready', 100, material.id
        row.error, row.lease_token, row.lease_until = None, None, None
        return True


def fail(factory, job, error):
    with factory.begin() as session:
        row = session.scalar(select(DraftImport).where(DraftImport.id == job.id,
            DraftImport.lease_token == job.lease_token, DraftImport.state == 'running').with_for_update())
        if row is None:
            return
        row.state = 'queued' if row.attempts < 3 else 'failed'
        row.error, row.lease_token, row.lease_until = error[:300], None, None
        row.available_at = utcnow() + timedelta(seconds=10 * row.attempts)
