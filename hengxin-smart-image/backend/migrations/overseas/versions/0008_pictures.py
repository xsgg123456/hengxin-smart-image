"""Frozen picture slots, immutable image versions and archive snapshots."""
import json
from uuid import UUID, uuid4
from datetime import datetime, timezone
from alembic import op
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, JSON, MetaData, String,
                        Table, Text, UniqueConstraint, CheckConstraint, Uuid, inspect, text, select)
revision = 'overseas_0008'
down_revision = 'overseas_0007'
branch_labels = None
depends_on = None

BACKFILL_SQL = """
INSERT INTO overseas_pictures
 (id,task_id,plan_id,job_id,sku,position,title,version,created_at,updated_at)
SELECT md5(j.id::text || ':' || p.ordinality::text)::uuid,
 j.task_id,(j.payload::jsonb->>'planId')::uuid,j.id,
 j.payload::jsonb->'sku'->>'code',p.ordinality-1,p.value->>'title',0,now(),now()
FROM overseas_jobs j CROSS JOIN LATERAL
 jsonb_array_elements(COALESCE(j.payload::jsonb#>'{sku,pictures}','[]'::jsonb))
 WITH ORDINALITY p(value,ordinality)
WHERE j.kind='generation' AND j.payload::jsonb->>'planId' IS NOT NULL
ON CONFLICT (task_id,sku,position) DO NOTHING
"""


def timestamps():
    return [Column('created_at', DateTime(timezone=True), nullable=False),
            Column('updated_at', DateTime(timezone=True), nullable=False)]


def upgrade():
    metadata = MetaData()
    for name in ('overseas_tasks', 'overseas_plans', 'overseas_jobs'):
        Table(name, metadata, Column('id', Uuid, primary_key=True))
    pictures = Table('overseas_pictures', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('plan_id', ForeignKey('overseas_plans.id'), nullable=False),
        Column('job_id', ForeignKey('overseas_jobs.id'), nullable=False),
        Column('sku', String(80), nullable=False), Column('position', Integer, nullable=False),
        Column('title', String(300), nullable=False), Column('version', Integer, nullable=False),
        Column('approved_version', Integer), UniqueConstraint('task_id', 'sku', 'position'),
        CheckConstraint('version >= 0'))
    versions = Table('overseas_picture_versions', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('picture_id', ForeignKey('overseas_pictures.id'), nullable=False, index=True),
        Column('job_id', ForeignKey('overseas_jobs.id'), nullable=False),
        Column('version', Integer, nullable=False), Column('bucket', String(200), nullable=False),
        Column('object_key', String(500), nullable=False, unique=True), Column('name', String(200), nullable=False),
        Column('content_type', String(80), nullable=False), Column('size_bytes', Integer, nullable=False),
        Column('checksum', String(64), nullable=False), Column('width', Integer, nullable=False),
        Column('height', Integer, nullable=False), Column('note', Text, nullable=False),
        Column('marks', JSON, nullable=False), UniqueConstraint('picture_id', 'version'),
        CheckConstraint('version >= 1'))
    archives = Table('overseas_archives', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, unique=True),
        Column('versions', JSON, nullable=False))
    for table in (pictures, versions, archives):
        table.create(op.get_bind(), checkfirst=True)
    if op.get_context().as_sql:
        op.execute(BACKFILL_SQL)
    else:
        backfill(op.get_bind(), pictures)


def downgrade():
    pass


def backfill(connection, pictures):
    # Phase22 may already have confirmed plans; preserve their exact frozen ordering.
    inspector = inspect(connection)
    if not inspector.has_table('overseas_jobs'):
        return
    rows = connection.execute(text("SELECT id, task_id, payload FROM overseas_jobs WHERE kind = 'generation'"))
    for job_id, task_id, payload in rows:
        payload = json.loads(payload) if isinstance(payload, str) else payload
        if not payload.get('planId') or not payload.get('sku'):
            continue
        for position, spec in enumerate(payload['sku']['pictures']):
            exists = connection.scalar(select(pictures.c.id).where(
                pictures.c.task_id == UUID(str(task_id)), pictures.c.sku == payload['sku']['code'],
                pictures.c.position == position))
            if not exists:
                connection.execute(pictures.insert().values(id=uuid4(), task_id=UUID(str(task_id)),
                    plan_id=UUID(payload['planId']), job_id=UUID(str(job_id)), sku=payload['sku']['code'],
                    position=position, title=spec['title'], version=0,
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
