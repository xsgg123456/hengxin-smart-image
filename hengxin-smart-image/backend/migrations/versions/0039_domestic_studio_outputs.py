"""Retain non-image files delivered by a domestic Studio conversation."""
from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None


def upgrade():
    name = 'domestic_studio_output_files'
    if sa.inspect(op.get_bind()).has_table(name):
        raise RuntimeError('Existing domestic Studio output table requires manual verification')
    op.create_table(name,
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('turn_id', sa.Uuid(), sa.ForeignKey('domestic_studio_turns.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('bucket', sa.String(200), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False, unique=True),
        sa.Column('source_path', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_domestic_studio_output_files_turn_id', name, ['turn_id'])


def downgrade():
    raise RuntimeError('Domestic Studio output files must be preserved.')
