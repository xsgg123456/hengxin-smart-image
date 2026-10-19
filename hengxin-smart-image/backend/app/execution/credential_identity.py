"""Session identities live outside the model-writable filesystem."""
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

from .managed_credentials import CredentialsError, _identity, _kind, _object, _encode
from .managed_credentials_files import directory, refresh_lock


def identity(auth):
    if _kind(auth) == 'chatgpt':
        account, subject = _identity(auth)
        return {'mode': 'chatgpt', 'account': account, 'subject': subject}
    return {'mode': 'apikey', 'fingerprint': hashlib.sha256(
        auth['OPENAI_API_KEY'].encode()).hexdigest()}


def check_identity(current, expected):
    if expected is not None and current != expected:
        raise CredentialsError('credentials_account_changed')


def _read_binding(folder):
    raw = folder.read('auth-identity.json', optional=True)
    if raw is None:
        return None
    value = _object(raw)
    keys = {'mode', 'account', 'subject'} if value.get('mode') == 'chatgpt' else {'mode', 'fingerprint'}
    if (set(value) != keys or value.get('mode') not in ('chatgpt', 'apikey')
            or not all(isinstance(item, str) and item.strip() for item in value.values())):
        raise ValueError('invalid credential binding')
    if value['mode'] == 'apikey' and (len(value['fingerprint']) != 64
            or any(c not in '0123456789abcdef' for c in value['fingerprint'])):
        raise ValueError('invalid key fingerprint')
    return value


@contextmanager
def binding(control, home, previous, require_existing):
    if control is None:
        if require_existing and previous is None:
            raise CredentialsError()
        yield identity(previous) if previous is not None else None, lambda _: None
        return
    home = Path(os.path.abspath(home))
    control = Path(os.path.abspath(control))
    # All supported workspaces mount home and work/rounds, never sibling control.
    # A caller cannot accidentally put the trust marker inside a writable mount.
    if control != home.parent / 'control':
        raise ValueError('control must be the private home sibling')
    with directory(control) as folder:
        if os.name == 'posix':
            os.fchmod(folder.fd, 0o700)
        with refresh_lock(folder, 'auth-identity.lock'):
            expected = _read_binding(folder)
            if expected is None:
                if require_existing and previous is None:
                    raise CredentialsError()
                expected = identity(previous) if previous is not None else None
            # Once bound, even a deleted or rewritten private auth is no authority.
            yield expected, lambda current: folder.write('auth-identity.json', _encode(current))
