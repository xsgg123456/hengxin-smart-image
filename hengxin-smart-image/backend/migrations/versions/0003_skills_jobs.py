"""Skill package versions, defaults and durable job ownership."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('job_records')}
    additions = [sa.Column('kind', sa.String(30), nullable=False, server_default='test'),
                 sa.Column('claim_token', sa.Uuid()), sa.Column('lease_until', sa.DateTime(timezone=True)),
                 sa.Column('error', sa.Text())]
    for column in additions:
        if column.name not in columns:
            op.add_column('job_records', column)
    existing = inspector.get_table_names()
    if 'skills' not in existing:
        op.create_table('skills', sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('mode', sa.String(20), nullable=False),
            sa.Column('description', sa.Text(), nullable=False), *timestamps(),
            sa.UniqueConstraint('name', 'mode'))
    if 'skill_versions' not in existing:
        op.create_table('skill_versions', sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('skill_id', sa.Uuid(), sa.ForeignKey('skills.id'), nullable=False),
            sa.Column('version', sa.String(100), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('checksum', sa.String(64), nullable=False),
            sa.Column('bucket', sa.String(63), nullable=False),
            sa.Column('object_key', sa.String(200), nullable=False, unique=True),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('installed_at', sa.DateTime(timezone=True)),
            sa.Column('node', sa.String(200)), sa.Column('error', sa.Text()),
            sa.Column('installed_path', sa.Text()), sa.Column('current_job_id', sa.Uuid()),
            *timestamps(), sa.UniqueConstraint('skill_id', 'version'))
    if 'module_skill_bindings' not in existing:
        op.create_table('module_skill_bindings', sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('mode', sa.String(20), nullable=False, unique=True),
            sa.Column('skill_version_id', sa.Uuid(), sa.ForeignKey('skill_versions.id')),
            sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id')), *timestamps())
    if 'skill_audits' not in existing:
        op.create_table('skill_audits', sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('action', sa.String(30), nullable=False),
            sa.Column('detail', sa.Text(), nullable=False), *timestamps())


def downgrade():
    op.drop_table('skill_audits')
    op.drop_table('module_skill_bindings')
    op.drop_table('skill_versions')
    op.drop_table('skills')
    for column in ('kind', 'claim_token', 'lease_until', 'error'):
        op.drop_column('job_records', column)
