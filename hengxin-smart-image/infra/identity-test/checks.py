"""Real HTTP assertions against three processes and two migrated databases."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
from redis import Redis
from sqlalchemy import create_engine, text

DIRECTORY = Path(__file__).resolve().parent
PYTHON = sys.executable
ID = 'http://127.0.0.1:8010'
ORIGIN = 'http://localhost:3013' if '--serve' in sys.argv else ID
PATH = '/api/identity/v1'
BUSINESS = {'domestic': ('http://127.0.0.1:8008', '/api/v1/auth'),
            'overseas': ('http://127.0.0.1:8009', '/api/overseas/v1/auth')}
HEADERS = {'X-HX-Request': '1'}
DB = {kind: 'postgresql+psycopg://postgres:p17-only@postgres/' + kind for kind in BUSINESS}
ENGINES = {kind: create_engine(url) for kind, url in DB.items()}
PROCESSES = {}
REDIS = Redis.from_url('redis://redis:6379/0', decode_responses=True)


def environment(kind):
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'PYTHONDONTWRITEBYTECODE')}
    env['PYTHONPATH'] = '/workspace/backend:' + str(DIRECTORY)
    env['HX_BUSINESS_CONTEXT'] = kind
    prefix = 'OVERSEAS_' if kind == 'overseas' else ''
    values = dict(APP_ENV='test', DATABASE_URL=DB[kind], REDIS_URL='redis://redis:6379/1',
                  MINIO_ENDPOINT='unused.invalid:9000', MINIO_ACCESS_KEY='disposable',
                  MINIO_SECRET_KEY='disposable', MINIO_BUCKET='disposable',
                  CODEX_EXECUTION_ROOT='/tmp/execution', SKILL_INSTALL_ROOT='/tmp/skills',
                  LOCAL_SKILL_ROOT='/tmp/local-skills', IDENTITY_SERVICE_URL=ID,
                  IDENTITY_PUBLIC_ORIGIN=ORIGIN, IDENTITY_SERVICE_KEY=KEYS[kind])
    env.update({prefix + k: v for k, v in values.items()})
    return env


KEYS = {kind: secrets.token_urlsafe(36) for kind in BUSINESS}


def seed():
    for kind, engine in ENGINES.items():
        with engine.begin() as connection:
            for member in ('both', kind):
                uid = str(uuid4())
                if kind == 'domestic':
                    connection.execute(text("INSERT INTO users (id,name,role,status,identity_source,created_at,updated_at) "
                        "VALUES (:id,:name,'operator','active','dingtalk',now(),now())"), {'id': uid, 'name': member})
                    connection.execute(text("INSERT INTO user_identities "
                        "(id,user_id,provider,corp_id,provider_user_id,union_id,department,created_at,updated_at) "
                        "VALUES (:id,:uid,'dingtalk','test-corp',:member,:member,'test',now(),now())"),
                        {'id': str(uuid4()), 'uid': uid, 'member': member})
                else:
                    connection.execute(text("INSERT INTO overseas_members "
                        "(id,corp_id,provider_user_id,name,department,status,created_at,updated_at) "
                        "VALUES (:id,'test-corp',:member,:member,'test','active',now(),now())"),
                        {'id': uid, 'member': member})
                    connection.execute(text("INSERT INTO overseas_member_roles (id,user_id,role,created_at,updated_at) "
                        "VALUES (:id,:uid,'operator',now(),now())"), {'id': str(uuid4()), 'uid': uid})


def start(kind, module, port, env):
    PROCESSES[kind] = subprocess.Popen([PYTHON, '-m', 'uvicorn', module, '--host', '0.0.0.0',
                                      '--port', str(port), '--no-access-log'], env=env)
    url = ID + PATH + '/config' if kind == 'identity' else ''.join(BUSINESS[kind]) + '/me'
    for _ in range(100):
        if PROCESSES[kind].poll() is not None:
            raise RuntimeError(kind + ' API exited')
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.TransportError:
            pass
        time.sleep(.1)
    raise RuntimeError(kind + ' API not ready')


def expect(response, status):
    assert response.status_code == status, (response.request.url.path, response.status_code, response.text)
    return response


@contextmanager
def login(member='both'):
    with httpx.Client(headers=HEADERS, timeout=10) as client:
        response = expect(client.post(ID + PATH + '/dingtalk/container', json={'code': member}), 200)
        cookie = response.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Path=/api/identity/v1' in cookie and 'SameSite=lax' in cookie
        yield client


def ticket(client, kind):
    return expect(client.post(ID + PATH + '/tickets', json={'business': kind}), 200).json()['ticket']


def exchange(client, kind, value=None, status=200):
    response = client.post(''.join(BUSINESS[kind]) + '/identity/session',
                           json={'ticket': value or ticket(client, kind)})
    return expect(response, status)


def me(client, kind, status=200):
    return expect(client.get(''.join(BUSINESS[kind]) + '/me'), status)


def check_matrix():
    for member in ('both', 'domestic', 'overseas', 'neither'):
        with login(member) as client:
            for kind in BUSINESS:
                allowed = member in ('both', kind)
                response = exchange(client, kind, status=200 if allowed else 403)
                if allowed:
                    me(client, kind)
                    expected = 'hx_session=' if kind == 'domestic' else 'hx_overseas_session='
                    assert expected in response.headers['set-cookie']
                    if kind == 'overseas':
                        assert 'Path=/api/overseas/v1' in response.headers['set-cookie']
        print('PASS authorization ' + member, flush=True)


def checks():
    check_matrix()
    with login() as client:
        value = ticket(client, 'domestic')
        exchange(client, 'overseas', value, 401)
        exchange(client, 'domestic', value)
        exchange(client, 'domestic', value, 401)
        exchange(client, 'domestic', value + 'tamper', 401)
        value = ticket(client, 'domestic')
        from hashlib import sha256
        key = 'hx:identity:ticket:domestic:' + sha256(value.encode()).hexdigest()
        assert 0 < REDIS.ttl(key) <= 60
        REDIS.pexpire(key, 1)
        time.sleep(.02)
        exchange(client, 'domestic', value, 401)
        exchange(client, 'overseas')
        for source, target in (('hx_session', 'overseas'), ('hx_overseas_session', 'domestic'),
                               ('hx_identity', 'overseas')):
            destination = 'hx_session' if target == 'domestic' else 'hx_overseas_session'
            for name in {source, destination}:
                with httpx.Client(headers={'Cookie': name + '=' + client.cookies.get(source)}) as isolated:
                    me(isolated, target, 401)
        print('PASS ticket binding replay tampering expiry and cookie isolation', flush=True)
        with ENGINES['overseas'].begin() as connection:
            connection.execute(text("UPDATE overseas_members SET status='disabled' WHERE provider_user_id='both'"))
        me(client, 'overseas', 403)
        me(client, 'domestic')
        with ENGINES['overseas'].begin() as connection:
            connection.execute(text("UPDATE overseas_members SET status='active' WHERE provider_user_id='both'"))
        expect(client.post(''.join(BUSINESS['overseas']) + '/logout'), 204)
        me(client, 'overseas', 401)
        me(client, 'domestic')
        exchange(client, 'overseas')
        expect(client.post(ID + PATH + '/logout'), 204)
        for kind in BUSINESS:
            me(client, kind, 401)
        print('PASS single-business disable/logout and global logout', flush=True)
    with httpx.Client() as client:
        response = expect(client.get(ID + PATH + '/dingtalk/authorize'), 303)
        state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
        callback = ID + PATH + '/dingtalk/callback?code=both&state=' + state
        expect(httpx.get(callback), 400)
        expect(client.get(callback), 303)
        expect(client.get(callback), 400)
        expect(client.post(ID + PATH + '/tickets', json={'business': 'domestic'}), 403)
    print('PASS OAuth browser binding replay and missing CSRF header', flush=True)
    with httpx.Client() as client:
        response = expect(client.get(ID + PATH + '/dingtalk/authorize'), 303)
        state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
        callback = ID + PATH + '/dingtalk/callback?code=invalid&state=' + state
        expect(client.get(callback), 303)
        expect(client.get(callback), 400)
    print('PASS failed OAuth exchange consumes state', flush=True)
    with login() as client:
        for kind in BUSINESS:
            exchange(client, kind)
            table = 'auth_sessions' if kind == 'domestic' else 'overseas_sessions'
            with ENGINES[kind].begin() as connection:
                connection.execute(text('UPDATE ' + table + " SET expires_at=now()-interval '1 second'"))
            me(client, kind, 401)
        for kind in BUSINESS:
            exchange(client, kind)
        from hashlib import sha256
        key = 'hx:identity:token:' + sha256(client.cookies.get('hx_identity').encode()).hexdigest()
        session_key = 'hx:identity:session:' + REDIS.get(key)
        record = json.loads(REDIS.get(session_key))
        record['expires_at'] = '2000-01-01T00:00:00+00:00'
        REDIS.set(session_key, json.dumps(record), ex=60)
        for kind in BUSINESS:
            me(client, kind, 401)
    print('PASS local business and upstream identity session expiry', flush=True)
    with login() as client:
        for kind in BUSINESS:
            exchange(client, kind)
        PROCESSES['identity'].terminate()
        PROCESSES['identity'].wait(timeout=10)
        for kind in BUSINESS:
            me(client, kind, 503)
    print('PASS identity outage fails closed for both businesses', flush=True)


def main():
    identity_env = {'PATH': os.environ['PATH'], 'PYTHONPATH': '/workspace/backend:' + str(DIRECTORY),
        'PYTHONDONTWRITEBYTECODE': '1', 'IDENTITY_REDIS_URL': 'redis://redis:6379/0',
        'IDENTITY_PUBLIC_ORIGIN': ORIGIN, 'IDENTITY_DOMESTIC_SERVICE_KEY': KEYS['domestic'],
        'IDENTITY_OVERSEAS_SERVICE_KEY': KEYS['overseas'], 'IDENTITY_DINGTALK_CORP_ID': 'test-corp',
        'IDENTITY_DINGTALK_CLIENT_ID': 'test-client', 'IDENTITY_DINGTALK_AGENT_ID': 'test-agent',
        'IDENTITY_DINGTALK_CLIENT_SECRET': 'disposable-not-a-real-secret'}
    try:
        for kind in BUSINESS:
            config = 'alembic.overseas.ini' if kind == 'overseas' else 'alembic.ini'
            migration = (
                'from alembic.config import Config; from alembic import command; '
                f'c=Config("/workspace/backend/{config}"); '
                'c.set_main_option("script_location", "/workspace/backend/migrations'
                + ('/overseas' if kind == 'overseas' else '') + '"); command.upgrade(c,"head")')
            subprocess.run([PYTHON, '-c', migration], env=environment(kind), check=True)
            with ENGINES[kind].connect() as connection:
                table = 'overseas_alembic_version' if kind == 'overseas' else 'alembic_version'
                version = connection.execute(text('SELECT version_num FROM ' + table)).scalar_one()
                assert version == ('overseas_0002' if kind == 'overseas' else '0027'), version
                other_table = 'users' if kind == 'overseas' else 'overseas_members'
                assert connection.execute(text('SELECT to_regclass(:name)'), {'name': other_table}).scalar() is None
                print('PASS migration ' + kind + ' ' + version, flush=True)
        seed()
        start('identity', 'provider_app:app', 8010, identity_env)
        start('domestic', 'app.main:app', 8008, environment('domestic'))
        start('overseas', 'app.overseas.main:app', 8009, environment('overseas'))
        checks()
        print('PASS ALL Phase 17 real HTTP integration', flush=True)
        if '--serve' in sys.argv:
            start('identity', 'provider_app:app', 8010, identity_env)
            def stop(signum, frame):
                raise SystemExit(0)
            signal.signal(signal.SIGTERM, stop)
            print('READY browser fixture codes: both domestic overseas neither', flush=True)
            while True:
                time.sleep(1)
    finally:
        for process in PROCESSES.values():
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        for engine in ENGINES.values():
            engine.dispose()
        REDIS.close()


if __name__ == '__main__':
    main()
