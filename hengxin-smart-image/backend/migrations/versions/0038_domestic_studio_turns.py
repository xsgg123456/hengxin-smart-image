"""Persist domestic Studio inputs and immutable generated image references."""
from alembic import op
import sqlalchemy as sa

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None


def timestamps():
    return (sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def file_fields():
    return (sa.Column('name', sa.String(255), nullable=False),
            sa.Column('content_type', sa.String(100), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('checksum', sa.String(64), nullable=False),
            sa.Column('bucket', sa.String(200), nullable=False),
            sa.Column('object_key', sa.String(500), nullable=False, unique=True))


def upgrade():
    names = ('domestic_studio_turns', 'domestic_studio_uploads',
             'domestic_studio_pictures', 'domestic_studio_transcript')
    if any(sa.inspect(op.get_bind()).has_table(name) for name in names):
        raise RuntimeError('Existing domestic Studio turn tables require manual verification')
    op.create_table(names[0],
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('conversation_id', sa.Uuid(), sa.ForeignKey('domestic_studio_conversations.id'), nullable=False),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('job_records.id'), nullable=False, unique=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('output_intents', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('reply', sa.Text()), sa.Column('error', sa.Text()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('process_identity', sa.JSON()),
        sa.Column('event_offset', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('event_session_id', sa.String(128)),
        sa.Column('event_invalid', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('dispatched', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('started_at', sa.DateTime(timezone=True)), sa.Column('finished_at', sa.DateTime(timezone=True)),
        *timestamps())
    op.create_index('ix_domestic_studio_turns_conversation_id', names[0], ['conversation_id'])
    op.create_table(names[1], sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('conversation_id', sa.Uuid(), sa.ForeignKey('domestic_studio_conversations.id'), nullable=False),
        *file_fields(), sa.Column('status', sa.String(16), nullable=False, server_default='ready'),
        sa.CheckConstraint("status IN ('ready', 'uploading')"), *timestamps())
    op.create_index('ix_domestic_studio_uploads_conversation_id', names[1], ['conversation_id'])
    op.create_table(names[2], sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('turn_id', sa.Uuid(), sa.ForeignKey('domestic_studio_turns.id'), nullable=False),
        *file_fields(), sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False), sa.Column('source_path', sa.Text()), *timestamps())
    op.create_index('ix_domestic_studio_pictures_turn_id', names[2], ['turn_id'])
    op.create_table(names[3], sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('turn_id', sa.Uuid(), sa.ForeignKey('domestic_studio_turns.id'), nullable=False),
        sa.Column('item_id', sa.Text(), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False), sa.Column('state', sa.String(20), nullable=False), *timestamps())
    op.create_index('ix_domestic_studio_transcript_turn_id', names[3], ['turn_id'])


def downgrade():
    raise RuntimeError('Domestic Studio turns and files must be preserved.')
