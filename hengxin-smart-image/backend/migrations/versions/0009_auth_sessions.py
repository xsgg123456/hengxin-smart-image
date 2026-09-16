"""Durable DingTalk identity bindings and server-side browser sessions."""
from alembic import op

from app.modules.auth.models import AuthSessionRecord, RoleAssignmentRecord, UserIdentityRecord

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None
TABLES = [UserIdentityRecord, AuthSessionRecord, RoleAssignmentRecord]


def upgrade():
    for model in TABLES:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in reversed(TABLES):
        model.__table__.drop(op.get_bind(), checkfirst=True)
