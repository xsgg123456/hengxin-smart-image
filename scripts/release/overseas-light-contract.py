"""Read-only production API contract used by the overseas release."""

CONTRACT = r'''
import json
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.db.session import get_session, session_factory
from app.overseas.auth.dependencies import get_current_member
from app.overseas.auth.models import Member, MemberRole
from app.overseas.main import app
with session_factory()() as session:
    session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    actor = session.scalar(select(Member).join(MemberRole, MemberRole.user_id == Member.id).where(
        MemberRole.role == 'super_admin', Member.status == 'active', Member.directory_state == 'enrolled').limit(1))
    assert actor is not None
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_member] = lambda: actor
    client = TestClient(app)
    def get(path):
        response = client.get('/api/overseas/v1' + path)
        assert response.status_code == 200, (path, response.status_code)
        return response.json()
    persons = get('/management/people')['items']
    jobs = get('/management/jobs?pageSize=20')
    assignees = get('/task-assignees')['items']
    first = get('/tasks?pageSize=20')
    second = get('/tasks?pageSize=20&page=2')
    assert len(first['items']) <= 20 and len(second['items']) <= 20 and first['total'] == second['total']
    assert not {t['id'] for t in first['items']} & {t['id'] for t in second['items']}
    designing = get('/tasks?statusGroup=designing&pageSize=20')
    if assignees:
        selected = get('/tasks?designerId=' + assignees[0]['id'] + '&pageSize=20')
        assert all(t['designer'] and t['designer']['id'] == assignees[0]['id'] for t in selected['items'])
    operators = get('/archive-operators')['items']
    archives = get('/archives?pageSize=20')
    if operators:
        get('/archives?archiverId=' + operators[0]['id'] + '&pageSize=20')
    assert all(p['calls'] > 0 for p in persons)
    print(json.dumps({'people': len(persons), 'jobs': jobs['total'], 'tasks': first['total'],
        'designing': designing['total'], 'assignees': len(assignees), 'archives': archives['total'],
        'archivers': len(operators), 'readOnly': True}))
    client.close()
    app.dependency_overrides.clear()
'''
