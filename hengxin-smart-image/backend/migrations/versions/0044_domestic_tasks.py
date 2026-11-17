"""Create domestic business tasks without changing execution/storage identities."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = '0044'
down_revision = '0043'
branch_labels = None
depends_on = None

NAMES = {'camera': '相机配件生成', 'case': '手机壳生成', 'product': '只换产品',
         'scene': '换场景 / 模特 / 产品 / 修改尺寸', 'phone': '换手机 / 壁纸 / 膜'}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('domestic_studio_tasks') or inspector.has_table('domestic_studio_task_requests'):
        raise RuntimeError('Existing domestic tasks require migration-state verification')
    columns = {column['name'] for column in inspector.get_columns('domestic_studio_conversations')}
    if 'task_id' in columns:
        raise RuntimeError('Existing conversation task column requires verification')
    op.create_table('domestic_studio_tasks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('workspace', sa.String(20), nullable=False),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deletion_status', sa.String(20)), sa.Column('deletion_error', sa.Text()),
        sa.Column('deletion_manifest', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('id', 'owner_id', 'workspace', name='uq_domestic_task_owner_workspace'),
        sa.CheckConstraint("workspace IN ('camera','case','product','scene','phone')"),
        sa.CheckConstraint('length(trim(name)) BETWEEN 1 AND 60'),
        sa.CheckConstraint("deletion_status IS NULL OR deletion_status IN ('deleting','delete_failed','deleted')"))
    for field in ('owner_id', 'workspace'):
        op.create_index('ix_domestic_studio_tasks_' + field, 'domestic_studio_tasks', [field])
    op.create_table('domestic_studio_task_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operation', sa.String(40), nullable=False), sa.Column('target', sa.String(80), nullable=False),
        sa.Column('key', sa.String(128), nullable=False), sa.Column('body_hash', sa.String(64), nullable=False),
        sa.Column('task_id', sa.Uuid(), sa.ForeignKey('domestic_studio_tasks.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'operation', 'target', 'key'))
    op.add_column('domestic_studio_conversations', sa.Column('task_id', sa.Uuid(), nullable=True))
    op.add_column('domestic_studio_conversation_deletions', sa.Column('task_id', sa.Uuid(), nullable=True))
    groups = bind.execute(sa.text('SELECT owner_id, workspace, min(created_at) AS created_at, '
        'max(updated_at) AS updated_at FROM domestic_studio_conversations GROUP BY owner_id, workspace')).mappings()
    for group in groups:
        identity = uuid4()
        bind.execute(sa.text('INSERT INTO domestic_studio_tasks '
            '(id,owner_id,workspace,name,created_at,updated_at) VALUES '
            '(:id,:owner_id,:workspace,:name,:created_at,:updated_at)'),
            dict(group) | {'id': identity, 'name': '历史任务 · ' + NAMES[group['workspace']]})
        bind.execute(sa.text('UPDATE domestic_studio_conversations SET task_id=:id '
            'WHERE owner_id=:owner_id AND workspace=:workspace'),
            {'id': identity, 'owner_id': group['owner_id'], 'workspace': group['workspace']})
    bind.execute(sa.text('UPDATE domestic_studio_conversation_deletions d SET task_id=c.task_id '
        'FROM domestic_studio_conversations c WHERE c.id=d.conversation_id '
        'AND c.owner_id=d.owner_id AND c.workspace=d.workspace'))
    op.alter_column('domestic_studio_conversations', 'task_id', nullable=False)
    op.create_index('ix_domestic_studio_conversations_task_id', 'domestic_studio_conversations', ['task_id'])
    op.create_foreign_key('fk_domestic_conversation_task_owner_workspace', 'domestic_studio_conversations',
        'domestic_studio_tasks', ['task_id', 'owner_id', 'workspace'], ['id', 'owner_id', 'workspace'])
    op.create_foreign_key('fk_domestic_deletion_task', 'domestic_studio_conversation_deletions',
                         'domestic_studio_tasks', ['task_id'], ['id'])


def downgrade():
    raise RuntimeError('Domestic task ownership and receipts must be preserved; restore the audited backup for rollback.')
