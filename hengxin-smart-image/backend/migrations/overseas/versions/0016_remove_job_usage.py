"""Remove overseas-only token accounting; raw execution evidence is retained."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0016'
down_revision = 'overseas_0015'
branch_labels = depends_on = None


def upgrade():
    if op.get_context().as_sql or 'usage' in {
            column['name'] for column in sa.inspect(op.get_bind()).get_columns('overseas_jobs')}:
        op.drop_column('overseas_jobs', 'usage')


def downgrade():
    raise RuntimeError('Removed overseas usage accounting cannot be restored')
