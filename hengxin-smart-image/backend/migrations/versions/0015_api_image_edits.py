"""Independent API image-edit domain, queue and global channel gate."""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def uid(name, reference=None, nullable=False, primary=False):
    args = [sa.ForeignKey(reference)] if reference else []
    return sa.Column(name, sa.Uuid(), *args, nullable=nullable, primary_key=primary)


def text(name, length=None, nullable=False):
    return sa.Column(name, sa.String(length) if length else sa.Text(), nullable=nullable)


def time(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def integer(name, default='0'):
    return sa.Column(name, sa.Integer(), nullable=False, server_default=default)


def create(name, *columns):
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, time('created_at', False), time('updated_at', False))


def upgrade():
    create('api_image_files', uid('id', primary=True), uid('owner_id', 'users.id'),
        text('name', 200), text('bucket', 63), text('object_key', 200),
        text('content_type', 50), text('checksum', 64), integer('size_bytes'),
        integer('width'), integer('height'), text('status', 20), time('deleted_at'),
        uid('deleted_by', 'users.id', True), sa.UniqueConstraint('object_key'))
    create('api_image_tasks', uid('id', primary=True), uid('owner_id', 'users.id'),
        uid('operator_id', 'users.id'), text('name', 60), text('prompt'),
        uid('material_id', 'api_image_files.id'), sa.Column('parameters', sa.JSON(), nullable=False),
        text('state', 20), text('error', 300, True), sa.Column('events', sa.JSON(), nullable=False),
        time('started_at'), time('completed_at'), time('deleted_at'), uid('deleted_by', 'users.id', True))
    create('api_image_items', uid('id', primary=True), uid('task_id', 'api_image_tasks.id'),
        uid('source_id', 'api_image_files.id'), uid('result_id', 'api_image_files.id', True),
        integer('position'), text('state', 20), integer('retries'), integer('cycle_retries'),
        integer('collection_retries'), time('next_attempt_at'), text('error', 300, True),
        text('result_url', nullable=True), sa.Column('result_bytes', sa.LargeBinary(), nullable=True),
        sa.UniqueConstraint('task_id', 'position'))
    create('api_image_attempts', uid('id', primary=True), uid('item_id', 'api_image_items.id'),
        uid('operator_id', 'users.id'), text('state', 20), text('error', 300, True),
        time('completed_at'), uid('resolved_by', 'users.id', True))
    create('api_image_dispatch', uid('id', 'api_image_tasks.id', primary=True),
        time('next_dispatch_at', False), integer('dispatch_count'), time('completed_at'))
    create('api_image_operations', uid('id', primary=True), uid('operator_id', 'users.id'),
        text('key', 128), text('payload_hash', 64), uid('task_id', 'api_image_tasks.id'),
        sa.UniqueConstraint('operator_id', 'key'))
    create('api_image_channel', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('paused', sa.Boolean(), nullable=False), text('reason', 300, True),
        uid('item_id', 'api_image_items.id', True), uid('token', nullable=True),
        time('lease_until'), sa.CheckConstraint('id = 1'))
    for table, column in [('api_image_tasks', 'state'), ('api_image_items', 'task_id'),
                          ('api_image_attempts', 'item_id'), ('api_image_dispatch', 'next_dispatch_at')]:
        name = f'ix_{table}_{column}'
        if name not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}:
            op.create_index(name, table, [column])
    op.execute(sa.text('INSERT INTO api_image_channel (id, paused, created_at, updated_at) '
                      'VALUES (1, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (id) DO NOTHING'))


def downgrade():
    active = op.get_bind().execute(sa.text("SELECT count(*) FROM api_image_items WHERE state "
                                           "IN ('running','collecting','uncertain','retry_wait','queued')")).scalar()
    if active:
        raise RuntimeError('Cannot downgrade while API image requests are active or uncertain')
    for table in ['api_image_channel', 'api_image_operations', 'api_image_dispatch',
                  'api_image_attempts', 'api_image_items', 'api_image_tasks', 'api_image_files']:
        op.drop_table(table)
