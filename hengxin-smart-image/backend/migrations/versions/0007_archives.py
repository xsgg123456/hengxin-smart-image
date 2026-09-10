"""Immutable archive snapshots and durable request receipts."""
from alembic import op
from app.modules.archives.models import ArchiveRecord, ArchiveImage, ArchiveRequest
from app.worker.cleanup_models import CleanupObject

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None
TABLES = [ArchiveRecord, ArchiveImage, ArchiveRequest, CleanupObject]


def upgrade():
    for model in TABLES:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in reversed(TABLES):
        model.__table__.drop(op.get_bind(), checkfirst=True)
