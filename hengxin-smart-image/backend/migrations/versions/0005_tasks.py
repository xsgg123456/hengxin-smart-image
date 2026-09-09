"""Durable generation snapshots, idempotency and result publication."""
from alembic import op
from app.modules.tasks.models import (TaskRecord, RoundRecord, TaskRequest, TaskSource,
    ResultSlotRecord, ImageVersion, ExecutionGate)
from app.models import utcnow

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None
TABLES = [TaskRecord, RoundRecord, TaskRequest, TaskSource, ResultSlotRecord, ImageVersion, ExecutionGate]


def upgrade():
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=True)
    gate = ExecutionGate.__table__
    if not bind.execute(gate.select().where(gate.c.id == 1)).first():
        bind.execute(gate.insert().values(id=1, created_at=utcnow(), updated_at=utcnow()))


def downgrade():
    for model in reversed(TABLES):
        model.__table__.drop(op.get_bind(), checkfirst=True)
