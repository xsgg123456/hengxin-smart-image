"""Member authorization versions and transactional audit trail."""
from alembic import context, op
from sqlalchemy import Column, Integer, inspect, text

from app.overseas.members.models import MemberAudit

revision = 'overseas_0003'
down_revision = 'overseas_0002'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = set() if context.is_offline_mode() else {
        column['name'] for column in inspect(bind).get_columns('overseas_members')}
    if 'version' not in columns:
        op.add_column('overseas_members', Column('version', Integer, nullable=False, server_default='1'))
    MemberAudit.__table__.create(bind, checkfirst=True)
    # Older installs retain all existing identities and authorizations.
    bind.execute(text('UPDATE overseas_members SET version = 1 WHERE version IS NULL'))


def downgrade():
    pass
