"""Explicit applications and directory classification; historical schema frozen here."""
from alembic import context, op
import sqlalchemy as sa

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None

MEMBERS = 'users'
APPLICATIONS = 'domestic_membership_applications'
EVENTS = 'domestic_membership_application_events'
AUDITS = 'domestic_member_audits'


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now())]


def upgrade():
    bind = op.get_bind()
    offline = context.is_offline_mode()
    columns = set() if offline else {column['name'] for column in sa.inspect(bind).get_columns(MEMBERS)}
    if 'directory_state' not in columns:
        op.add_column(MEMBERS, sa.Column('directory_state', sa.String(32), nullable=False,
                                         server_default='enrolled'))
        op.create_check_constraint('ck_users_directory_state', MEMBERS,
                                   "directory_state IN ('enrolled','legacy_unconfirmed')")
        op.execute(sa.text("UPDATE users SET directory_state = 'legacy_unconfirmed' "
                           "WHERE status = 'pending'"))
    if offline or not sa.inspect(bind).has_table(APPLICATIONS):
        op.create_table(APPLICATIONS,
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('corp_id', sa.String(200), nullable=False),
            sa.Column('provider_user_id', sa.String(200), nullable=False),
            sa.Column('union_id', sa.String(200)),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('department', sa.String(200), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('reason', sa.String(1000)),
            *timestamps(),
            sa.UniqueConstraint('corp_id', 'provider_user_id', name='uq_domestic_application_identity'),
            sa.CheckConstraint("status IN ('pending','approved','rejected','withdrawn')"))
    if offline or not sa.inspect(bind).has_table(EVENTS):
        op.create_table(EVENTS,
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('application_id', sa.Uuid(), sa.ForeignKey(APPLICATIONS + '.id'), nullable=False),
            sa.Column('actor_id', sa.Uuid()),
            sa.Column('action', sa.String(32), nullable=False),
            sa.Column('before', sa.JSON(), nullable=False),
            sa.Column('after', sa.JSON(), nullable=False),
            *timestamps())
        op.create_index('ix_' + EVENTS + '_application_id', EVENTS, ['application_id'])
    if offline or not sa.inspect(bind).has_table(AUDITS):
        op.create_table(AUDITS,
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('member_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('actor_id', sa.Uuid()),
            sa.Column('action', sa.String(32), nullable=False),
            sa.Column('before', sa.JSON(), nullable=False),
            sa.Column('after', sa.JSON(), nullable=False),
            *timestamps())
        op.create_index('ix_domestic_member_audits_member_id', AUDITS, ['member_id'])


def downgrade():
    op.drop_table(AUDITS)
    op.drop_table(EVENTS)
    op.drop_table(APPLICATIONS)
    op.drop_constraint('ck_users_directory_state', MEMBERS, type_='check')
    op.drop_column(MEMBERS, 'directory_state')
