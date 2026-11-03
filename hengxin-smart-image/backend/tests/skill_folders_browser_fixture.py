"""Disposable Linux browser fixture: real API + UDS publisher, no production resources."""
import os
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_overseas_configuration import FAKE_OVERSEAS

os.environ['HX_BUSINESS_CONTEXT'] = 'overseas'
for key, value in FAKE_OVERSEAS.items():
    os.environ['OVERSEAS_' + key] = value

from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core import browser_auth
from app.core.config import get_settings
from app.db.session import get_session
from app.db.timestamps import utcnow
from app.overseas.db import Base
from app.overseas.execution.models import ExecutionGate
from app.overseas.main import app
from app.overseas.management.skill_publisher import create_app
from app.overseas.management.skill_transfer_store import TransferStore
from test_overseas_auth import MEMBER, seed


def run():
    assert os.name == 'posix', 'This fixture needs a real Unix domain socket'
    with TemporaryDirectory(prefix='hx-skill-folder-browser-') as temporary:
        root = Path(temporary)
        settings = get_settings()
        settings.local_skill_root = str(root / 'skills')
        Path(settings.local_skill_root).mkdir()
        settings.identity_service_url = 'http://identity.test'
        settings.identity_service_key = 'isolated-browser-service-key-' * 3
        settings.identity_public_origin = 'http://127.0.0.1:3054'
        assertion = {'member': MEMBER, 'identity_session_id': 'folder-test',
                     'expires_at': (utcnow() + timedelta(hours=6)).isoformat()}
        browser_auth.redeem_ticket = lambda *args: assertion
        browser_auth.check_identity = lambda *args: True
        engine = create_engine('sqlite:///' + str(root / 'test.sqlite'),
                               connect_args={'check_same_thread': False, 'timeout': 30})
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory.begin() as session:
            session.add(ExecutionGate(id=1))
        settings.skill_toggle_owner_id = seed(factory, roles=('super_admin',))

        def session_dependency():
            with factory() as session:
                yield session

        app.dependency_overrides[get_session] = session_dependency
        sock = str(root / 'publisher.sock')
        os.environ['HX_SKILL_PUBLISH_SOCKET'] = sock
        publisher = create_app(TransferStore(root / 'uploads', root / 'skills'), factory)
        server = uvicorn.Server(uvicorn.Config(publisher, uds=sock, log_level='warning'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('Isolated publisher did not start')
            time.sleep(.05)

        @app.get('/api/identity/v1/me')
        def identity():
            return {'name': '文件夹隔离验收', 'sessionId': 'folder-test'}

        @app.post('/api/identity/v1/tickets')
        def ticket():
            return {'ticket': 'isolated-folder-ticket'}

        @app.get('/api/identity/v1/config')
        def config():
            return {'configured': True, 'corpId': 'corp', 'clientId': 'isolated'}

        @app.get('/fixture-login', response_class=HTMLResponse)
        def login():
            return '''<!doctype html><meta charset="utf-8"><title>隔离验收</title>
            <button onclick="login()">进入 Skill 管理</button><script>
            async function login(){const r=await fetch('/api/overseas/v1/auth/identity/session',{
            method:'POST',headers:{'Content-Type':'application/json','X-HX-Request':'1'},
            body:JSON.stringify({ticket:'isolated-folder-ticket'})});
            if(r.ok)location.href='/#/overseas/admin/skills';}
            </script>'''

        try:
            uvicorn.run(app, host='0.0.0.0', port=3053, log_level='warning')
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            engine.dispose()


if __name__ == '__main__':
    run()
