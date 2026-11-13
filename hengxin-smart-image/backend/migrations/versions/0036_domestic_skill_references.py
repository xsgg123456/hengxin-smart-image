"""Protect Skill bytes needed by domestic Studio executions."""
from alembic import op
import sqlalchemy as sa

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade():
    name = 'domestic_studio_skill_references'
    if sa.inspect(op.get_bind()).has_table(name):
        raise RuntimeError('Existing domestic Skill reference table requires manual verification')
    op.create_table(
        name,
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('job_records.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('release', sa.String(64), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_domestic_studio_skill_references_name', name, ['name'])


def downgrade():
    raise RuntimeError('Skill execution references must be preserved.')
