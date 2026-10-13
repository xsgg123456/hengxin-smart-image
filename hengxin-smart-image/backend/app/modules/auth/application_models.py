from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.membership.models import ApplicationFields, EventFields
from app.models import Base


class MembershipApplication(ApplicationFields, Base):
    __tablename__ = 'domestic_membership_applications'
    __table_args__ = (
        UniqueConstraint('corp_id', 'provider_user_id', name='uq_domestic_application_identity'),
        CheckConstraint("status IN ('pending','approved','rejected','withdrawn')"),
    )


class ApplicationEvent(EventFields, Base):
    __tablename__ = 'domestic_membership_application_events'
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey('domestic_membership_applications.id'), index=True)


class MemberAudit(EventFields, Base):
    __tablename__ = 'domestic_member_audits'
    member_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
