"""Independent API worker heartbeat."""
from alembic import op
from app.modules.api_image_edits.heartbeat_models import ApiWorkerHeartbeat

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade():
    ApiWorkerHeartbeat.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
