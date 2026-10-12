"""Frozen Phase19 schema; later runtime models must not alter migration history."""
from alembic import op
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON,
                        MetaData, String, Table, Text, UniqueConstraint, Uuid)

revision = 'overseas_0004'
down_revision = 'overseas_0003'
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()
    # Foreign-key stub only; the existing member table is never created here.
    Table('overseas_members', metadata, Column('id', Uuid, primary_key=True))

    def base_columns():
        return [Column('id', Uuid, primary_key=True),
                Column('created_at', DateTime(timezone=True), nullable=False),
                Column('updated_at', DateTime(timezone=True), nullable=False)]

    tasks = Table('overseas_tasks', metadata, *base_columns(),
        Column('name', String(80), nullable=False), Column('product_name', String(80), nullable=False),
        Column('brand', String(60), nullable=False), Column('platform', String(40), nullable=False),
        Column('market', String(60), nullable=False), Column('remarks', Text, nullable=False),
        Column('created_by', ForeignKey('overseas_members.id'), nullable=False, index=True),
        Column('designer_id', ForeignKey('overseas_members.id'), nullable=False, index=True),
        Column('status', String(40), nullable=False), Column('version', Integer, nullable=False),
        CheckConstraint('version >= 1'))
    skus = Table('overseas_task_skus', metadata, *base_columns(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('code', String(80), nullable=False), Column('code_key', String(240), nullable=False),
        Column('position', Integer, nullable=False),
        UniqueConstraint('task_id', 'code_key'), UniqueConstraint('task_id', 'position'))
    events = Table('overseas_task_events', metadata, *base_columns(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('kind', String(40), nullable=False),
        Column('actor_id', ForeignKey('overseas_members.id'), nullable=False),
        Column('actor_name', String(200), nullable=False), Column('title', String(200), nullable=False),
        Column('before_designer_id', ForeignKey('overseas_members.id')),
        Column('after_designer_id', ForeignKey('overseas_members.id'), nullable=False),
        Column('version', Integer, nullable=False), UniqueConstraint('task_id', 'version'))
    requests = Table('overseas_task_requests', metadata, *base_columns(),
        Column('user_id', ForeignKey('overseas_members.id'), nullable=False),
        Column('operation', String(40), nullable=False), Column('target', String(100), nullable=False),
        Column('key', String(128), nullable=False), Column('body_hash', String(64), nullable=False),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False),
        UniqueConstraint('user_id', 'operation', 'target', 'key'))
    outbox = Table('overseas_task_outbox', metadata, *base_columns(),
        Column('event_id', ForeignKey('overseas_task_events.id'), nullable=False, unique=True),
        Column('topic', String(40), nullable=False), Column('payload', JSON, nullable=False),
        Column('published_at', DateTime(timezone=True)))
    for table in (tasks, skus, events, requests, outbox):
        table.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
