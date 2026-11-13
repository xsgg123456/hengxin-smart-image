"""Creator-owned domestic Studio sessions and durable mutation receipts."""
from alembic import op
import sqlalchemy as sa

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def timestamps():
    return (sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def upgrade():
    bind = op.get_bind()
    names = ('domestic_studio_workspaces', 'domestic_studio_conversations',
             'domestic_studio_conversation_requests')
    if any(sa.inspect(bind).has_table(name) for name in names):
        raise RuntimeError('Existing domestic Studio conversation tables require manual verification')
    check = "workspace IN ('camera','case','product','scene','phone')"
    op.create_table(names[0],
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('workspace', sa.String(20), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint(check), *timestamps())
    op.create_table(names[1],
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('workspace', sa.String(20), nullable=False),
        sa.Column('name', sa.String(30), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('session_id', sa.String(128)),
        sa.ForeignKeyConstraint(['owner_id', 'workspace'], [names[0] + '.owner_id', names[0] + '.workspace']),
        sa.CheckConstraint(check), *timestamps())
    op.create_index('ix_domestic_studio_conversations_owner_id', names[1], ['owner_id'])
    op.create_table(names[2],
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operation', sa.String(40), nullable=False),
        sa.Column('target', sa.String(80), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('body_hash', sa.String(64), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.UniqueConstraint('user_id', 'operation', 'target', 'key'), *timestamps())


def downgrade():
    raise RuntimeError('Domestic Studio conversations must be preserved.')
