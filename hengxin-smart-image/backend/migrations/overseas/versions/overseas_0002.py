"""Independent overseas members, explicit roles and opaque business sessions."""
from alembic import op
from app.overseas.auth.models import BusinessSession, Member, MemberRole

revision = 'overseas_0002'
down_revision = 'overseas_0001'
branch_labels = None
depends_on = None


def upgrade():
    for model in (Member, MemberRole, BusinessSession):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass
