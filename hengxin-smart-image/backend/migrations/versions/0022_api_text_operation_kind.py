"""Preserve the operation type on successful API versions."""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('api_image_versions')}
    if 'kind' not in columns:
        op.add_column('api_image_versions', sa.Column('kind', sa.String(20), nullable=True))


def downgrade():
    # Retain operation evidence when rolling back application code.
    pass
