"""Persistent task studio, with legacy task and archive compatibility."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0012'
down_revision = 'overseas_0011'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(bind)
    if offline or 'workflow' not in {c['name'] for c in inspector.get_columns('overseas_tasks')}:
        op.add_column('overseas_tasks', sa.Column('workflow', sa.String(20), nullable=False, server_default='legacy'))
    if offline or 'assets' not in {c['name'] for c in inspector.get_columns('overseas_skill_versions')}:
        op.add_column('overseas_skill_versions', sa.Column('assets', sa.JSON, nullable=False, server_default='{}'))
    if offline:
        op.drop_constraint('overseas_jobs_kind_check', 'overseas_jobs', type_='check')
    for constraint in ([] if offline else inspector.get_check_constraints('overseas_jobs')):
        if 'kind' in constraint['sqltext'] and 'studio' not in constraint['sqltext']:
            op.drop_constraint(constraint['name'], 'overseas_jobs', type_='check')
    checks = [] if offline else sa.inspect(bind).get_check_constraints('overseas_jobs')
    if not any('studio' in c['sqltext'] for c in checks):
        op.create_check_constraint('overseas_jobs_kind_check', 'overseas_jobs',
                                   "kind IN ('analysis','reanalysis','generation','revision','studio')")
    metadata = sa.MetaData()
    for name in ('overseas_tasks', 'overseas_jobs', 'overseas_members'):
        sa.Table(name, metadata, sa.Column('id', sa.Uuid, primary_key=True))
    def common():
        return [sa.Column('id', sa.Uuid, primary_key=True),
                sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]
    def task():
        return sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True)
    def file_columns():
        return [sa.Column('name', sa.String(255), nullable=False),
            sa.Column('content_type', sa.String(100), nullable=False),
            sa.Column('size_bytes', sa.Integer, nullable=False),
            sa.Column('checksum', sa.String(64), nullable=False),
            sa.Column('bucket', sa.String(200), nullable=False),
            sa.Column('object_key', sa.String(500), nullable=False, unique=True)]
    sa.Table('overseas_studio_conversations', metadata, *common(),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), unique=True, nullable=False),
        sa.Column('session_id', sa.String(128)))
    sa.Table('overseas_studio_turns', metadata, *common(), task(),
        sa.Column('conversation_id', sa.ForeignKey('overseas_studio_conversations.id'), nullable=False),
        sa.Column('job_id', sa.ForeignKey('overseas_jobs.id'), nullable=False, unique=True),
        sa.Column('actor_id', sa.ForeignKey('overseas_members.id'), nullable=False),
        sa.Column('text', sa.Text, nullable=False), sa.Column('skill_name', sa.String(100)),
        sa.Column('attachment_ids', sa.JSON, nullable=False), sa.Column('reference_ids', sa.JSON, nullable=False),
        sa.Column('reply', sa.Text), sa.Column('dispatched', sa.Boolean, nullable=False))
    sa.Table('overseas_studio_uploads', metadata, *common(), task(), *file_columns())
    sa.Table('overseas_studio_pictures', metadata, *common(), task(), *file_columns(),
        sa.Column('turn_id', sa.ForeignKey('overseas_studio_turns.id'), nullable=False, index=True),
        sa.Column('width', sa.Integer, nullable=False), sa.Column('height', sa.Integer, nullable=False),
        sa.Column('sku', sa.String(80)))
    for name in ('conversations', 'turns', 'uploads', 'pictures'):
        metadata.tables['overseas_studio_' + name].create(bind, checkfirst=not offline)


def downgrade():
    raise RuntimeError('Studio history migration is forward-only')
