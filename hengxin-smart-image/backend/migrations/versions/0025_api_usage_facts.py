"""Durable API usage evidence and frozen next-request operator."""
from alembic import op
import sqlalchemy as sa
from app.modules.management.api_stats.models import ApiUsageFact

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    ApiUsageFact.__table__.create(bind, checkfirst=True)
    columns = {column['name'] for column in sa.inspect(bind).get_columns('api_image_items')}
    if 'request_operator_id' not in columns:
        op.add_column('api_image_items', sa.Column('request_operator_id', sa.Uuid(), nullable=True))
    if 'request_is_retry' not in columns:
        op.add_column('api_image_items', sa.Column('request_is_retry', sa.Boolean(), nullable=True))


def downgrade():
    pass  # Facts are retained on rollback; they must survive process-history cleanup.
