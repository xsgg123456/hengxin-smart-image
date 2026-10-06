"""Independent single-image CLI conversations and replayable events."""
from alembic import op
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn, ConversationEvent

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    for model in (Conversation, ConversationTurn, ConversationEvent):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Preserve session identities and immutable history on rollback.
