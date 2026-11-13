"""Domestic workspace binding; no Skill packages or default assignments."""
from alembic import op
import sqlalchemy as sa

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    name = 'domestic_studio_skill_bindings'
    inspector = sa.inspect(bind)
    if inspector.has_table(name):
        # Refuse an untracked pre-existing table: superficially similar columns
        # or a permissive CHECK are not proof of a compatible migration.
        raise RuntimeError('Existing domestic studio binding table requires manual verification')
    op.create_table(
        name,
        sa.Column('workspace', sa.String(20), primary_key=True),
        sa.Column('skill_id', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("workspace IN ('camera','case','product','scene','phone')"),
    )


def downgrade():
    raise RuntimeError('Remove bindings explicitly before retiring domestic studio configuration.')
