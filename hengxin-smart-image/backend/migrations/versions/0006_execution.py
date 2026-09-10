"""Persist task sessions, CLI attempts, usage and worker observations."""
from alembic import op
from app.modules.tasks.attempts import (
    ExecutionSession, ExecutionAttempt, ExecutionUsage, WorkerHeartbeat,
)

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None
TABLES = [ExecutionSession, ExecutionAttempt, ExecutionUsage, WorkerHeartbeat]


def upgrade():
    for model in TABLES:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in reversed(TABLES):
        model.__table__.drop(op.get_bind(), checkfirst=True)
