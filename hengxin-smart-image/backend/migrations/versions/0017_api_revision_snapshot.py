"""Freeze multi-image revision inputs without changing legacy edit cycles."""
from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('api_image_items')}
    if 'revision_snapshot' not in columns:
        op.add_column('api_image_items', sa.Column('revision_snapshot', sa.JSON(), nullable=True))


def downgrade():
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('api_image_items')}
    if 'revision_snapshot' not in columns:
        return
    items = sa.Table('api_image_items', sa.MetaData(), autoload_with=bind)
    # JSON null and SQL NULL both represent legacy cycles. Any real snapshot
    # must survive rollback, including failed edits that can be retried later.
    if any(snapshot is not None for snapshot in bind.execute(sa.select(items.c.revision_snapshot)).scalars()):
        raise RuntimeError('Cannot discard frozen API image revision snapshots')
    op.drop_column('api_image_items', 'revision_snapshot')
