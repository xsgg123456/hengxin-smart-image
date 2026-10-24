"""Retain non-picture Studio outputs without changing picture or input semantics."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0022'
down_revision = 'overseas_0021'
branch_labels = depends_on = None


def upgrade():
    metadata = sa.MetaData()
    for name in ('overseas_tasks', 'overseas_studio_turns'):
        sa.Table(name, metadata, sa.Column('id', sa.Uuid, primary_key=True))
    table = sa.Table('overseas_studio_output_files', metadata,
        sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        sa.Column('turn_id', sa.ForeignKey('overseas_studio_turns.id'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer, nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('bucket', sa.String(200), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False, unique=True),
        sa.Column('source_path', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    table.create(op.get_bind(), checkfirst=not op.get_context().as_sql)


def downgrade():
    raise RuntimeError('Studio output originals must be retained; migration is forward-only')
