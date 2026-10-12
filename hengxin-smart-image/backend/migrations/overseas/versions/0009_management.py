"""Independent immutable skills, audited configuration and nullable CLI usage."""
from alembic import op
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer,
                        JSON, MetaData, String, Table, UniqueConstraint, Uuid, inspect)

revision = 'overseas_0009'
down_revision = 'overseas_0008'
branch_labels = depends_on = None


def timestamps():
    return [Column('created_at', DateTime(timezone=True), nullable=False),
            Column('updated_at', DateTime(timezone=True), nullable=False)]


def upgrade():
    metadata = MetaData()
    Table('overseas_members', metadata, Column('id', Uuid, primary_key=True))
    skills = Table('overseas_skills', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('name', String(100), nullable=False, unique=True), Column('stage', String(20), nullable=False),
        Column('enabled', Boolean, nullable=False), Column('version', Integer, nullable=False),
        Column('current_version', Integer, nullable=False),
        CheckConstraint("stage IN ('analysis','generation','revision')"))
    versions = Table('overseas_skill_versions', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('skill_id', ForeignKey('overseas_skills.id'), nullable=False),
        Column('version', Integer, nullable=False), Column('files', JSON, nullable=False),
        UniqueConstraint('skill_id', 'version'))
    settings = Table('overseas_settings', metadata, Column('id', Integer, primary_key=True), *timestamps(),
        Column('version', Integer, nullable=False), Column('values', JSON, nullable=False), CheckConstraint('id = 1'))
    audit = Table('overseas_management_audit', metadata, Column('id', Uuid, primary_key=True), *timestamps(),
        Column('actor_id', ForeignKey('overseas_members.id'), nullable=False),
        Column('action', String(80), nullable=False), Column('target', String(100), nullable=False),
        Column('before', JSON, nullable=False), Column('after', JSON, nullable=False))
    offline = op.get_context().as_sql
    for table in (skills, versions, settings, audit):
        table.create(op.get_bind(), checkfirst=not offline)
    if offline or 'usage' not in {c['name'] for c in inspect(op.get_bind()).get_columns('overseas_jobs')}:
        op.add_column('overseas_jobs', Column('usage', JSON, nullable=True))
    op.execute("""INSERT INTO overseas_settings (id,version,values,created_at,updated_at)
        VALUES (1,1,'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) ON CONFLICT (id) DO NOTHING""")


def downgrade():
    pass
