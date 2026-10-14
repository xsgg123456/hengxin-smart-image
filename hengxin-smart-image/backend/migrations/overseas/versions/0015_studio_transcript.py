"""Keep conversation history and full public CLI messages independently of images."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0015'
down_revision = 'overseas_0014'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(bind)
    channels = 'overseas_studio_conversations'
    if offline:
        op.drop_constraint(channels + '_task_id_key', channels, type_='unique')
    else:
        for constraint in inspector.get_unique_constraints(channels):
            if constraint['column_names'] == ['task_id']:
                op.drop_constraint(constraint['name'], channels, type_='unique')
    index = 'ix_overseas_studio_conversations_task_id'
    if offline or index not in {i['name'] for i in inspector.get_indexes(channels)}:
        op.create_index(index, channels, ['task_id'])
    changes = {
        'overseas_studio_turns': [sa.Column('delivery_error', sa.Text),
            sa.Column('event_offset', sa.Integer, nullable=False, server_default='0'),
            sa.Column('event_session_id', sa.String(128)),
            sa.Column('event_invalid', sa.Boolean, nullable=False, server_default=sa.false())],
        'overseas_studio_pictures': [sa.Column('source_path', sa.Text)],
    }
    for table, columns in changes.items():
        existing = set() if offline else {c['name'] for c in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    metadata = sa.MetaData()
    for name in ('overseas_tasks', 'overseas_studio_turns'):
        sa.Table(name, metadata, sa.Column('id', sa.Uuid, primary_key=True))
    sa.Table('overseas_studio_transcript', metadata,
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        sa.Column('turn_id', sa.ForeignKey('overseas_studio_turns.id'), nullable=False, index=True),
        sa.Column('item_id', sa.Text, nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('text', sa.Text, nullable=False), sa.Column('state', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    metadata.tables['overseas_studio_transcript'].create(bind, checkfirst=not offline)
    op.execute(sa.text("""INSERT INTO overseas_studio_transcript
        (task_id, turn_id, item_id, kind, text, state, created_at, updated_at)
        SELECT t.task_id, t.id, 'legacy-reply', 'message', t.reply, 'completed', t.created_at, t.updated_at
        FROM overseas_studio_turns t WHERE t.reply IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM overseas_studio_transcript e WHERE e.turn_id=t.id)
        ORDER BY t.created_at, t.id"""))


def downgrade():
    raise RuntimeError('Public transcript history migration is forward-only')
