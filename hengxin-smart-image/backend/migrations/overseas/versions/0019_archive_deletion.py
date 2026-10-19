"""Minimal durable receipts for independently deleting archived products."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0019'
down_revision = 'overseas_0018'
branch_labels = depends_on = None


def upgrade():
    table = sa.Table('overseas_archive_deletions', sa.MetaData(),
        sa.Column('archive_id', sa.Uuid, primary_key=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('error', sa.String(200)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    table.create(op.get_bind(), checkfirst=not op.get_context().as_sql)


def downgrade():
    raise RuntimeError('Archive deletion migration is forward-only')
