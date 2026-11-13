"""Journal Skill publication independently of overseas audit records."""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    name = 'domestic_studio_skill_publication_audit'
    if sa.inspect(op.get_bind()).has_table(name):
        raise RuntimeError('Existing domestic Skill publication journal requires manual verification')
    op.create_table(
        name,
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('target', sa.String(100), nullable=False),
        sa.Column('before', sa.JSON(), nullable=False),
        sa.Column('after', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    raise RuntimeError('Skill publication audit is required for recovery.')
