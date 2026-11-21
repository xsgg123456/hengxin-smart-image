"""Loopback-only QA identity provider and ephemeral overseas database. Real overseas business app."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
build = Path(sys.argv[1]).resolve(strict=True)
if json.loads((build / 'release-scope.json').read_text(encoding='utf8'))['scope'] != 'overseas':
    raise ValueError('Expected an overseas release frontend build')
backend = Path(__file__).resolve().parents[2] / 'backend'
sys.path[:0] = [str(backend), str(backend/'tests')]
import pytest, uvicorn
from fastapi import Request, HTTPException
from sqlalchemy import create_engine
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles
from app.core import browser_auth
from app.storage.minio_store import get_store
import test_overseas_auth as auth
from test_overseas_materials import MemoryStore

origin = 'http://127.0.0.1:4231'
with TemporaryDirectory(prefix='hx-creative-browser-') as tmp, pytest.MonkeyPatch.context() as patch:
    patch.setattr(auth, 'create_engine', lambda *a, **kw: create_engine('sqlite:///' + str(Path(tmp)/'tasks.db')))
    fixture = auth.overseas.__wrapped__(patch, Path(tmp))
    client, db, _ = next(fixture)
    app = client.app
    auth.Base.metadata.create_all(db.kw['bind'])
    ids = {}
    for role in ('designer','non_designer','super_admin'):
        user = dict(auth.MEMBER, provider_user_id=role, union_id=role, name='验收' + role)
        patch.setattr(auth,'MEMBER',user)
        auth.seed(db,roles=(role,))
        ids[role] = dict(member=user, identity_session_id='qa-' + role,expires_at=(auth.utcnow()+timedelta(days=1)).isoformat())
    auth.get_settings().identity_public_origin = origin
    patch.setattr(browser_auth,'redeem_ticket',lambda url,key,ticket,purpose: ids[ticket])
    store = MemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    def role_of(req):
        role = req.cookies.get('local-qa-identity','designer')
        if role not in ids: raise HTTPException(401)
        return role
    def current(req: Request):
        identity = ids[role_of(req)]
        return {'sessionId':identity['identity_session_id'],'name':identity['member']['name']}
    def ticket(req: Request):
        return {'ticket':role_of(req)}
    app.add_api_route('/api/identity/v1/config',lambda:{'configured':True,'corpId':'local','clientId':'local'})
    app.add_api_route('/api/identity/v1/me',current)
    app.add_api_route('/api/identity/v1/tickets',ticket,methods=['POST'])
    app.add_api_route('/api/v1/auth/identity/access',lambda:{'state':'unregistered'},methods=['POST'])
    app.mount('/overseas',StaticFiles(directory=build,html=True))
    try:
        uvicorn.run(TrustedHostMiddleware(app,allowed_hosts=['127.0.0.1']),host='127.0.0.1',port=4231,lifespan='off',access_log=False)
    finally:
        fixture.close()
