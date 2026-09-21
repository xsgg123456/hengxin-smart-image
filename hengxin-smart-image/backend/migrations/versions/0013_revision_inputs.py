"""Persist the selected unmarked result and optional annotation for a revision."""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('execution_rounds')}
    for name, table in [('base_version_id', 'image_versions'), ('annotation_file_id', 'files')]:
        if name not in columns:
            op.add_column('execution_rounds', sa.Column(name, sa.Uuid(),
                sa.ForeignKey(table + '.id', name='fk_execution_rounds_' + name), nullable=True))


def downgrade():
    for name in ('annotation_file_id', 'base_version_id'):
        op.drop_constraint('fk_execution_rounds_' + name, 'execution_rounds', type_='foreignkey')
        op.drop_column('execution_rounds', name)
