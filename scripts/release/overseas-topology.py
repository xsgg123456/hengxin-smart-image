"""Prepare private production topology; never contact Docker or start services.

Returned metadata contains paths, never credentials. All generated files are
exclusive-create, mode 0600. A failed/previous preparation needs manual recovery.
"""
import json
import os
from pathlib import Path
import secrets

ORIGIN = 'https://zhitu.qhhengxin.top'
RUNTIME = '/opt/hengxin-overseas/backend'
WORKER_DESTINATION = Path('/etc/hengxin-overseas/worker.env')
AUTH_FILE = '/var/lib/hengxin-overseas/auth/auth.json'
ROOTS = {key: '/var/lib/hengxin-overseas/' + directory for key, directory in (
    ('CODEX_EXECUTION_ROOT', 'execution'), ('SKILL_INSTALL_ROOT', 'skills'),
    ('LOCAL_SKILL_ROOT', 'local-skills'))}
NETWORKS = ('hx-identity-domestic', 'hx-identity-overseas', 'hx-overseas-edge')


def _env(values, *, systemd=False):
    lines = []
    for key, value in sorted(values.items()):
        value = str(value)
        # Fail with a field name only, never echo secret input in diagnostics.
        if any(c in value for c in "\r\n\0'"):
            raise ValueError('Unsupported environment value: ' + key)
        if systemd:
            value = '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
        else:
            value = "'" + value + "'"  # Compose dotenv: no interpolation.
        lines.append(key + '=' + value)
    return '\n'.join(lines) + '\n'


def _external(*names):
    return {name: {'external': True, 'name': name} for name in names}


def prepare(work, source, image, domestic_env):
    """Generate staged envs/Compose overlays; caller installs worker env as root.

    source is the unpacked application root containing infra/ and backend/.
    domestic_env must include the four DINGTALK fields and CODEX_BINARY; only
    explicitly allowlisted provider/CLI settings are copied. Existing overseas
    configuration is refused (including the eventual systemd env destination).
    """
    work, source = Path(work), Path(source)
    if not work.is_dir() or not source.is_dir():
        raise ValueError('Release work/source directory is missing')
    for filename in ('compose.overseas.yaml', 'compose.identity.yaml'):
        if not (source / 'infra' / filename).is_file():
            raise ValueError('Release Compose source is missing: ' + filename)
    if not image or any(c.isspace() or c in '$\0' for c in image):
        raise ValueError('Invalid release image')
    required = ('DINGTALK_CORP_ID', 'DINGTALK_CLIENT_ID', 'DINGTALK_AGENT_ID',
                'DINGTALK_CLIENT_SECRET', 'CODEX_BINARY')
    for key in required:
        if not isinstance(domestic_env.get(key), str) or not domestic_env[key].strip():
            raise ValueError('Required deployment field is missing: ' + key)
    for key in ('CODEX_BINARY', 'CODEX_BWRAP_BINARY'):
        value = domestic_env.get(key, '/opt/hengxin-runtime/bwrap')
        if not value.startswith('/') or any(c in value for c in '$\r\n\0'):
            raise ValueError('Invalid native executable path: ' + key)

    names = ('identity.env', 'overseas.env', 'worker.env', 'overseas-overlay.json',
             'identity-overlay.json', 'domestic-overlay.private.json', 'web-overlay.json')
    paths = {name: work / name for name in names}
    if any(p.exists() or p.is_symlink() for p in (*paths.values(), WORKER_DESTINATION)):
        raise FileExistsError('Existing overseas release configuration; refusing credential regeneration')

    random = lambda: secrets.token_hex(32)
    domestic_key, overseas_key = random(), random()
    identity = {
        'IDENTITY_APP_IMAGE': image, 'IDENTITY_HTTP_PORT': '18012',
        'IDENTITY_REDIS_PASSWORD': random(), 'IDENTITY_PUBLIC_ORIGIN': ORIGIN,
        'IDENTITY_DOMESTIC_SERVICE_KEY': domestic_key,
        'IDENTITY_OVERSEAS_SERVICE_KEY': overseas_key,
        **{'IDENTITY_' + key: domestic_env[key] for key in required[:4]},
    }
    overseas = {
        'HX_BUSINESS_CONTEXT': 'overseas', 'OVERSEAS_APP_IMAGE': image,
        'OVERSEAS_APP_ENV': 'production', 'OVERSEAS_API_PORT': '18018',
        'OVERSEAS_POSTGRES_DB': 'hengxin_overseas',
        'OVERSEAS_MINIO_BUCKET': 'hengxin-overseas',
        'OVERSEAS_IDENTITY_SERVICE_URL': 'http://identity-api:8000',
        'OVERSEAS_IDENTITY_SERVICE_KEY': overseas_key,
        'OVERSEAS_IDENTITY_PUBLIC_ORIGIN': ORIGIN,
        **{'OVERSEAS_' + key: random() for key in (
            'POSTGRES_PASSWORD', 'OWNER_PASSWORD', 'APP_PASSWORD', 'REDIS_PASSWORD',
            'MINIO_ROOT_PASSWORD', 'MINIO_SECRET_KEY')},
        'OVERSEAS_MINIO_ROOT_USER': 'hxroot' + secrets.token_hex(10),
        'OVERSEAS_MINIO_ACCESS_KEY': 'hxapp' + secrets.token_hex(10),
    }
    worker = {
        'HX_BUSINESS_CONTEXT': 'overseas', 'OVERSEAS_APP_ENV': 'production',
        'OVERSEAS_IDENTITY_SERVICE_URL': 'http://127.0.0.1:18012',
        'OVERSEAS_IDENTITY_SERVICE_KEY': overseas_key,
        'OVERSEAS_IDENTITY_PUBLIC_ORIGIN': ORIGIN,
        'OVERSEAS_DATABASE_URL': 'postgresql+psycopg://overseas_app:' + overseas['OVERSEAS_APP_PASSWORD'] + '@127.0.0.1:15443/hengxin_overseas',
        'OVERSEAS_REDIS_URL': 'redis://:' + overseas['OVERSEAS_REDIS_PASSWORD'] + '@127.0.0.1:16398/0',
        'OVERSEAS_MINIO_ENDPOINT': '127.0.0.1:15910',
        **{key: overseas[key] for key in ('OVERSEAS_MINIO_ACCESS_KEY', 'OVERSEAS_MINIO_SECRET_KEY', 'OVERSEAS_MINIO_BUCKET')},
        **{'OVERSEAS_' + key: value for key, value in ROOTS.items()},
        'OVERSEAS_CODEX_AUTH_FILE': AUTH_FILE,
        'OVERSEAS_CODEX_BINARY': domestic_env['CODEX_BINARY'],
        'OVERSEAS_CODEX_BWRAP_BINARY': domestic_env.get('CODEX_BWRAP_BINARY', '/opt/hengxin-runtime/bwrap'),
        'OVERSEAS_CODEX_VERSION': domestic_env.get('CODEX_VERSION', '0.153.4'),
        'OVERSEAS_ENABLE_CODEX_EXECUTOR': 'true', 'OVERSEAS_GENERATION_CONCURRENCY': '5',
        'OVERSEAS_ENABLE_FIXTURE_EXECUTOR': 'false', 'OVERSEAS_ENABLE_TEST_JOBS': 'false',
        'OVERSEAS_ENABLE_DEV_IDENTITY': 'false', 'OVERSEAS_CLI_RETENTION_ENABLED': 'false',
        'OVERSEAS_MINIO_SECURE': 'false', 'OVERSEAS_WORKER_NODE_NAME': 'overseas-production',
        'OVERSEAS_DB_POOL_SIZE': '2', 'OVERSEAS_DB_MAX_OVERFLOW': '2',
    }
    overseas_overlay = {
        'services': {
            'overseas-postgres': {'mem_limit': '384m', 'ports': ['127.0.0.1:15443:5432']},
            'overseas-redis': {'mem_limit': '128m', 'ports': ['127.0.0.1:16398:6379']},
            'overseas-minio': {'mem_limit': '384m', 'ports': ['127.0.0.1:15910:9000']},
            'api': {'mem_limit': '384m', 'networks': {
                'overseas': {}, 'hx-identity-overseas': {},
                'hx-overseas-edge': {'aliases': ['overseas-api']}},
                'environment': {'OVERSEAS_DB_POOL_SIZE': '2', 'OVERSEAS_DB_MAX_OVERFLOW': '2'}},
        }, 'networks': _external('hx-identity-overseas', 'hx-overseas-edge'),
    }
    identity_overlay = {
        'services': {
            'identity-redis': {'mem_limit': '128m'},
            'identity-api': {'mem_limit': '256m', 'networks': {
                'identity': {}, **{name: {'aliases': ['identity-api']} for name in NETWORKS}}},
        }, 'networks': _external(*NETWORKS),
    }
    domestic_overlay = {
        'services': {'api': {'networks': {'default': {}, 'hx-identity-domestic': {}},
            'environment': {'IDENTITY_SERVICE_URL': 'http://identity-api:8000',
                'IDENTITY_SERVICE_KEY': domestic_key, 'IDENTITY_PUBLIC_ORIGIN': ORIGIN}}},
        'networks': _external('hx-identity-domestic'),
    }
    web_overlay = {'services': {'web': {'networks': {'default': {}, 'hx-overseas-edge': {}}}},
                   'networks': _external('hx-overseas-edge')}
    contents = {'identity.env': _env(identity), 'overseas.env': _env(overseas),
                'worker.env': _env(worker, systemd=True)}
    contents.update({name: json.dumps(value, indent=2) + '\n' for name, value in (
        ('overseas-overlay.json', overseas_overlay), ('identity-overlay.json', identity_overlay),
        ('domestic-overlay.private.json', domestic_overlay), ('web-overlay.json', web_overlay))})
    # Validate every value before creating any file. O_EXCL also prevents symlink
    # races from replacing pre-existing files between the preflight and writes.
    for name, content in contents.items():
        fd = os.open(paths[name], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    return {
        'identity_env': str(paths['identity.env']), 'overseas_env': str(paths['overseas.env']),
        'worker_env': str(paths['worker.env']), 'worker_env_destination': str(WORKER_DESTINATION),
        'overseas_overlay': str(paths['overseas-overlay.json']),
        'identity_overlay': str(paths['identity-overlay.json']),
        'domestic_overlay': str(paths['domestic-overlay.private.json']),
        'web_overlay': str(paths['web-overlay.json']),
        'overseas_compose': str(source / 'infra/compose.overseas.yaml'),
        'identity_compose': str(source / 'infra/compose.identity.yaml'),
        'runtime': RUNTIME, 'auth_file': AUTH_FILE, 'directories': list(ROOTS.values()),
        'loopback_ports': {'overseas_api': 18018, 'identity_api': 18012,
                           'overseas_postgres': 15443, 'overseas_redis': 16398,
                           'overseas_minio': 15910},
        'networks': [{'name': name, 'internal': name != 'hx-overseas-edge'} for name in NETWORKS],
    }
