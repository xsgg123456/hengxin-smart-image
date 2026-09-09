"""Shared templates and immutable ordered snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if 'templates' not in existing:
        op.create_table('templates',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True)), *timestamps())
    if 'template_versions' not in existing:
        op.create_table('template_versions',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('template_id', sa.Uuid(), sa.ForeignKey('templates.id'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('mode', sa.String(20), nullable=False),
            sa.Column('notes', sa.Text(), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('skill_binding', sa.String(20), nullable=False),
            sa.Column('skill_version_id', sa.Uuid(), sa.ForeignKey('skill_versions.id')),
            sa.Column('skill_name', sa.String(200), nullable=False), *timestamps(),
            sa.UniqueConstraint('template_id', 'version'),
            sa.CheckConstraint("mode IN ('wallpaper','product')"),
            sa.CheckConstraint("skill_binding IN ('module_default','specific')"))
    if 'template_images' not in existing:
        op.create_table('template_images',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('template_version_id', sa.Uuid(), sa.ForeignKey('template_versions.id'), nullable=False),
            sa.Column('file_id', sa.Uuid(), sa.ForeignKey('files.id'), nullable=False),
            sa.Column('slot', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(200), nullable=False), *timestamps(),
            sa.UniqueConstraint('template_version_id', 'slot'),
            sa.CheckConstraint('slot >= 0 AND slot < 20'))


def downgrade():
    op.drop_table('template_images')
    op.drop_table('template_versions')
    op.drop_table('templates')
