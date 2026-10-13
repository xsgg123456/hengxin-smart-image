from uuid import uuid4

import pytest
from sqlalchemy import select

from app.overseas.auth.models import BusinessSession, Member, MemberRole, ROLES
from app.overseas.members.models import MemberAudit
from test_overseas_auth import overseas, seed, login, HEADERS, COOKIE_PATH

URL = COOKIE_PATH + '/members'


def add_member(factory, status='pending', roles=(), name='待授权成员', department='海外设计'):
    with factory.begin() as session:
        member = Member(corp_id='corp', provider_user_id=str(uuid4()), name=name,
                        department=department, status=status)
        session.add(member)
        session.flush()
        session.add_all(MemberRole(user_id=member.id, role=role) for role in roles)
        return member.id


def payload(version=1, roles=None, status='active'):
    return {'roles': roles if roles is not None else ['designer'],
            'status': status, 'version': version}


def test_admin_search_detail_activation_and_audit(overseas):
    client, factory, _ = overseas
    admin_id = seed(factory, roles=('super_admin',))
    target = add_member(factory)
    other = add_member(factory, name='同名', department='国内')
    login(client)
    response = client.get(URL, params={'search': '海外设计', 'status': 'pending', 'pageSize': 1})
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['id'] == str(target)
    assert client.get(URL + '/' + str(other)).json()['department'] == '国内'
    result = client.patch(URL + '/' + str(target), headers=HEADERS,
                          json=payload(roles=['designer']))
    assert result.status_code == 200
    assert result.json()['roles'] == ['designer']
    assert result.json()['version'] == 2
    audit = client.get(URL + '/' + str(target) + '/audit').json()['items']
    assert len(audit) == 1 and audit[0]['actorId'] == str(admin_id)
    assert audit[0]['before'] == {'status': 'pending', 'roles': [], 'version': 1}
    assert audit[0]['after'] == {'status': 'active', 'roles': ['designer'], 'version': 2}
    assert client.get(URL, params={'role': 'designer'}).json()['total'] == 1
    assert client.get(URL, params={'search': '%'}).json()['total'] == 0
    assert client.get(URL + '/' + str(uuid4())).status_code == 404
    assert client.patch(URL + '/' + str(uuid4()), headers=HEADERS, json=payload()).status_code == 404


@pytest.mark.parametrize('roles', [(r,) for r in ROLES if r != 'super_admin'] + [()])
def test_ordinary_or_roleless_cannot_manage(overseas, roles):
    client, factory, _ = overseas
    member_id = seed(factory, roles=roles)
    login(client)
    for path in (URL, URL + '/' + str(member_id), URL + '/' + str(member_id) + '/audit'):
        assert client.get(path).status_code in (401, 403)
    assert client.patch(URL + '/' + str(member_id), headers=HEADERS,
                        json=payload(roles=['super_admin'])).status_code in (401, 403)


@pytest.mark.parametrize('body', [payload(roles=[]), payload(roles=['unknown']), payload(roles=['operator', 'designer']), payload(roles=['designer', 'designer']),
    payload(version=0), payload(version=True), payload(version='1'),
    payload(status='pending'), {**payload(), 'name': '伪造姓名'}])
def test_strict_input(overseas, body):
    client, factory, _ = overseas
    member_id = seed(factory, roles=('super_admin',))
    login(client)
    assert client.patch(URL + '/' + str(member_id), headers=HEADERS, json=body).status_code == 422


def test_last_admin_version_csrf_and_revocation(overseas):
    client, factory, _ = overseas
    member_id = seed(factory, roles=('super_admin',))
    login(client)
    assert client.patch(URL + '/' + str(member_id), headers=HEADERS, json=payload()).status_code == 409
    target = add_member(factory, status='active', roles=('designer',))
    assert client.patch(URL + '/' + str(target), json=payload()).status_code == 403
    assert client.patch(URL + '/' + str(target), headers={**HEADERS, 'Origin': 'https://evil.test'},
                        json=payload()).status_code == 403
    with factory.begin() as session:
        from app.overseas.auth.sessions import issue_session
        from app.db.timestamps import utcnow
        from datetime import timedelta
        tokens = [issue_session(session, target, f'identity-{index}', utcnow() + timedelta(hours=1))
                  for index in range(2)]
    assert client.patch(URL + '/' + str(target), headers=HEADERS,
                        json=payload(status='disabled', roles=[])).status_code == 200
    assert client.patch(URL + '/' + str(target), headers=HEADERS, json=payload()).status_code == 409
    with factory() as session:
        from app.overseas.auth.sessions import resolve_session
        assert all(resolve_session(session, token) is None for token in tokens)
        assert all(s.revoked_at for s in session.scalars(select(BusinessSession).where(
            BusinessSession.user_id == target)))
        assert len(list(session.scalars(select(MemberAudit)))) == 1


def test_roles_change_invalidates_old_admin_session_without_relogin(overseas):
    client, factory, _ = overseas
    member_id = seed(factory, roles=('super_admin',))
    add_member(factory, status='active', roles=('super_admin',))
    login(client)
    assert client.patch(URL + '/' + str(member_id), headers=HEADERS, json=payload()).status_code == 200
    assert client.get(URL).status_code == 403
    assert client.get(COOKIE_PATH + '/auth/me').json()['roles'] == ['designer']


def test_audit_failure_rolls_back_roles_status_and_version(overseas, monkeypatch):
    from sqlalchemy import event
    client, factory, _ = overseas
    seed(factory, roles=('super_admin',))
    target = add_member(factory)
    login(client)

    def fail(*args):
        raise RuntimeError('audit unavailable')

    event.listen(MemberAudit, 'before_insert', fail)
    try:
        with pytest.raises(RuntimeError, match='audit unavailable'):
            client.patch(URL + '/' + str(target), headers=HEADERS, json=payload())
    finally:
        event.remove(MemberAudit, 'before_insert', fail)
    with factory() as session:
        assert session.get(Member, target).status == 'pending'
        assert session.get(Member, target).version == 1
        assert session.scalar(select(MemberRole).where(MemberRole.user_id == target)) is None


@pytest.mark.parametrize('query', [{'page': 0}, {'pageSize': 101}, {'status': 'unknown'},
                                  {'role': 'admin'}, {'search': 'x' * 101}])
def test_query_validation(overseas, query):
    client, factory, _ = overseas
    seed(factory, roles=('super_admin',))
    login(client)
    assert client.get(URL, params=query).status_code == 422


def test_pagination_and_latest_100_audits(overseas):
    from datetime import timedelta
    from app.db.timestamps import utcnow
    client, factory, _ = overseas
    actor_id = seed(factory, roles=('super_admin',))
    target = add_member(factory)
    for _ in range(3):
        add_member(factory)
    login(client)
    first = client.get(URL, params={'pageSize': 2}).json()
    second = client.get(URL, params={'pageSize': 2, 'page': 2}).json()
    assert first['total'] == second['total'] == 5
    assert len(first['items']) == len(second['items']) == 2
    assert not ({m['id'] for m in first['items']} & {m['id'] for m in second['items']})
    with factory.begin() as session:
        for i in range(101):
            session.add(MemberAudit(member_id=target, actor_id=actor_id, action='update',
                before={'roles': [], 'status': 'pending', 'version': i},
                after={'roles': ['designer'], 'status': 'active', 'version': i + 1},
                created_at=utcnow() + timedelta(seconds=i)))
    entries = client.get(URL + '/' + str(target) + '/audit').json()['items']
    assert len(entries) == 100
    assert entries[0]['after']['version'] == 101
    assert entries[-1]['after']['version'] == 2
