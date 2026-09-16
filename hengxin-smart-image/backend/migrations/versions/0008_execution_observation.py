"""Durable, public-safe execution observations; existing attempts remain nullable."""
from alembic import op
from sqlalchemy import Column, JSON, inspect

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    if 'observation' not in {c['name'] for c in inspect(op.get_bind()).get_columns('execution_attempts')}:
        op.add_column('execution_attempts', Column('observation', JSON(none_as_null=True), nullable=True))


def downgrade():
    if 'observation' in {c['name'] for c in inspect(op.get_bind()).get_columns('execution_attempts')}:
        op.drop_column('execution_attempts', 'observation')
