"""Durable, finite display derivatives. Originals remain untouched."""
from alembic import op
import sqlalchemy as sa

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('image_variants'):
        op.create_table('image_variants',
            sa.Column('domain', sa.String(24), primary_key=True),
            sa.Column('file_id', sa.Uuid(), primary_key=True),
            sa.Column('source_checksum', sa.String(64), nullable=False),
            sa.Column('outputs', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('next_attempt', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('lease_until', sa.DateTime(timezone=True)), sa.Column('token', sa.Uuid()),
            sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
            *(sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
              for name in ('created_at', 'updated_at')))
        op.create_index('ix_image_variants_next_attempt', 'image_variants', ['next_attempt'])
        op.create_index('ix_image_variants_completed', 'image_variants', ['completed'])


def downgrade():
    # Retain resumable jobs and objects when reverting the application.
    pass
