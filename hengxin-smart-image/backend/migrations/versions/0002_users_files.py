"""Stable users, private image metadata and shared deletion audit."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if 'users' not in existing:
        op.create_table('users',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('role', sa.String(32)),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('identity_source', sa.String(20), nullable=False),
            *timestamps(),
            sa.CheckConstraint("status IN ('active','pending','disabled')"),
            sa.CheckConstraint("role IN ('super_admin','design_manager','designer','operator')"),
        )
    if 'files' not in existing:
        op.create_table('files',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('bucket', sa.String(63), nullable=False),
            sa.Column('object_key', sa.String(200), nullable=False, unique=True),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('checksum', sa.String(64), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('width', sa.Integer(), nullable=False),
            sa.Column('height', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True)),
            *timestamps(), sa.CheckConstraint("status IN ('staging','ready','failed')"),
        )
    if 'deletion_records' not in existing:
        op.create_table('deletion_records',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('resource_type', sa.String(30), nullable=False),
            sa.Column('resource_id', sa.Uuid(), nullable=False),
            sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
            *timestamps(),
        )
        op.create_index('ix_deletion_records_resource_id', 'deletion_records', ['resource_id'])


def downgrade():
    op.drop_table('deletion_records')
    op.drop_table('files')
    op.drop_table('users')
