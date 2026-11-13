"""Persist private conversation cleanup ownership and recovery state."""
from alembic import op
import sqlalchemy as sa

revision = '0043'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade():
    name = 'domestic_studio_conversation_deletions'
    if sa.inspect(op.get_bind()).has_table(name):
        raise RuntimeError('Existing conversation deletion table requires manual verification')
    op.create_table(name, sa.Column('conversation_id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('workspace', sa.String(20), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('manifest', sa.JSON(), nullable=False), sa.Column('error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index(f'ix_{name}_owner_id', name, ['owner_id'])
    op.create_index(f'ix_{name}_status', name, ['status'])


def downgrade():
    raise RuntimeError('Domestic conversation deletion receipts must be preserved.')
