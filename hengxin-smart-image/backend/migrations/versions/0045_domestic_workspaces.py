"""Expand only the workspace checks installed on the domestic 0044 schema."""
from alembic import op

revision = '0045'
down_revision = '0044'
branch_labels = None
depends_on = None


TABLES = ('domestic_studio_skill_bindings', 'domestic_studio_workspaces',
          'domestic_studio_tasks', 'domestic_studio_conversations', 'domestic_studio_archives')
OLD_PRODUCTS = ('camera', 'case')
OLD_REPLACEMENTS = ('product', 'scene', 'phone')


def replace_checks(products, replacements):
    for table in TABLES:
        workspaces = products if table == 'domestic_studio_archives' else products + replacements
        # PostgreSQL names the original inline column checks <table>_workspace_check.
        name = f'{table}_workspace_check'
        op.drop_constraint(name, table, type_='check')
        op.create_check_constraint(name, table, f'workspace IN {workspaces}')


def upgrade():
    replace_checks(OLD_PRODUCTS + ('film', 'cable', 'earbud', 'accessory'), OLD_REPLACEMENTS + ('edit',))


def downgrade():
    # PostgreSQL validates each narrower check transactionally. A new workspace
    # record prevents downgrade without discarding or relabeling business data.
    replace_checks(OLD_PRODUCTS, OLD_REPLACEMENTS)
