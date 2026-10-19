"""Persist authenticated archive confirmations independently from source tasks."""
from uuid import UUID, uuid5
from alembic import op
import sqlalchemy as sa

revision = 'overseas_0018'
down_revision = 'overseas_0017'
branch_labels = depends_on = None


def upgrade():
    metadata = sa.MetaData()
    sa.Table('overseas_archives', metadata, sa.Column('id', sa.Uuid, primary_key=True))
    events = sa.Table('overseas_archive_events', metadata,
        sa.Column('id', sa.Uuid, primary_key=True),
        sa.Column('archive_id', sa.ForeignKey('overseas_archives.id'), nullable=False, index=True),
        sa.Column('actor_id', sa.Uuid, nullable=False),
        sa.Column('actor_name', sa.String(200), nullable=False),
        sa.Column('pictures', sa.JSON, nullable=False),
        sa.Column('prior_history_unknown', sa.Boolean, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    events.create(op.get_bind(), checkfirst=not op.get_context().as_sql)
    if not op.get_context().as_sql:
        backfill(op.get_bind(), events)


def backfill(connection, events):
    # Only legacy whole-set confirmations carry verifiable actor/name/time evidence.
    # Studio request hashes cannot reconstruct selected pictures; leave those unknown.
    metadata = sa.MetaData()
    archives, changes, assets = [sa.Table(name, metadata, autoload_with=connection) for name in
        ('overseas_archives', 'overseas_task_events', 'overseas_archive_assets')]
    for archive in connection.execute(sa.select(archives)).mappings():
        if (not archive['task_id'] or not archive['versions']
                or any(v.startswith('studio:') for v in archive['versions'])
                or connection.scalar(sa.select(events.c.id).where(events.c.archive_id == UUID(str(archive['id']))))):
            continue
        evidence = connection.execute(sa.select(changes).where(
            changes.c.task_id == archive['task_id'], changes.c.kind == 'task.archived')).mappings().all()
        pictures = connection.execute(sa.select(assets).where(assets.c.archive_id == archive['id'])
            .order_by(assets.c.position, assets.c.id)).mappings().all()
        if (len(evidence) != 1 or not evidence[0]['actor_name']
                or {p['source_version'] for p in pictures} != set(archive['versions'])
                or len(pictures) != len(archive['versions'])):
            continue
        event = evidence[0]
        connection.execute(events.insert().values(id=uuid5(UUID(str(archive['id'])), 'legacy-confirmation'),
            archive_id=UUID(str(archive['id'])), actor_id=UUID(str(event['actor_id'])), actor_name=event['actor_name'],
            pictures=[dict(id=str(UUID(str(p['id']))), name=p['name'], sku=p['sku']) for p in pictures],
            prior_history_unknown=False, created_at=event['created_at'], updated_at=event['created_at']))


def downgrade():
    raise RuntimeError('Archive audit migration is forward-only')
