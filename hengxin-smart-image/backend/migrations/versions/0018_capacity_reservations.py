"""Persistent disk admission and immutable API collection identity."""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for name in ('created_at', 'updated_at')]


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('capacity_gate'):
        op.create_table('capacity_gate', sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            *(sa.Column(name, sa.BigInteger(), nullable=False, server_default='0') for name in
              ('floor_bytes', 'api_bytes', 'cli_bytes', 'free_bytes')),
            sa.Column('sample_at', sa.DateTime(timezone=True)),
            sa.Column('volumes', sa.JSON(), nullable=False, server_default='{}'),
            *timestamps(), sa.CheckConstraint('id = 1'))
        table = sa.Table('capacity_gate', sa.MetaData(), autoload_with=bind)
        bind.execute(table.insert().values(id=1))
    if not sa.inspect(bind).has_table('capacity_reservations'):
        op.create_table('capacity_reservations', sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('kind', sa.String(8), nullable=False), sa.Column('owner_id', sa.Uuid(), nullable=False),
            sa.Column('bytes', sa.BigInteger(), nullable=False),
            sa.Column('state', sa.String(16), nullable=False, server_default='held'),
            sa.Column('published_at', sa.DateTime(timezone=True)), *timestamps(),
            sa.CheckConstraint('bytes > 0'))
        op.create_index('ix_capacity_reservations_owner_id', 'capacity_reservations', ['owner_id'])
        op.create_index('ix_capacity_reservations_state', 'capacity_reservations', ['state'])
    columns = {c['name'] for c in sa.inspect(bind).get_columns('api_image_items')}
    if 'capacity_cycle_id' not in columns:
        op.add_column('api_image_items', sa.Column('capacity_cycle_id', sa.Uuid()))
    if 'staging_file_id' not in columns:
        op.add_column('api_image_items', sa.Column('staging_file_id', sa.Uuid(),
                      sa.ForeignKey('api_image_files.id', name='fk_api_item_staging_file')))


def downgrade():
    # Roll back application/config, not durable paid-result ownership/evidence.
    raise RuntimeError('Capacity and collection evidence must be retained; schema downgrade is disabled')
