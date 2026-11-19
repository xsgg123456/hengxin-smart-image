"""Allow an independent, category-neutral new-product workspace."""
from alembic import op

revision = '0046'
down_revision = '0045'
branch_labels = None
depends_on = None

TABLES = ('domestic_studio_skill_bindings', 'domestic_studio_workspaces',
          'domestic_studio_tasks', 'domestic_studio_conversations', 'domestic_studio_archives')
PRODUCTS_0045 = ('camera', 'case', 'film', 'cable', 'earbud', 'accessory')
REPLACEMENTS = ('product', 'scene', 'phone', 'edit')


def replace_checks(products):
    for table in TABLES:
        allowed = products if table == 'domestic_studio_archives' else products + REPLACEMENTS
        name = f'{table}_workspace_check'
        op.drop_constraint(name, table, type_='check')
        op.create_check_constraint(name, table, f'workspace IN {allowed}')


def upgrade():
    replace_checks(('general',) + PRODUCTS_0045)


def downgrade():
    # PostgreSQL refuses the narrower constraint if any general records remain.
    replace_checks(PRODUCTS_0045)
