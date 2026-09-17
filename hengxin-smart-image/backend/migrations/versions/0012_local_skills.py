"""Local published versions have no object-store package."""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('skill_versions')}
    if 'source_type' not in columns:
        op.add_column('skill_versions', sa.Column('source_type', sa.String(10),
                                                nullable=False, server_default='zip'))
    if 'description' not in columns:
        op.add_column('skill_versions', sa.Column('description', sa.Text(), nullable=True))
    op.alter_column('skill_versions', 'bucket', existing_type=sa.String(63), nullable=True)
    op.alter_column('skill_versions', 'object_key', existing_type=sa.String(200), nullable=True)


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM skill_versions WHERE source_type = 'local' LIMIT 1")).first():
        raise RuntimeError('Remove unreferenced local registrations before downgrade; never delete bound versions')
    op.alter_column('skill_versions', 'bucket', existing_type=sa.String(63), nullable=False)
    op.alter_column('skill_versions', 'object_key', existing_type=sa.String(200), nullable=False)
    op.drop_column('skill_versions', 'source_type')
    op.drop_column('skill_versions', 'description')
