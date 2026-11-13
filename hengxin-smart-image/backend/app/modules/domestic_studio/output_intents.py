"""Durable single-write evidence for generated and manually recovered files."""
from types import SimpleNamespace
from uuid import UUID

from app.overseas.studio.files import verify


def details(expected):
    return dict(bucket=expected['bucket'], object_key=expected['object_key'],
                size_bytes=expected['size_bytes'], checksum=expected['checksum'])


def reserve(turn, identity, expected):
    if not isinstance(turn.output_intents, dict):
        raise ValueError('Invalid output write intents')
    key = str(identity)
    existing = turn.output_intents.get(key)
    wanted = details(expected)
    if existing is not None:
        if (not isinstance(existing, dict) or existing.get('status') not in ('uploading', 'ready')
                or {k: v for k, v in existing.items() if k != 'status'} != wanted):
            raise ValueError('Output write identity conflict')
        return False
    turn.output_intents = {**turn.output_intents, key: {**wanted, 'status': 'uploading'}}
    return True


def confirm(turn, identity, expected):
    if reserve(turn, identity, expected):
        raise ValueError('Output write intent missing')
    key = str(identity)
    turn.output_intents = {**turn.output_intents, key: {**details(expected), 'status': 'ready'}}


def inventory(turn, channel, published, store):
    if not isinstance(turn.output_intents, dict):
        raise ValueError('Invalid output write intents')
    result = set()
    for identity, item in turn.output_intents.items():
        try:
            if str(UUID(identity)) != identity:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Invalid output write identity') from None
        prefix = f'domestic-studio/outputs/{channel.owner_id}/{channel.workspace}/{channel.id}/{turn.id}/'
        if (not isinstance(item, dict) or set(item) != {'bucket', 'object_key', 'size_bytes', 'checksum', 'status'}
                or not isinstance(item['bucket'], str) or not item['bucket']
                or item['object_key'] != prefix + identity or type(item['size_bytes']) is not int
                or item['size_bytes'] < 0 or not isinstance(item['checksum'], str)
                or len(item['checksum']) != 64 or item['status'] not in ('uploading', 'ready')):
            raise ValueError('Invalid output write intent')
        row = published.get(identity)
        expected = {key: item[key] for key in ('bucket', 'object_key', 'size_bytes', 'checksum')}
        if row is not None and any(getattr(row, key) != value for key, value in expected.items()):
            raise ValueError('Published output differs from its write intent')
        if item['status'] == 'ready' and row is None:
            raise ValueError('Confirmed output record missing')
        if item['status'] == 'uploading':
            # The one allowed PUT may still arrive after its caller has exited.
            verify(store, SimpleNamespace(**expected))
        result.add((item['bucket'], item['object_key']))
    return result
