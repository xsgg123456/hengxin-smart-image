from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.membership.models import ApplicationFields, EventFields
from app.overseas.db import Base


class MembershipApplication(ApplicationFields, Base):
    __tablename__ = 'overseas_membership_applications'
    __table_args__ = (
        UniqueConstraint('corp_id', 'provider_user_id', name='uq_overseas_application_identity'),
        CheckConstraint("status IN ('pending','approved','rejected','withdrawn')"),
    )


class ApplicationEvent(EventFields, Base):
    __tablename__ = 'overseas_membership_application_events'
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey('overseas_membership_applications.id'), index=True)
