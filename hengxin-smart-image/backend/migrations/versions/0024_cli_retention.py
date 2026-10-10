"""Explicit, initially disabled CLI retention lifecycle and object receipts."""
from alembic import op
from app.retention.models import RetentionEntry, RetentionObject

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade():
    for model in (RetentionEntry, RetentionObject):
        model.__table__.create(op.get_bind(), checkfirst=True)
    # Existing identities are registered on first enabled scan with a fresh 7-day grace.


def downgrade():
    pass  # Never erase cleanup receipts or revive expired memories on rollback.
