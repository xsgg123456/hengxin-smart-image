"""Personal drafts, attachment membership and durable leased imports (additive)."""
from alembic import op

revision = 'overseas_0026'
down_revision = 'overseas_0025'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS overseas_requirement_drafts (
        id UUID PRIMARY KEY, owner_id UUID NOT NULL UNIQUE REFERENCES overseas_members(id),
        epoch UUID NOT NULL UNIQUE, version INTEGER NOT NULL CHECK (version >= 1),
        fields JSON NOT NULL, source JSON, submit_key VARCHAR(128) NOT NULL,
        last_submitted_task_id UUID, last_submitted_key VARCHAR(128),
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS overseas_draft_materials (
        id UUID PRIMARY KEY, draft_id UUID NOT NULL REFERENCES overseas_requirement_drafts(id),
        epoch UUID NOT NULL, material_id UUID NOT NULL UNIQUE REFERENCES overseas_materials(id),
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE (draft_id, material_id)
    )''')
    op.execute('''CREATE INDEX IF NOT EXISTS ix_overseas_draft_materials_epoch
                  ON overseas_draft_materials(epoch)''')
    op.execute('''CREATE TABLE IF NOT EXISTS overseas_draft_imports (
        id UUID PRIMARY KEY, draft_id UUID NOT NULL REFERENCES overseas_requirement_drafts(id),
        epoch UUID NOT NULL, owner_id UUID NOT NULL REFERENCES overseas_members(id),
        sku VARCHAR(80) NOT NULL, requirement_id VARCHAR(200) NOT NULL,
        source_file_id VARCHAR(200) NOT NULL, filename VARCHAR(255) NOT NULL,
        size INTEGER NOT NULL CHECK (size > 0 AND size <= 500000000),
        kind VARCHAR(20) NOT NULL CHECK (kind IN ('requirement','competitor')),
        state VARCHAR(20) NOT NULL CHECK (state IN ('queued','running','ready','failed','cancelled')),
        progress INTEGER NOT NULL CHECK (progress >= 0 AND progress <= 100), error VARCHAR(300),
        material_id UUID REFERENCES overseas_materials(id) ON DELETE SET NULL, lease_token UUID, lease_until TIMESTAMPTZ,
        available_at TIMESTAMPTZ NOT NULL, attempts INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE (draft_id, epoch, source_file_id)
    )''')
    for field in ('draft_id', 'state', 'lease_until'):
        op.execute(f'CREATE INDEX IF NOT EXISTS ix_overseas_draft_imports_{field} '
                   f'ON overseas_draft_imports({field})')


def downgrade():
    op.drop_table('overseas_draft_imports')
    op.drop_table('overseas_draft_materials')
    op.drop_table('overseas_requirement_drafts')
