"""Persist versioned runtime settings and their audit trail."""
from alembic import op
from app.modules.management.models import SystemSettings, SettingsAuditRecord

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    SystemSettings.__table__.create(op.get_bind(), checkfirst=True)
    SettingsAuditRecord.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    SettingsAuditRecord.__table__.drop(op.get_bind(), checkfirst=True)
    SystemSettings.__table__.drop(op.get_bind(), checkfirst=True)
