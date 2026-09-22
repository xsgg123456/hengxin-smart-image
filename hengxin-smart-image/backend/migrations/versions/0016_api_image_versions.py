"""Per-item leases, frozen revision inputs and immutable successful versions."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('api_image_items')}
    additions = [sa.Column('lease_token', sa.Uuid()),
                 sa.Column('lease_until', sa.DateTime(timezone=True)),
                 sa.Column('current_version', sa.Integer()),
                 sa.Column('revision_base_version', sa.Integer()),
                 sa.Column('revision_text', sa.Text())]
    for name, table in [('revision_source_id', 'api_image_files'),
                        ('revision_annotation_id', 'api_image_files'),
                        ('revision_operator_id', 'users')]:
        additions.append(sa.Column(name, sa.Uuid(), sa.ForeignKey(f'{table}.id')))
    for column in additions:
        if column.name not in columns:
            op.add_column('api_image_items', column)
    if not sa.inspect(bind).has_table('api_image_versions'):
        op.create_table('api_image_versions',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('item_id', sa.Uuid(), sa.ForeignKey('api_image_items.id'), nullable=False),
            sa.Column('number', sa.Integer(), nullable=False),
            sa.Column('file_id', sa.Uuid(), sa.ForeignKey('api_image_files.id'), nullable=False),
            sa.Column('operator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('annotation_id', sa.Uuid(), sa.ForeignKey('api_image_files.id')),
            sa.Column('base_version', sa.Integer()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('item_id', 'number'))
        op.create_index('ix_api_image_versions_item_id', 'api_image_versions', ['item_id'])
    metadata = sa.MetaData()
    items = sa.Table('api_image_items', metadata, autoload_with=bind)
    tasks = sa.Table('api_image_tasks', metadata, autoload_with=bind)
    versions = sa.Table('api_image_versions', metadata, autoload_with=bind)
    gate = sa.Table('api_image_channel', metadata, autoload_with=bind)
    rows = bind.execute(sa.select(items.c.id, items.c.result_id, items.c.updated_at,
        tasks.c.owner_id, tasks.c.prompt).join(tasks, items.c.task_id == tasks.c.id)
        .where(items.c.result_id.is_not(None), items.c.current_version.is_(None))).mappings()
    for row in rows:
        exists = bind.execute(sa.select(versions.c.id).where(
            versions.c.item_id == row['id'], versions.c.number == 1)).first()
        if not exists:
            bind.execute(versions.insert().values(id=uuid4(), item_id=row['id'], number=1,
                file_id=row['result_id'], operator_id=row['owner_id'], text=row['prompt'],
                created_at=row['updated_at'], updated_at=row['updated_at']))
        bind.execute(items.update().where(items.c.id == row['id']).values(current_version=1))
    # Preserve in-flight ownership and uncertainty; never reset an active item to queued.
    for row in bind.execute(sa.select(gate)).mappings():
        if row['item_id'] and row['token']:
            bind.execute(items.update().where(items.c.id == row['item_id'],
                items.c.lease_token.is_(None)).values(lease_token=row['token'], lease_until=row['lease_until']))


def downgrade():
    bind = op.get_bind()
    count = bind.execute(sa.text('SELECT count(*) FROM api_image_versions WHERE number > 1')).scalar()
    active = bind.execute(sa.text("SELECT count(*) FROM api_image_items WHERE revision_base_version "
                                 "IS NOT NULL OR lease_token IS NOT NULL")).scalar()
    if count or active:
        raise RuntimeError('Cannot discard API image history or active leases')
    op.drop_table('api_image_versions')
    for name in ['revision_operator_id', 'revision_annotation_id', 'revision_source_id',
                 'revision_text', 'revision_base_version', 'current_version', 'lease_until', 'lease_token']:
        op.drop_column('api_image_items', name)
