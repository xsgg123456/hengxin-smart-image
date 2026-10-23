"""Named independent Studio sessions; retain all historical identities and bytes."""
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0021'
down_revision = 'overseas_0020'
branch_labels = depends_on = None


def add(table, column):
    if op.get_context().as_sql or column.name not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
        op.add_column(table, column)
        return True
    return False


def upgrade():
    if add('overseas_studio_conversations', sa.Column('name', sa.String(30), nullable=False, server_default='新会话')):
        op.execute("""UPDATE overseas_studio_conversations AS c SET name = '会话 ' || ordered.position
            FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY created_at, id) AS position
                  FROM overseas_studio_conversations) AS ordered WHERE c.id = ordered.id""")
    add('overseas_studio_conversations', sa.Column('version', sa.Integer, nullable=False, server_default='1'))
    add('overseas_studio_uploads', sa.Column('conversation_id', sa.Uuid,
        sa.ForeignKey('overseas_studio_conversations.id'), nullable=True))
    add('overseas_task_requests', sa.Column('conversation_id', sa.Uuid, nullable=True))
    add('overseas_archive_assets', sa.Column('source_conversation_id', sa.Uuid, nullable=True))
    add('overseas_archive_assets', sa.Column('source_conversation_name', sa.String(30), nullable=True))
    add('overseas_studio_pictures', sa.Column('origin_turn_id', sa.Uuid, nullable=True))
    op.alter_column('overseas_studio_pictures', 'turn_id', existing_type=sa.Uuid, nullable=True)
    add('overseas_studio_material_visibility', sa.Column('scope', sa.String(36), nullable=False, server_default=''))
    # Older uploads remain task-wide, including attachments referenced in multiple
    # historical sessions. Guessing ownership here would break saved conversations.
    op.execute("""UPDATE overseas_archive_assets AS a
        SET source_conversation_id = c.id, source_conversation_name = c.name
        FROM overseas_studio_pictures AS p
        JOIN overseas_studio_turns AS t ON t.id = p.turn_id
        JOIN overseas_studio_conversations AS c ON c.id = t.conversation_id
        WHERE a.source_version = 'studio:' || CAST(p.id AS TEXT)
          AND a.source_conversation_id IS NULL""")
    metadata = sa.MetaData()
    sa.Table('overseas_tasks', metadata, sa.Column('id', sa.Uuid, primary_key=True))
    table = sa.Table('overseas_studio_conversation_deletions', metadata,
        sa.Column('conversation_id', sa.Uuid, primary_key=True),
        sa.Column('task_id', sa.ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        sa.Column('actor_id', sa.Uuid, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('error', sa.String(200)), sa.Column('manifest', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    table.create(op.get_bind(), checkfirst=not op.get_context().as_sql)
    if op.get_context().as_sql:
        op.drop_constraint('overseas_studio_material_visibility_task_id_checksum_key',
                           'overseas_studio_material_visibility', type_='unique')
        op.create_unique_constraint('uq_studio_material_scope', 'overseas_studio_material_visibility',
                                    ['task_id', 'checksum', 'scope'])
        op.create_index('ix_overseas_studio_uploads_conversation_id', 'overseas_studio_uploads', ['conversation_id'])
    else:
        inspector = sa.inspect(op.get_bind())
        constraints = inspector.get_unique_constraints('overseas_studio_material_visibility')
        for constraint in constraints:
            if constraint['column_names'] == ['task_id', 'checksum']:
                op.drop_constraint(constraint['name'], 'overseas_studio_material_visibility', type_='unique')
        if not any(c['column_names'] == ['task_id', 'checksum', 'scope'] for c in constraints):
            op.create_unique_constraint('uq_studio_material_scope', 'overseas_studio_material_visibility',
                                        ['task_id', 'checksum', 'scope'])
        if not any(i['column_names'] == ['conversation_id'] for i in inspector.get_indexes('overseas_studio_uploads')):
            op.create_index('ix_overseas_studio_uploads_conversation_id', 'overseas_studio_uploads', ['conversation_id'])


def downgrade():
    raise RuntimeError('Studio sessions migration is forward-only')
