"""Durable domestic generation cycles and shared upstream protection."""
from alembic import op
import sqlalchemy as sa

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def columns():
    dt = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=True)
    uid = lambda name: sa.Column(name, sa.Uuid(), nullable=True)
    integer = lambda name, default: sa.Column(name, sa.Integer(), nullable=False, server_default=str(default))
    boolean = lambda name: sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())
    return {
        'api_image_tasks': [dt('last_send_at')],
        'api_image_items': [uid('retry_cycle_id'),
            sa.Column('retry_policy_version', sa.String(30), nullable=False, server_default='legacy-v1'),
            integer('attempts', 0), integer('max_attempts', 4),
            dt('retry_started_at'), dt('retry_deadline_at'), boolean('stop_requested'),
            sa.Column('retry_reason', sa.String(100), nullable=True)],
        'api_image_attempts': [uid('retry_cycle_id'),
            sa.Column('gate_generation', sa.Integer(), nullable=True), boolean('is_probe'),
            sa.Column('request_id', sa.String(128), nullable=True)],
        'api_image_channel': [dt('next_send_at'), dt('cooldown_until'),
            integer('failure_streak', 0), integer('generation', 0), uid('probe_attempt_id'),
            boolean('recovering'), integer('recovery_limit', 1)],
    }


def upgrade():
    bind = op.get_bind()
    for table, additions in columns().items():
        present = {column['name'] for column in sa.inspect(bind).get_columns(table)}
        for column in additions:
            if column.name not in present:
                op.add_column(table, column)
    # No terminal row is reopened. Unknown legacy cycle boundaries are counted
    # conservatively; an explicit manual retry is the only way to obtain v2.
    bind.execute(sa.text('UPDATE api_image_items SET attempts = LEAST(4, '
        '(SELECT COUNT(*) FROM api_image_attempts a WHERE a.item_id = api_image_items.id)) '
        "WHERE retry_policy_version = 'legacy-v1' AND retry_cycle_id IS NULL AND attempts < "
        '(SELECT COUNT(*) FROM api_image_attempts a WHERE a.item_id = api_image_items.id)'))


def downgrade():
    raise RuntimeError('0031 retry state cannot be discarded safely. Restore the verified backup '
                       'only after all new cycles and unknown calls have been resolved.')
