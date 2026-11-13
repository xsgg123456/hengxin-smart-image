"""Build, but never install, the domestic Studio service configuration.

This is a pure candidate transformer. A separate reviewed joint transaction
must provision paths, migrate the domestic database, switch and record it.
"""
import copy
from pathlib import PurePosixPath
import re
from urllib.parse import unquote, urlsplit


SKILLS = '/var/lib/hengxin-domestic/local-skills'
TRANSFERS = '/var/lib/hengxin-domestic/skill-transfers'
LOCKS = '/var/lib/hengxin-domestic/studio-locks'
SOCKET_DIR = '/run/hengxin-domestic-skill-publisher'
SOCKET = SOCKET_DIR + '/publisher.sock'
PUBLISHER = 'domestic-skill-publisher'
LOCK_GROUP = '986'
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')


def bind(source, target, *, readonly):
    return {'type': 'bind', 'source': source, 'target': target, 'read_only': readonly,
            'bind': {'create_host_path': False}}


def native_environment():
    return {'DOMESTIC_SKILL_ROOT': SKILLS, 'DOMESTIC_STUDIO_LOCK_ROOT': LOCKS,
            'DOMESTIC_STUDIO_PROTECTED': '1'}


def database_identity(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'postgresql+psycopg' or not parsed.hostname or not parsed.path.strip('/'):
            raise ValueError('Invalid database endpoint')
        return parsed.hostname.lower(), parsed.port or 5432, unquote(parsed.path.lstrip('/'))
    except (TypeError, ValueError):
        raise ValueError('Invalid database endpoint') from None


def candidate(compose, release):
    """Return a candidate without exposing secrets or altering the input."""
    root = PurePosixPath(str(release))
    if (root.parent != PurePosixPath('/opt/hengxin-unified-releases')
            or not root.name or root.name.startswith('.') or '..' in root.parts):
        raise ValueError('Invalid immutable release root')
    result = copy.deepcopy(compose)
    if not isinstance(result, dict) or not isinstance(result.get('services'), dict):
        raise ValueError('Invalid compose configuration')
    services = result['services']
    if PUBLISHER in services or not isinstance(services.get('domestic-api'), dict):
        raise ValueError('Publisher already exists or domestic API is missing')
    api = services['domestic-api']
    env = api.get('environment')
    image = api.get('image')
    if (not isinstance(env, dict) or not isinstance(env.get('DATABASE_URL'), str)
            or not env['DATABASE_URL'].startswith('postgresql+psycopg://')
            or env.get('APP_ENV') not in ('production', 'development')
            or env.get('HX_BUSINESS_CONTEXT', 'domestic') != 'domestic'
            or any(str(env.get(key, 'false')).lower() not in ('false', '0', 'no', 'off')
                   for key in ('ENABLE_DEV_IDENTITY', 'ENABLE_TEST_JOBS'))
            or not isinstance(image, str) or not IMAGE.fullmatch(image)
            or LOCK_GROUP not in [str(group) for group in api.get('group_add', [])]):
        raise ValueError('Domestic API runtime identity is not suitable')
    overseas = services.get('overseas-skill-publisher', {}).get('environment', {})
    overseas_url = overseas.get('OVERSEAS_DATABASE_URL') if isinstance(overseas, dict) else None
    if overseas_url and database_identity(env['DATABASE_URL']) == database_identity(overseas_url):
        raise ValueError('Domestic and overseas databases must be separate')
    database_identity(env['DATABASE_URL'])
    required_env = dict(native_environment(), DOMESTIC_SKILL_PUBLISH_SOCKET=SOCKET)
    if any(key in env and env[key] != value for key, value in required_env.items()):
        raise ValueError('Existing domestic Studio environment conflicts')
    mounts = api.get('volumes')
    if not isinstance(mounts, list) or any(not isinstance(row, dict) or not row.get('target') for row in mounts):
        raise ValueError('Invalid domestic API mounts')
    reserved = {SKILLS, LOCKS, SOCKET_DIR}
    targets = [PurePosixPath(row['target']) for row in mounts]
    if any(not target.is_absolute() or '..' in target.parts for target in targets):
        raise ValueError('Invalid existing mount target')
    if any(target == path or target in path.parents or path in target.parents
           for target in targets for path in map(PurePosixPath, reserved)):
        raise ValueError('Domestic Studio mount conflicts with an existing mount')
    mounts.extend((bind(SKILLS, SKILLS, readonly=True), bind(LOCKS, LOCKS, readonly=False),
                   bind(SOCKET_DIR, SOCKET_DIR, readonly=True)))
    env.update(required_env)
    health = ("import socket; s=socket.socket(socket.AF_UNIX); s.settimeout(3); "
              f"s.connect('{SOCKET}'); s.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); "
              "assert s.recv(128).split(b'\\r\\n',1)[0].split()[1]==b'200'")
    publisher = {
        'image': image, 'container_name': 'hengxin-lan-' + PUBLISHER, 'user': '0:0',
        'command': ['python', '-B', '-m', 'app.modules.domestic_studio.skill_publisher'],
        'working_dir': '/app', 'init': True, 'read_only': True,
        'restart': 'unless-stopped', 'pull_policy': 'never',
        'security_opt': ['no-new-privileges:true'], 'cap_drop': ['ALL'], 'cap_add': ['CHOWN'],
        'tmpfs': ['/tmp:rw,noexec,nosuid,size=64m'],
        'environment': {
            'APP_ENV': 'production', 'HX_BUSINESS_CONTEXT': 'domestic', 'DATABASE_URL': env['DATABASE_URL'],
            'MINIO_ACCESS_KEY': 'not-used-by-publisher', 'MINIO_SECRET_KEY': 'not-used-by-publisher',
            'DB_APPLICATION_NAME': 'hx-domestic-skill-publisher', 'DB_POOL_SIZE': '1', 'DB_MAX_OVERFLOW': '0',
            'DOMESTIC_SKILL_ROOT': SKILLS, 'DOMESTIC_SKILL_TRANSFER_ROOT': TRANSFERS,
            'DOMESTIC_SKILL_PUBLISH_SOCKET': SOCKET, 'DOMESTIC_STUDIO_PROTECTED': '1',
        },
        'volumes': [bind(SKILLS, SKILLS, readonly=False), bind(TRANSFERS, TRANSFERS, readonly=False),
                    bind(SOCKET_DIR, SOCKET_DIR, readonly=False),
                    bind(str(root / 'backend/app'), '/app/app', readonly=True)],
        'healthcheck': {'test': ['CMD', 'python', '-c', health], 'interval': '10s',
                        'timeout': '5s', 'retries': 3, 'start_period': '20s'},
    }
    if 'networks' not in api:
        raise ValueError('Domestic API network is missing')
    publisher['networks'] = copy.deepcopy(api['networks'])
    services[PUBLISHER] = publisher
    return result
