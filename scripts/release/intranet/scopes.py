"""Explicit LAN service ownership; the gateway and DATA never belong to a release."""
from contextlib import contextmanager

GROUPS = ('domestic', 'overseas', 'shared')
DOMESTIC_PUBLISHER = 'domestic-skill-publisher'
APPS = {
    'domestic': ('domestic-api', 'domestic-api-image-worker', 'domestic-api-image-outbox',
                 'domestic-image-variants', 'domestic-outbox'),
    'overseas': ('overseas-api', 'overseas-skill-publisher'),
    'shared': ('identity-api',),
}
NATIVE = {
    'domestic': ('hengxin-vps-codex-worker', 'hengxin-retention', 'hengxin-domestic-deletions'),
    'overseas': ('hengxin-overseas-worker', 'hengxin-overseas-outbox'),
    'shared': ('hengxin-codex-accounts', 'hengxin-codex-auth'),
}
WORKERS = {
    'domestic': ('hengxin-vps-codex-worker', 'domestic-api-image-worker'),
    'overseas': ('hengxin-overseas-worker',), 'shared': (),
}
UI = {s: s + '-ui' for s in GROUPS}
QUEUES = {'hengxin-vps-codex-worker': 'celery', 'hengxin-overseas-worker': 'overseas.cli',
          'domestic-api-image-worker': 'api_image_edits'}
READY = {'domestic': (18008, '/api/v1/health/ready'),
         'overseas': (18018, '/api/overseas/v1/health/ready'),
         'shared': (18012, '/api/identity/v1/config')}


def has_domestic_publisher(state):
    return DOMESTIC_PUBLISHER in state.get('images', {})


def apps(scope, publisher=False):
    validate(scope)
    return APPS[scope] + ((DOMESTIC_PUBLISHER,) if scope == 'domestic' and publisher else ())


def validate(scope, mode='full'):
    if scope not in GROUPS or mode not in ('full', 'frontend'):
        raise ValueError('Unknown release scope/mode')


@contextmanager
def replace(obj, **values):
    """Caller holds the single shared release lock; always restore globals."""
    old = {k: getattr(obj, k) for k in values}
    try:
        for k, value in values.items():
            setattr(obj, k, value)
        yield
    finally:
        for k, value in old.items():
            setattr(obj, k, value)
