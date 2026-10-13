"""Typed recovery rows and credential-free audit values."""
import hashlib
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID


class SafetyError(ValueError):
    """Only fixed, non-sensitive messages may cross the CLI boundary."""


SENSITIVE = re.compile(r'password|passwd|secret|token|credential|session|(?:^|_)key(?:$|_)', re.I)


def encode(value):
    if isinstance(value, (datetime, date, UUID, Decimal)):
        return {'$type': type(value).__name__, 'value': str(value)}
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise SafetyError('unsupported_recovery_value')


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'$type', 'value'}:
            kinds = {'datetime': datetime.fromisoformat, 'date': date.fromisoformat,
                     'UUID': UUID, 'Decimal': Decimal}
            if value['$type'] not in kinds:
                raise SafetyError('invalid_recovery_type')
            return kinds[value['$type']](value['value'])
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def canonical(value):
    return json.dumps(encode(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def safe_rows(rows):
    def inspect_value(value):
        if isinstance(value, dict):
            if any(SENSITIVE.search(str(name)) for name in value):
                raise SafetyError('credential_column_in_recovery_table')
            for item in value.values():
                inspect_value(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                inspect_value(item)
    inspect_value(rows)
    return encode(rows)


def write_json(path, value, exclusive=False):
    """Write durable evidence before any delete; never overwrite a prepared bundle."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(encode(value), stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if os.name != 'nt':
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def column_value(column, value):
    try:
        kind = column.type.python_type
        if kind is UUID:
            return UUID(str(value))
        return str(value) if kind is str and isinstance(value, UUID) else value
    except (ValueError, NotImplementedError):
        raise SafetyError('invalid_member_id') from None
