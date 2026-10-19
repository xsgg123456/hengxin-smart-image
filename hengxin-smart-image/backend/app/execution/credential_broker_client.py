"""Bounded local credential protocol; neither paths nor identities cross requests."""
import json
import socket
import struct
import time

from .managed_credentials import CredentialsError, _kind, _remaining, _object
from .credential_identity import identity

MAX_REQUEST = 128
MAX_RESPONSE = 131072
CLIENT_TIMEOUT = 75
ERROR_CODES = frozenset({'credentials_invalid', 'credentials_busy',
                         'credentials_refresh_failed', 'credentials_account_changed'})


def timeout_value(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 10 <= value <= 7200:
        raise ValueError('invalid execution timeout')
    return value


def _receive(connection, length, deadline):
    data = bytearray()
    while len(data) < length:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('credential exchange timed out')
        connection.settimeout(remaining)
        block = connection.recv(length - len(data))
        if not block:
            raise ValueError('incomplete credential exchange')
        data.extend(block)
    return bytes(data)


def receive(connection, limit, deadline):
    length = struct.unpack('!I', _receive(connection, 4, deadline))[0]
    if not 0 < length <= limit:
        raise ValueError('credential frame too large')
    return _object(_receive(connection, length, deadline))


def send(connection, value, limit, deadline):
    payload = json.dumps(value, separators=(',', ':')).encode()
    if not 0 < len(payload) <= limit:
        raise ValueError('credential frame too large')
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('credential exchange timed out')
    connection.settimeout(remaining)
    connection.sendall(struct.pack('!I', len(payload)) + payload)


def request_credentials(path, timeout_seconds):
    try:
        timeout_value(timeout_seconds)
        deadline = time.monotonic() + CLIENT_TIMEOUT
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(CLIENT_TIMEOUT)
            connection.connect(str(path))
            send(connection, {'timeout_seconds': timeout_seconds}, MAX_REQUEST, deadline)
            response = receive(connection, MAX_RESPONSE, deadline)
        if set(response) == {'error'} and response['error'] in ERROR_CODES:
            raise CredentialsError(response['error'])
        if set(response) != {'auth'} or not isinstance(response['auth'], dict):
            raise ValueError('invalid credential response')
        auth = response['auth']
        identity(auth)
        if _kind(auth) == 'chatgpt':
            if auth['tokens'].get('refresh_token') != '' or _remaining(auth) < timeout_seconds + 290:
                raise ValueError('invalid private access token')
        return auth
    except CredentialsError:
        raise
    except Exception:
        raise CredentialsError() from None
