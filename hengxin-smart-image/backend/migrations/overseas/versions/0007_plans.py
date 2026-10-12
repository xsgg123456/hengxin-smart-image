"""Frozen versioned overseas analysis plans."""
from alembic import op
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON,
                        MetaData, String, Table, Text, UniqueConstraint, Uuid)

revision = 'overseas_0007'
down_revision = 'overseas_0006'
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()
    Table('overseas_tasks', metadata, Column('id', Uuid, primary_key=True))
    Table('overseas_jobs', metadata, Column('id', Uuid, primary_key=True))
    plans = Table('overseas_plans', metadata,
        Column('id', Uuid, primary_key=True),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('updated_at', DateTime(timezone=True), nullable=False),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('job_id', ForeignKey('overseas_jobs.id'), nullable=False, unique=True),
        Column('version', Integer, nullable=False), Column('status', String(20), nullable=False),
        Column('feedback', Text, nullable=False), Column('content', JSON),
        UniqueConstraint('task_id', 'version'), CheckConstraint('version >= 1'),
        CheckConstraint("status IN ('pending','ready','confirmed')"))
    plans.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
