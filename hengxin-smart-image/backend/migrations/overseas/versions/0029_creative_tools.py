"""Add overseas creative workbench entry, creator snapshots and independent Skill bindings."""
from alembic import op

revision = 'overseas_0029'
down_revision = 'overseas_0028'
branch_labels = depends_on = None


def upgrade():
    op.execute('SELECT pg_advisory_xact_lock(7318041802)')
    op.execute('ALTER TABLE overseas_member_roles DROP CONSTRAINT IF EXISTS ck_overseas_member_roles_role')
    op.execute("""
        ALTER TABLE overseas_member_roles ADD CONSTRAINT ck_overseas_member_roles_role
        CHECK (role IN ('designer', 'design_manager', 'super_admin', 'non_designer'))
    """)
    op.execute('ALTER TABLE overseas_tasks ADD COLUMN IF NOT EXISTS tool_key VARCHAR(40)')
    for table in ('overseas_tasks', 'overseas_archives'):
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS creator_identity VARCHAR(20)')
    op.execute("""
        CREATE TABLE IF NOT EXISTS overseas_tool_skill_bindings (
            tool_key VARCHAR(40) NOT NULL,
            skill_name VARCHAR(100) NOT NULL REFERENCES overseas_installed_skill_availability(id) ON DELETE CASCADE,
            PRIMARY KEY (tool_key, skill_name)
        )
    """)


def downgrade():
    raise RuntimeError('Creative task identities and tool bindings require overseas_0029')
