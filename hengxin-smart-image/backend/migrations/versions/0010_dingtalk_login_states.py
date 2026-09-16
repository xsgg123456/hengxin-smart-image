"""Store one-time browser login state for DingTalk OAuth."""
from alembic import op

from app.modules.auth.models import AuthLoginStateRecord


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    AuthLoginStateRecord.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    AuthLoginStateRecord.__table__.drop(op.get_bind(), checkfirst=True)
