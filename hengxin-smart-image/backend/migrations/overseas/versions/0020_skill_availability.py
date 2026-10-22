"""Durable installed Skill switches; only the two approved OUTON packages start enabled."""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0020'
down_revision = 'overseas_0019'
branch_labels = depends_on = None


def upgrade():
    table = sa.Table('overseas_installed_skill_availability', sa.MetaData(),
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('enabled', sa.Boolean, nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version >= 1'))
    table.create(op.get_bind(), checkfirst=not op.get_context().as_sql)
    from sqlalchemy.dialects.postgresql import insert
    now = datetime.now(timezone.utc)
    for name in ('amazon-new-product-image-set', 'amazon-new-product-aplus'):
        op.execute(insert(table).values(id=name, enabled=True, version=1,
                                       created_at=now, updated_at=now).on_conflict_do_nothing(index_elements=['id']))


def downgrade():
    raise RuntimeError('Skill availability migration is forward-only')
