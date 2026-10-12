"""Frozen overseas persistent execution and admission schema."""
from alembic import op, context
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        Integer, JSON, MetaData, String, Table, Uuid, select)
from datetime import datetime, timezone

revision = 'overseas_0006'
down_revision = 'overseas_0005'
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()
    Table('overseas_tasks', metadata, Column('id', Uuid, primary_key=True))

    def timestamps():
        return [Column('created_at', DateTime(timezone=True), nullable=False),
                Column('updated_at', DateTime(timezone=True), nullable=False)]

    gate = Table('overseas_execution_gate', metadata,
        Column('id', Integer, primary_key=True), Column('paused', Boolean, nullable=False),
        *timestamps(), CheckConstraint('id = 1'))
    jobs = Table('overseas_jobs', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('kind', String(20), nullable=False), Column('dedupe_key', String(200), nullable=False, unique=True),
        Column('payload', JSON, nullable=False), Column('status', String(20), nullable=False, index=True),
        Column('version', Integer, nullable=False), Column('claim_token', Uuid),
        Column('lease_until', DateTime(timezone=True)), Column('worker_node', String(200)),
        Column('process_id', Integer), Column('process_boot', String(200)), Column('process_started', String(200)),
        Column('process_exited', Boolean, nullable=False), Column('cancel_requested', Boolean, nullable=False),
        Column('result', JSON), Column('error', String(500)), Column('started_at', DateTime(timezone=True)),
        Column('completed_at', DateTime(timezone=True)), Column('execution_count', Integer, nullable=False),
        CheckConstraint('version >= 1'),
        CheckConstraint("kind IN ('analysis','reanalysis','generation','revision')"),
        CheckConstraint("status IN ('queued','running','collecting','cancelling','uncertain','succeeded','failed','cancelled')"))
    outbox = Table('overseas_job_outbox', metadata,
        Column('job_id', ForeignKey('overseas_jobs.id'), primary_key=True), *timestamps(),
        Column('dispatch_count', Integer, nullable=False),
        Column('next_dispatch_at', DateTime(timezone=True), nullable=False),
        Column('completed_at', DateTime(timezone=True)))
    events = Table('overseas_execution_events', metadata,
        Column('id', Integer, primary_key=True, autoincrement=True), *timestamps(),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('job_id', ForeignKey('overseas_jobs.id'), nullable=False, index=True),
        Column('status', String(20), nullable=False), Column('message', String(100), nullable=False))
    connection = op.get_bind()
    for table in (gate, jobs, outbox, events):
        table.create(connection, checkfirst=True)
    if context.is_offline_mode():
        op.execute("INSERT INTO overseas_execution_gate (id, paused, created_at, updated_at) "
                   "VALUES (1, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (id) DO NOTHING")
    elif not connection.execute(select(gate.c.id).where(gate.c.id == 1)).scalar():
        now = datetime.now(timezone.utc)
        connection.execute(gate.insert().values(id=1, paused=False, created_at=now, updated_at=now))


def downgrade():
    pass
