"""Domestic installation availability; installed files remain separate."""
from alembic import op
import sqlalchemy as sa

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade():
    name = 'domestic_studio_skill_states'
    if sa.inspect(op.get_bind()).has_table(name):
        raise RuntimeError('Existing domestic studio skill state table requires manual verification')
    op.create_table(
        name,
        sa.Column('name', sa.String(100), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version >= 1'),
    )


def downgrade():
    raise RuntimeError('Disable domestic Skills explicitly before retiring availability state.')
