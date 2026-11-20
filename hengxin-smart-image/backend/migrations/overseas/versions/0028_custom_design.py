"""Persist design type on tasks and their independent archive snapshots."""
from alembic import op

revision = 'overseas_0028'
down_revision = 'overseas_0027'
branch_labels = depends_on = None


def upgrade():
    for table, title in [('overseas_tasks', 'name'), ('overseas_archives', 'task_name')]:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS design_type VARCHAR(20) NOT NULL DEFAULT 'platform'")
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {title} TYPE VARCHAR(161)')


def downgrade():
    raise RuntimeError('Custom task and archive identities require the overseas_0028 schema')
