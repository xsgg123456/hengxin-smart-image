"""Add content-group visibility without changing any original or historical IDs."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0017'
down_revision = 'overseas_0016'
branch_labels = depends_on = None


def upgrade():
    metadata = sa.MetaData()
    sa.Table('overseas_tasks', metadata, sa.Column('id', sa.Uuid, primary_key=True))
    table = sa.Table('overseas_studio_material_visibility', metadata,
        sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('hidden', sa.Boolean, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('task_id', 'checksum'))
    table.create(op.get_bind(), checkfirst=not op.get_context().as_sql)


def downgrade():
    raise RuntimeError('Material visibility migration is forward-only')
