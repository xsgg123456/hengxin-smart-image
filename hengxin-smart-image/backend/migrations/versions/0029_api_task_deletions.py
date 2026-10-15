"""Explicit task erasure only; never enqueue historical soft-deleted tasks."""
from alembic import op
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade():
    ApiTaskDeletion.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Pending deletion fences and receipts must survive application rollback.
