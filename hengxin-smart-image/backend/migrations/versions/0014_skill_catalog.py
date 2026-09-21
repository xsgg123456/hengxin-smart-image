"""Stable Skill catalog state and immutable automatic snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('skills')}
    for column in [sa.Column('catalog_path', sa.String(100), nullable=True),
        sa.Column('catalog_status', sa.String(20), nullable=True),
        sa.Column('catalog_error', sa.Text(), nullable=True),
        sa.Column('current_version_id', sa.Uuid(), nullable=True),
        sa.Column('manually_disabled', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('removed', sa.Boolean(), server_default=sa.false(), nullable=False)]:
        if column.name not in columns:
            op.add_column('skills', column)
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('skills')}
    if 'uq_skills_catalog_path' not in indexes:
        op.create_index('uq_skills_catalog_path', 'skills', ['catalog_path'], unique=True)
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('skill_versions')}
    if 'catalog_snapshot' not in columns:
        op.add_column('skill_versions', sa.Column('catalog_snapshot', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM skill_versions WHERE catalog_snapshot = true')).scalar():
        raise RuntimeError('Cannot downgrade while automatic Skill snapshots exist')
    op.drop_column('skill_versions', 'catalog_snapshot')
    op.drop_index('uq_skills_catalog_path', table_name='skills')
    for name in ('removed', 'manually_disabled', 'current_version_id', 'catalog_error', 'catalog_status', 'catalog_path'):
        op.drop_column('skills', name)
