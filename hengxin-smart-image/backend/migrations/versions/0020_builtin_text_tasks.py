"""Allow text-only tasks without a Skill; preserve all legacy snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name']: c for c in sa.inspect(op.get_bind()).get_columns('task_records')}
    with op.batch_alter_table('task_records') as batch:
        if 'builtin_prompt' not in columns:
            batch.add_column(sa.Column('builtin_prompt', sa.JSON(), nullable=True))
        if not columns['skill_version_id']['nullable']:
            batch.alter_column('skill_version_id', existing_type=sa.Uuid(), nullable=True)


def downgrade():
    # Keeping nullable Skill and immutable prompts avoids destroying new tasks.
    pass
