"""Frozen Phase20 source document and parsing history schema."""
from alembic import op
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Integer,
                        MetaData, String, Table, Text, UniqueConstraint, Uuid)

revision = 'overseas_0005'
down_revision = 'overseas_0004'
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()
    Table('overseas_members', metadata, Column('id', Uuid, primary_key=True))
    Table('overseas_tasks', metadata, Column('id', Uuid, primary_key=True))

    def base_columns():
        return [Column('id', Uuid, primary_key=True),
                Column('created_at', DateTime(timezone=True), nullable=False),
                Column('updated_at', DateTime(timezone=True), nullable=False)]

    materials = Table('overseas_materials', metadata, *base_columns(),
        Column('owner_id', ForeignKey('overseas_members.id'), nullable=False, index=True),
        Column('task_id', ForeignKey('overseas_tasks.id'), index=True),
        Column('kind', String(20), nullable=False), Column('name', String(255), nullable=False),
        Column('bucket', String(200), nullable=False),
        Column('object_key', String(200), nullable=False, unique=True),
        Column('content_type', String(100), nullable=False), Column('checksum', String(64), nullable=False),
        Column('size_bytes', Integer, nullable=False), Column('status', String(20), nullable=False),
        Column('version', Integer, nullable=False), Column('deleted_at', DateTime(timezone=True)),
        UniqueConstraint('task_id', 'kind'), CheckConstraint("kind IN ('requirement', 'competitor')"),
        CheckConstraint('version >= 0'))
    versions = Table('overseas_material_versions', metadata, *base_columns(),
        Column('material_id', ForeignKey('overseas_materials.id'), nullable=False, index=True),
        Column('version', Integer, nullable=False), Column('status', String(20), nullable=False),
        Column('parser_version', String(80), nullable=False), Column('text', Text, nullable=False),
        Column('error', String(500)), UniqueConstraint('material_id', 'version'), CheckConstraint('version >= 1'))
    for table in (materials, versions):
        table.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
