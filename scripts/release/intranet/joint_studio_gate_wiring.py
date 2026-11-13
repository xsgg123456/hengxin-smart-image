"""Bind a read-only release gate to every HTTP and asynchronous entry point."""
import copy
from pathlib import PurePosixPath

import domestic_studio_wiring as wiring


DIRECTORY = '/var/lib/hengxin-domestic/release-gate'
ENVIRONMENT = 'HX_RELEASE_GATE_DIR'
SERVICES = ('domestic-api', 'overseas-api', 'identity-api', 'domestic-api-image-worker',
            'domestic-api-image-outbox', 'domestic-image-variants', 'domestic-outbox')
NATIVE = ('hengxin-retention', 'hengxin-domestic-deletions', 'hengxin-overseas-outbox',
          'hengxin-vps-codex-worker', 'hengxin-overseas-worker',
          'hengxin-codex-accounts', 'hengxin-codex-auth')


def candidate(compose):
    result = copy.deepcopy(compose)
    for name in SERVICES:
        service = result['services'].get(name)
        if not isinstance(service, dict):
            raise ValueError('Missing release-gated service: ' + name)
        env, mounts = service.get('environment'), service.setdefault('volumes', [])
        if not isinstance(env, dict) or not isinstance(mounts, list):
            raise ValueError('Invalid release-gated service configuration: ' + name)
        if ENVIRONMENT in env and env[ENVIRONMENT] != DIRECTORY:
            raise ValueError('Conflicting release gate environment: ' + name)
        gate = PurePosixPath(DIRECTORY)
        for item in mounts:
            if not isinstance(item, dict) or not item.get('target'):
                raise ValueError('Invalid release-gated mount: ' + name)
            target = PurePosixPath(item['target'])
            if not target.is_absolute() or '..' in target.parts:
                raise ValueError('Invalid release-gated mount target: ' + name)
            if target == gate or target in gate.parents or gate in target.parents:
                raise ValueError('Conflicting release gate mount: ' + name)
        mounts.append(wiring.bind(DIRECTORY, DIRECTORY, readonly=True))
        env[ENVIRONMENT] = DIRECTORY
    return result


def verify(live, ctx):
    for name in SERVICES:
        info = live[name]
        values = info['Config'].get('Env') or []
        pairs = [item.split('=', 1) for item in values if isinstance(item, str) and '=' in item]
        if (len(pairs) != len(values) or len({key for key, _ in pairs}) != len(pairs)
                or dict(pairs).get(ENVIRONMENT) != DIRECTORY):
            raise RuntimeError('Release gate environment differs: ' + name)
        mounts = [item for item in info['Mounts'] if item.get('Destination') == DIRECTORY]
        if (len(mounts) != 1 or mounts[0].get('Source') != DIRECTORY
                or mounts[0].get('Type') != 'bind' or mounts[0].get('RW') is not False):
            raise RuntimeError('Release gate mount differs: ' + name)
    for name in NATIVE:
        if ctx[name]['env'].get(ENVIRONMENT) != DIRECTORY:
            raise RuntimeError('Native release gate environment differs: ' + name)
