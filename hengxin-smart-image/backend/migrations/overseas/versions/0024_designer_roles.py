"""Consolidate overseas roles without replacing members or historical evidence."""
from alembic import op

revision = 'overseas_0024'
down_revision = 'overseas_0023'
branch_labels = depends_on = None


def upgrade():
    # Match the permission-writer lock, then exclude writes during the conversion.
    # A SQL block also makes offline Alembic scripts safe to apply and repeat.
    op.execute('SELECT pg_advisory_xact_lock(7318041802)')
    op.execute('LOCK TABLE overseas_members, overseas_member_roles IN ACCESS EXCLUSIVE MODE')
    op.execute("""
        UPDATE overseas_members SET version = version + 1, updated_at = CURRENT_TIMESTAMP
        WHERE id IN (SELECT user_id FROM overseas_member_roles
                     WHERE role IN ('operator', 'operator_manager'))
    """)
    op.execute("""
        UPDATE overseas_member_roles
        SET role = CASE role WHEN 'operator' THEN 'designer' ELSE 'design_manager' END,
            updated_at = CURRENT_TIMESTAMP
        WHERE role IN ('operator', 'operator_manager')
    """)
    # 0001 used an unnamed CHECK; do not assume a deployment-specific generated name.
    op.execute("""
        DO $$ DECLARE role_check record;
        BEGIN
            FOR role_check IN
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'overseas_member_roles'::regclass AND contype = 'c'
                  AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                      WHERE attrelid = 'overseas_member_roles'::regclass AND attname = 'role')]
            LOOP
                EXECUTE format('ALTER TABLE overseas_member_roles DROP CONSTRAINT %I', role_check.conname);
            END LOOP;
            ALTER TABLE overseas_member_roles ADD CONSTRAINT ck_overseas_member_roles_role
                CHECK (role IN ('designer', 'design_manager', 'super_admin'));
        END $$
    """)


def downgrade():
    raise RuntimeError('Role consolidation is forward-only; downgrade is not supported')
