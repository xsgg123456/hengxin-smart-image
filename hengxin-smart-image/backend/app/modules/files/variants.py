"""Two immutable display sizes; originals and authorization remain authoritative."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, JSON, String, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, utcnow
from app.resource_models import Timestamps
from .delivery import FileDelivery

SIZES = (256, 1024)


class ImageVariants(Timestamps, Base):
    __tablename__ = 'image_variants'
    domain: Mapped[str] = mapped_column(String(24), primary_key=True)
    file_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_checksum: Mapped[str] = mapped_column(String(64))
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token: Mapped[UUID | None] = mapped_column(Uuid)
    completed: Mapped[bool] = mapped_column(default=False, index=True)


def register(session, record, domain):
    """Register in the same transaction as publishing the ready original."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = sqlite_insert if session.bind.dialect.name == 'sqlite' else pg_insert
    session.execute(insert(ImageVariants).values(domain=domain, file_id=record.id,
        source_checksum=record.checksum, outputs={}, attempts=0, completed=False,
        next_attempt=utcnow()).on_conflict_do_nothing(index_elements=['domain', 'file_id']))


def representation(session, original, domain, size):
    row = session.get(ImageVariants, (domain, original.id))
    if row is None:
        register(session, original, domain)
        session.commit()
        return original
    data = row.outputs.get(str(size)) if row.source_checksum == original.checksum else None
    if not data:
        return original
    return FileDelivery(id=original.id, bucket=original.bucket,
        object_key=f'derived/{domain}/{original.id}/v1-{size}-{data["checksum"]}.webp',
        name=original.name.rsplit('.', 1)[0] + '.webp', content_type='image/webp',
        size_bytes=data['size'], checksum=data['checksum'])


def backfill(factory, limit=100):
    """Bounded, restart-safe legacy discovery. No original is changed or deleted."""
    from app.resource_models import FileRecord
    from app.modules.api_image_edits.models import ApiFile
    total = 0
    for domain, model in [('originals', FileRecord), ('api-image-edits', ApiFile)]:
        with factory.begin() as session:
            registered = select(ImageVariants.file_id).where(
                ImageVariants.domain == domain, ImageVariants.file_id == model.id).exists()
            rows = session.scalars(select(model).where(model.status == 'ready',
                model.deleted_at.is_(None), ~registered).order_by(model.created_at, model.id).limit(limit))
            for row in rows:
                register(session, row, domain)
                total += 1
    return total
