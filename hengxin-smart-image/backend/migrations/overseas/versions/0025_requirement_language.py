"""Persist explicit requirement language and independent archive metadata."""
from alembic import op

revision = 'overseas_0025'
down_revision = 'overseas_0024'
branch_labels = depends_on = None


def upgrade():
    # IF NOT EXISTS supports offline SQL and safe retry after partial manual DDL.
    op.execute('ALTER TABLE overseas_tasks ADD COLUMN IF NOT EXISTS language VARCHAR(2)')
    op.execute('ALTER TABLE overseas_archives ADD COLUMN IF NOT EXISTS task_name VARCHAR(80)')
    op.execute('ALTER TABLE overseas_archives ADD COLUMN IF NOT EXISTS language VARCHAR(2)')
    op.execute('''
        UPDATE overseas_archives AS archive
        SET task_name = COALESCE(archive.task_name, task.name),
            language = COALESCE(archive.language, task.language)
        FROM overseas_tasks AS task
        WHERE archive.task_id = task.id
          AND (archive.task_name IS NULL OR archive.language IS NULL)
    ''')


def downgrade():
    op.drop_column('overseas_archives', 'language')
    op.drop_column('overseas_archives', 'task_name')
    op.drop_column('overseas_tasks', 'language')
