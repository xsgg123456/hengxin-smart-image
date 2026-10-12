"""Bind newly exchanged domestic sessions to the neutral identity session."""
from alembic import op
from sqlalchemy import Column, String, inspect

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if 'identity_session_id' not in {c['name'] for c in inspect(connection).get_columns('auth_sessions')}:
        op.add_column('auth_sessions', Column('identity_session_id', String(128), nullable=True))
        op.create_index('ix_auth_sessions_identity_session_id', 'auth_sessions', ['identity_session_id'])


def downgrade():
    pass
