import pytest
from sqlalchemy import delete, select

from app.overseas.auth.models import Member, MemberRole
from app.overseas.members.bootstrap import bootstrap_admins
from app.overseas.members.models import MemberAudit
from app.overseas.members import membership
from app.membership.service import submit
from test_overseas_auth import overseas, seed, MEMBER
from test_overseas_members import add_member


def test_explicit_bootstrap_verified_identity_and_idempotency(overseas):
    _, factory, _ = overseas
    with factory() as session:
        submit(session, membership, MEMBER)
    with factory() as session:
        assert bootstrap_admins(session, ' corp ', ' member-1, member-1, ') == 1
    with factory() as session:
        assert bootstrap_admins(session, 'corp', 'member-1') == 0
        assert session.scalar(select(Member)).version == 2
        assert len(list(session.scalars(select(MemberAudit)))) == 1
        assert session.scalar(select(MemberRole.role)) == 'super_admin'


@pytest.mark.parametrize('corp,users', [('', ''), ('corp', ' , '), ('corp', 'missing'),
                                     ('different-corp', 'member-1'), ('corp', 'member-1,missing')])
def test_bootstrap_rejects_empty_or_unverified_and_cross_corp(overseas, corp, users):
    _, factory, _ = overseas
    seed(factory, status='pending', roles=())
    with factory() as session, pytest.raises(ValueError):
        bootstrap_admins(session, corp, users)
    with factory() as session:
        assert session.scalar(select(MemberRole)) is None


def test_same_name_cannot_match_and_existing_admin_refuses(overseas):
    _, factory, _ = overseas
    seed(factory, status='pending', roles=())
    add_member(factory, status='active', roles=('super_admin',), name=MEMBER['name'])
    with factory() as session, pytest.raises(ValueError, match='已有有效'):
        bootstrap_admins(session, 'corp', 'member-1')


def test_bootstrap_never_restores_demoted_admin(overseas):
    _, factory, _ = overseas
    with factory() as session:
        submit(session, membership, MEMBER)
    with factory() as session:
        bootstrap_admins(session, 'corp', 'member-1')
    with factory.begin() as session:
        session.execute(delete(MemberRole).where(MemberRole.user_id == session.scalar(select(Member.id))))
    with factory() as session, pytest.raises(ValueError, match='禁止重新提权'):
        bootstrap_admins(session, 'corp', 'member-1')
