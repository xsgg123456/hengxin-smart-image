"""Independent, domestic-shared archive copies and deletion receipts."""
from alembic import op
import sqlalchemy as sa

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def timestamps():
    return (sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def upgrade():
    names = ('domestic_studio_archives', 'domestic_studio_archive_files',
             'domestic_studio_archive_requests', 'domestic_studio_archive_deletions')
    if any(sa.inspect(op.get_bind()).has_table(name) for name in names):
        raise RuntimeError('Existing domestic archive tables require manual verification')
    op.create_table(names[0], sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('workspace', sa.String(20), nullable=False),
        sa.Column('source_conversation_id', sa.Uuid(), nullable=False),
        sa.Column('source_conversation_name', sa.String(30), nullable=False),
        sa.Column('product_name', sa.String(60), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.CheckConstraint("workspace IN ('camera','case')"), *timestamps())
    for column in ('owner_id', 'workspace', 'source_conversation_id', 'product_name'):
        op.create_index(f'ix_{names[0]}_{column}', names[0], [column])
    op.create_table(names[1], sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('archive_id', sa.Uuid(), sa.ForeignKey(names[0] + '.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False), sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False), sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False), sa.Column('bucket', sa.String(200), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False, unique=True),
        sa.Column('width', sa.Integer()), sa.Column('height', sa.Integer()),
        sa.UniqueConstraint('archive_id', 'kind', 'source_id'),
        sa.CheckConstraint("kind IN ('upload','picture','output')"), *timestamps())
    op.create_index(f'ix_{names[1]}_archive_id', names[1], ['archive_id'])
    op.create_table(names[2], sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operation', sa.String(40), nullable=False), sa.Column('target', sa.String(80), nullable=False),
        sa.Column('key', sa.String(128), nullable=False), sa.Column('body_hash', sa.String(64), nullable=False),
        sa.Column('archive_id', sa.Uuid(), nullable=False),
        sa.UniqueConstraint('user_id', 'operation', 'target', 'key'), *timestamps())
    op.create_table(names[3], sa.Column('archive_id', sa.Uuid(), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('error', sa.Text()), *timestamps())
    op.create_index(f'ix_{names[3]}_status', names[3], ['status'])


def downgrade():
    raise RuntimeError('Domestic Studio archives must be preserved.')
