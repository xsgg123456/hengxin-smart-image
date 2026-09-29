"""Keep per-attempt size evidence nullable for historical requests."""
from alembic import op
import sqlalchemy as sa

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('api_image_attempts')}
    for name in ('request_width', 'request_height', 'return_width', 'return_height'):
        if name not in columns:
            op.add_column('api_image_attempts', sa.Column(name, sa.Integer(), nullable=True))


def downgrade():
    # Retain observed evidence when rolling application code back.
    pass
