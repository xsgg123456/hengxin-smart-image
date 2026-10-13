"""Enforce one overseas business role, preserving administrator migration evidence."""
from uuid import uuid4
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = 'overseas_0011'
down_revision = 'overseas_0010'
branch_labels = depends_on = None


def upgrade():
    if op.get_context().as_sql:
        offline_upgrade()
        return
    bind = op.get_bind()
    metadata = sa.MetaData()
    members = sa.Table('overseas_members', metadata, sa.Column('id', sa.Uuid, primary_key=True), autoload_with=bind)
    roles = sa.Table('overseas_member_roles', metadata, sa.Column('user_id', sa.Uuid), autoload_with=bind)
    audits = sa.Table('overseas_member_audits', metadata, sa.Column('id', sa.Uuid, primary_key=True),
                      sa.Column('member_id', sa.Uuid), sa.Column('actor_id', sa.Uuid), autoload_with=bind)
    # Validate the entire population before writing; never guess a business role.
    grouped = {}
    for row in bind.execute(sa.select(roles.c.user_id, roles.c.role)):
        grouped.setdefault(row.user_id, []).append(row.role)
    ambiguous = [str(uid) for uid, values in grouped.items()
                 if len(values) > 1 and 'super_admin' not in values]
    roleless = [str(uid) for uid in bind.scalars(sa.select(members.c.id).where(
        members.c.status == 'active', ~members.c.id.in_(list(grouped))))]
    if ambiguous or roleless:
        raise RuntimeError('请明确唯一角色后重试迁移；多角色成员: ' + ', '.join(sorted(ambiguous))
                           + '；启用但未授权成员: ' + ', '.join(sorted(roleless)))
    now = datetime.now(timezone.utc)
    for uid, values in grouped.items():
        if len(values) <= 1:
            continue
        member = bind.execute(sa.select(members).where(members.c.id == uid)).mappings().one()
        bind.execute(roles.delete().where(roles.c.user_id == uid, roles.c.role != 'super_admin'))
        bind.execute(members.update().where(members.c.id == uid).values(
            version=member['version'] + 1, updated_at=now))
        bind.execute(audits.insert().values(id=uuid4(), member_id=uid, actor_id=None,
            action='single_role_migration', created_at=now, updated_at=now,
            before={'roles': sorted(values), 'status': member['status'], 'version': member['version']},
            after={'roles': ['super_admin'], 'status': member['status'], 'version': member['version'] + 1}))
    constraints = sa.inspect(bind).get_unique_constraints(roles.name)
    if not any(c['column_names'] == ['user_id'] for c in constraints):
        with op.batch_alter_table(roles.name) as batch:
            batch.create_unique_constraint('uq_overseas_member_single_role', ['user_id'])


def downgrade():
    raise RuntimeError('Single-role audit migration is forward-only')


def offline_upgrade():
    # Offline output still checks the actual data when applied by PostgreSQL.
    op.execute("""DO $$ DECLARE invalid_ids text; BEGIN
      SELECT string_agg(id::text, ', ') INTO invalid_ids FROM overseas_members m
      WHERE (SELECT count(*) FROM overseas_member_roles r WHERE r.user_id=m.id)>1
        AND NOT EXISTS (SELECT 1 FROM overseas_member_roles r WHERE r.user_id=m.id AND r.role='super_admin')
        OR (m.status='active' AND NOT EXISTS (SELECT 1 FROM overseas_member_roles r WHERE r.user_id=m.id));
      IF invalid_ids IS NOT NULL THEN RAISE EXCEPTION '请明确唯一角色后重试迁移，成员: %', invalid_ids; END IF;
    END $$""")
    op.execute("""INSERT INTO overseas_member_audits
      (id, member_id, actor_id, action, before, after, created_at, updated_at)
      SELECT gen_random_uuid(), m.id, NULL, 'single_role_migration',
        json_build_object('roles', (SELECT json_agg(role ORDER BY role) FROM overseas_member_roles WHERE user_id=m.id),
                          'status', m.status, 'version', m.version),
        json_build_object('roles', json_build_array('super_admin'), 'status', m.status, 'version', m.version+1), now(), now()
      FROM overseas_members m WHERE (SELECT count(*) FROM overseas_member_roles WHERE user_id=m.id)>1""")
    op.execute("""UPDATE overseas_members m SET version=version+1, updated_at=now()
      WHERE (SELECT count(*) FROM overseas_member_roles WHERE user_id=m.id)>1""")
    op.execute("""DELETE FROM overseas_member_roles r WHERE r.role <> 'super_admin'
      AND EXISTS (SELECT 1 FROM overseas_member_roles a WHERE a.user_id=r.user_id AND a.role='super_admin')""")
    op.create_unique_constraint('uq_overseas_member_single_role', 'overseas_member_roles', ['user_id'])
