"""Three-day retention and independent durable cleanup observations."""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    def dt(name, nullable=True, index=False):
        return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, index=index)
    def uid(name, nullable=False, index=False, primary_key=False):
        return sa.Column(name, sa.Uuid(), nullable=nullable, index=index, primary_key=primary_key)
    def number(name):
        return sa.Column(name, sa.Integer(), nullable=False)
    def table(name, *columns):
        return sa.Table(name, metadata, *columns, dt('created_at', False), dt('updated_at', False))
    table('cli_retention_records', uid('id', primary_key=True), uid('resource_id', index=True),
        uid('task_id', True), sa.Column('task_name', sa.String(60), nullable=False),
        number('image_position'), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('result', sa.String(30), nullable=False, index=True), dt('last_activity_at', False),
        dt('due_at', False, True), dt('processed_at', index=True), dt('completed_at', index=True),
        dt('next_attempt_at'), number('turns_removed'), number('objects_removed'), number('objects_pending'),
        sa.Column('counted', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('resource_id', 'kind', 'last_activity_at'))
    table('cli_retention_object_links', uid('id', primary_key=True), uid('record_id', index=True),
        uid('object_id', index=True), sa.UniqueConstraint('record_id', 'object_id'))
    table('cli_retention_runs', uid('id', primary_key=True), dt('started_at', False, True),
        dt('finished_at'), sa.Column('status', sa.String(20), nullable=False))
    table('cli_retention_service', sa.Column('id', sa.String(20), primary_key=True),
        dt('heartbeat_at', False), dt('next_scan_at'))
    totals = table('cli_retention_totals', sa.Column('id', sa.String(20), primary_key=True),
        dt('since', False), number('cache_total'), number('history_total'))
    metadata.create_all(bind, checkfirst=True)
    if bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    now = datetime.now(timezone.utc)
    bind.execute(insert(totals).values(id='api_cli', since=now, cache_total=0,
        history_total=0, created_at=now, updated_at=now).on_conflict_do_nothing(index_elements=['id']))
    # Preserve effective activity and every pending retry fence; no installation grace.
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text("UPDATE cli_retention SET next_cleanup_at = last_activity_at + "
            "CASE WHEN cache_cleared_at IS NULL THEN INTERVAL '24 hours' ELSE INTERVAL '72 hours' END "
            "WHERE domain = 'api_cli' AND status = 'active'"))
    else:
        bind.execute(sa.text("UPDATE cli_retention SET next_cleanup_at = "
            "strftime('%Y-%m-%d %H:%M:%f', last_activity_at, CASE WHEN cache_cleared_at IS NULL "
            "THEN '+24 hours' ELSE '+72 hours' END) WHERE domain = 'api_cli' AND status = 'active'"))


def downgrade():
    raise RuntimeError('Pause retention instead of discarding durable cleanup receipts.')
