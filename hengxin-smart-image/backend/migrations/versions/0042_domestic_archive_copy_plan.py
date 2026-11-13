"""Persist archive copy ownership before writing any independent object."""
from alembic import op
import sqlalchemy as sa

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade():
    archive, files = 'domestic_studio_archives', 'domestic_studio_archive_files'
    inspector = sa.inspect(op.get_bind())
    if ({'status', 'error'} & {column['name'] for column in inspector.get_columns(archive)}
            or {'status', 'source_bucket', 'source_object_key'} & {column['name'] for column in inspector.get_columns(files)}):
        raise RuntimeError('Existing domestic archive copy state requires manual verification')
    op.add_column(archive, sa.Column('status', sa.String(20), nullable=False, server_default='preparing'))
    op.add_column(archive, sa.Column('error', sa.Text()))
    op.add_column(files, sa.Column('source_bucket', sa.String(200), nullable=True))
    op.add_column(files, sa.Column('source_object_key', sa.String(500), nullable=True))
    op.add_column(files, sa.Column('status', sa.String(20), nullable=False, server_default='pending'))
    # These tables were created by this same unpublished migration chain.
    if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {archive}')).scalar_one():
        raise RuntimeError('Unexpected archive rows before copy-plan migration')
    op.alter_column(files, 'source_bucket', existing_type=sa.String(200), nullable=False)
    op.alter_column(files, 'source_object_key', existing_type=sa.String(500), nullable=False)


def downgrade():
    raise RuntimeError('Domestic archive copy plans must be preserved.')
