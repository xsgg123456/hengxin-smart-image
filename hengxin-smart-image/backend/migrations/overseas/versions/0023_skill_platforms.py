"""Approved initial associations; switches and installed package bytes stay intact."""
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa

revision = 'overseas_0023'
down_revision = 'overseas_0022'
branch_labels = depends_on = None

# Frozen from the approved preview, deliberately independent of future app code.
INITIAL = {
    'amazon-main-image-product-swap-1600': ['Amazon'],
    'amazon-main-image-product-swap-1250': ['Amazon'],
    'amazon-aplus-product-swap': ['Amazon'],
    'wayfair-new-product-image-set-main': ['Wayfair'],
    'wayfair-new-product-image-set-main-aplus': ['Wayfair'],
    'overseas-product-image-swap': [],
    'walmart-new-product-image-set-original': ['Walmart'],
    'walmart-new-product-image-set-revised-0927': ['Walmart'],
    'beleev-amazon-image-set': ['Amazon'],
    'beleev-amazon-aplus': ['Amazon'],
    'outonlife-amazon-image-set': ['Amazon'],
    'amazon-outonlife-new-product-aplus': ['Amazon'],
    'amazon-new-product-image-set': ['Amazon'],
    'amazon-new-product-aplus': ['Amazon'],
    'outon-brand-image-design-version-1023-night': ['Amazon'],
}


def upgrade():
    name = 'overseas_installed_skill_availability'
    # The column and seed commit atomically. A repeat must preserve later edits,
    # including an explicitly cleared association, rather than applying seeds again.
    if not op.get_context().as_sql:
        if 'platforms' in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(name)}:
            return
    op.add_column(name, sa.Column('platforms', sa.JSON(), nullable=False, server_default='[]'))
    table = sa.table(name, sa.column('id', sa.String), sa.column('enabled', sa.Boolean),
        sa.column('version', sa.Integer), sa.column('platforms', sa.JSON),
        sa.column('created_at', sa.DateTime(timezone=True)), sa.column('updated_at', sa.DateTime(timezone=True)))
    from sqlalchemy.dialects.postgresql import insert
    now = datetime.now(timezone.utc)
    for identity, platforms in INITIAL.items():
        # JSON as a SQL CAST supports Alembic --sql as well as bound execution.
        value = sa.cast(sa.literal(json.dumps(platforms)), sa.JSON)
        op.execute(insert(table).values(id=identity, enabled=False, version=1, platforms=value,
            created_at=now, updated_at=now).on_conflict_do_update(
                index_elements=['id'], set_={'platforms': value}))


def downgrade():
    raise RuntimeError('Skill platform migration is forward-only')
