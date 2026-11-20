"""Add overseas feedback and individually assigned management access."""
from alembic import op

revision = 'overseas_0027'
down_revision = 'overseas_0026'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS overseas_feedback_grants (
        id UUID PRIMARY KEY REFERENCES overseas_members(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS overseas_feedback (
        id UUID PRIMARY KEY, submitter_id UUID NOT NULL REFERENCES overseas_members(id),
        submitter_name VARCHAR(200) NOT NULL, question TEXT NOT NULL, source VARCHAR(500) NOT NULL,
        task_name VARCHAR(200), sku VARCHAR(8099), screenshot_type VARCHAR(20), screenshot BYTEA,
        status VARCHAR(16) NOT NULL CHECK (status IN ('pending','processing','resolved')),
        public_reply TEXT NOT NULL, internal_note TEXT NOT NULL, version INTEGER NOT NULL CHECK (version >= 1),
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        CHECK (status != 'resolved' OR length(trim(public_reply)) > 0)
    )''')
    op.execute('''CREATE INDEX IF NOT EXISTS ix_overseas_feedback_owner_date
        ON overseas_feedback(submitter_id, created_at)''')
    op.execute('''CREATE INDEX IF NOT EXISTS ix_overseas_feedback_status_date
        ON overseas_feedback(status, created_at)''')


def downgrade():
    op.drop_table('overseas_feedback')
    op.drop_table('overseas_feedback_grants')
