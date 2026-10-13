"""Independent archives and resumable, verified task erasure."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0013'
down_revision = 'overseas_0012'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(bind)
    columns = set() if offline else {c['name'] for c in inspector.get_columns('overseas_archives')}
    for name, kind in [('product_name', sa.String(80)), ('brand', sa.String(60)),
            ('platform', sa.String(40)), ('skus', sa.JSON), ('sku_search', sa.Text),
            ('created_by', sa.Uuid), ('designer_id', sa.Uuid)]:
        if name not in columns:
            op.add_column('overseas_archives', sa.Column(name, kind, nullable=True))
    op.alter_column('overseas_archives', 'task_id', existing_type=sa.Uuid, nullable=True)
    op.execute(sa.text('''UPDATE overseas_archives AS a SET product_name=t.product_name,
        brand=t.brand, platform=t.platform, created_by=t.created_by, designer_id=t.designer_id,
        sku_search=(SELECT string_agg(s.code, chr(10) ORDER BY s.position)
          FROM overseas_task_skus s WHERE s.task_id=t.id),
        skus=COALESCE((SELECT json_agg(json_build_object('code', s.code) ORDER BY s.position)
          FROM overseas_task_skus s WHERE s.task_id=t.id), '[]'::json)
        FROM overseas_tasks t WHERE a.task_id=t.id AND a.created_by IS NULL'''))
    metadata = sa.MetaData()
    for name in ('overseas_tasks', 'overseas_jobs', 'overseas_archives'):
        sa.Table(name, metadata, sa.Column('id', sa.Uuid, primary_key=True))
    def times():
        return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]
    sa.Table('overseas_task_deletions', metadata,
        sa.Column('task_id', sa.Uuid, primary_key=True), sa.Column('actor_id', sa.Uuid, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('phase', sa.String(30), nullable=False), sa.Column('error', sa.String(200)),
        sa.Column('manifest', sa.JSON, nullable=False), *times())
    sa.Table('overseas_execution_objects', metadata,
        sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        sa.Column('job_id', sa.ForeignKey('overseas_jobs.id'), nullable=False, index=True),
        sa.Column('bucket', sa.String(200), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False, unique=True), *times())
    sa.Table('overseas_archive_assets', metadata,
        sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('archive_id', sa.ForeignKey('overseas_archives.id'), nullable=False, index=True),
        sa.Column('source_version', sa.String(80), nullable=False),
        sa.Column('position', sa.Integer, nullable=False), sa.Column('sku', sa.String(80), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer, nullable=False), sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('width', sa.Integer, nullable=False), sa.Column('height', sa.Integer, nullable=False),
        sa.Column('bucket', sa.String(200), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False, unique=True),
        sa.UniqueConstraint('archive_id', 'source_version'), *times())
    for name in ('overseas_task_deletions', 'overseas_execution_objects', 'overseas_archive_assets'):
        metadata.tables[name].create(bind, checkfirst=not offline)
    indexes = set() if offline else {i['name'] for i in sa.inspect(bind).get_indexes('overseas_archives')}
    for name in ('created_by', 'designer_id'):
        index = 'ix_overseas_archives_' + name
        if index not in indexes:
            op.create_index(index, 'overseas_archives', [name])


def downgrade():
    raise RuntimeError('Task erasure and independent archives are forward-only')
