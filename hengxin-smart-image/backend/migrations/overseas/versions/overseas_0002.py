"""Independent overseas members, explicit roles and opaque business sessions."""
from alembic import op
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, MetaData,
                        String, Table, UniqueConstraint, Uuid)

revision = 'overseas_0002'
down_revision = 'overseas_0001'
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()

    def timestamps():
        return [Column('created_at', DateTime(timezone=True), nullable=False),
                Column('updated_at', DateTime(timezone=True), nullable=False)]

    members = Table('overseas_members', metadata,
        Column('id', Uuid, primary_key=True), Column('corp_id', String(200), nullable=False),
        Column('provider_user_id', String(200), nullable=False), Column('union_id', String(200)),
        Column('name', String(200), nullable=False), Column('department', String(200), nullable=False),
        Column('status', String(20), nullable=False), *timestamps(),
        UniqueConstraint('corp_id', 'provider_user_id', name='uq_overseas_member_identity'),
        CheckConstraint("status IN ('active','pending','disabled')"))
    roles = Table('overseas_member_roles', metadata,
        Column('id', Uuid, primary_key=True),
        Column('user_id', ForeignKey('overseas_members.id', ondelete='CASCADE'), nullable=False, index=True),
        Column('role', String(32), nullable=False), *timestamps(),
        UniqueConstraint('user_id', 'role', name='uq_overseas_member_role'),
        CheckConstraint("role IN ('operator','operator_manager','designer','design_manager','super_admin')"))
    sessions = Table('overseas_sessions', metadata,
        Column('id', Uuid, primary_key=True),
        Column('user_id', ForeignKey('overseas_members.id', ondelete='CASCADE'), nullable=False, index=True),
        Column('token_hash', String(64), nullable=False, unique=True, index=True),
        Column('identity_session_id', String(128), nullable=False, index=True),
        Column('expires_at', DateTime(timezone=True), nullable=False, index=True),
        Column('last_seen_at', DateTime(timezone=True)), Column('revoked_at', DateTime(timezone=True)),
        *timestamps())
    for table in (members, roles, sessions):
        table.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
