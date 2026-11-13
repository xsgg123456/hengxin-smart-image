"""Durably request output recovery without restarting the model."""
from alembic import op
import sqlalchemy as sa

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('domestic_studio_turns')}
    if 'recovery_requested' in columns:
        raise RuntimeError('Existing delivery retry column requires manual verification')
    op.add_column('domestic_studio_turns', sa.Column('recovery_requested', sa.Boolean(),
                                                   nullable=False, server_default=sa.false()))


def downgrade():
    raise RuntimeError('Domestic Studio delivery recovery state must be preserved.')
