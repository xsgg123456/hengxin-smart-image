"""Server-owned OAuth refresh; private CLI homes receive access credentials only."""
import base64
import copy
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .managed_credentials_files import directory, refresh_lock

TOKEN_ENDPOINT = 'https://auth.openai.com/oauth/token'
CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
AUTH_CLAIM = 'https://api.openai.com/auth'
NETWORK_TIMEOUT = 30


class CredentialsError(RuntimeError):
    def __init__(self, code='credentials_invalid'):
        self.code = code
        messages = {
            'credentials_account_changed': 'Codex 登录账号或工作区已变更，请管理员恢复原登录后重试。',
            'credentials_busy': 'Codex 登录凭据正在更新，请稍后重试。',
            'credentials_refresh_failed': 'Codex 登录已失效或暂时无法更新，请管理员恢复登录后重试。',
        }
        super().__init__(messages.get(code, 'Codex 登录凭据不可用，请管理员恢复登录后重试。'))


def _object(data):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('duplicate credential field')
            result[key] = item
        return result
    value = json.loads(data, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('invalid credential object')
    return value


def _jwt(value):
    if not isinstance(value, str) or len(value.split('.')) != 3:
        raise ValueError('invalid jwt')
    encoded = value.split('.')[1]
    return _object(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _kind(auth):
    mode = auth.get('auth_mode')
    if mode in (None, 'apikey') and _nonempty(auth.get('OPENAI_API_KEY')):
        return 'apikey'
    if mode in (None, 'chatgpt') and isinstance(auth.get('tokens'), dict):
        return 'chatgpt'
    raise ValueError('unsupported authentication mode')


def _identity(auth):
    tokens = auth['tokens']
    account = tokens.get('account_id')
    claims = _jwt(tokens.get('id_token'))
    namespace = claims.get(AUTH_CLAIM)
    if not _nonempty(account) or not isinstance(namespace, dict):
        raise ValueError('missing account identity')
    if namespace.get('chatgpt_account_id') != account or not _nonempty(claims.get('sub')):
        raise ValueError('invalid account identity')
    access = _jwt(tokens.get('access_token'))
    access_auth = access.get(AUTH_CLAIM, {})
    if not isinstance(access_auth, dict):
        raise ValueError('invalid access identity')
    if access_auth.get('chatgpt_account_id') != account:
        raise CredentialsError('credentials_account_changed')
    if access.get('sub') is not None and access['sub'] != claims['sub']:
        raise CredentialsError('credentials_account_changed')
    return account, claims['sub']


def _remaining(auth):
    exp = _jwt(auth['tokens'].get('access_token')).get('exp')
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp):
        raise ValueError('missing token expiry')
    return exp - time.time()


def _check_previous(auth, previous):
    if previous is None:
        return
    if _kind(auth) != _kind(previous):
        raise CredentialsError('credentials_account_changed')
    if _kind(auth) == 'chatgpt':
        if _identity(auth) != _identity(previous):
            raise CredentialsError('credentials_account_changed')
    elif auth['OPENAI_API_KEY'] != previous['OPENAI_API_KEY']:
        raise CredentialsError('credentials_account_changed')


# A socket timeout alone permits an indefinitely slow response. An isolated
# standard-library helper gives the complete exchange a hard wall-clock bound;
# secrets travel only through pipes, never argv/environment or application logs.
_REFRESH_SCRIPT = '''
import json, sys, urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('redirect rejected')
try:
    payload = sys.stdin.buffer.read(131073)
    if len(payload) > 131072:
        raise ValueError('request too large')
    request = urllib.request.Request('https://auth.openai.com/oauth/token',
        method='POST', data=payload, headers={'Content-Type': 'application/json',
                                            'Accept': 'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        data = response.read(131073)
        if len(data) > 131072:
            raise ValueError('response too large')
        sys.stdout.buffer.write(data)
except Exception:
    sys.exit(1)
'''


def _request_refresh(refresh_token):
    payload = json.dumps({
        'client_id': CLIENT_ID, 'grant_type': 'refresh_token', 'refresh_token': refresh_token,
    }).encode()
    try:
        result = subprocess.run([sys.executable, '-I', '-c', _REFRESH_SCRIPT],
                                input=payload, capture_output=True, timeout=NETWORK_TIMEOUT,
                                check=True)
        if len(result.stdout) > 131072:
            raise ValueError('response too large')
        return _object(result.stdout)
    except Exception:
        raise CredentialsError('credentials_refresh_failed') from None


def _refresh(auth, previous, required):
    tokens = auth['tokens']
    refresh = tokens.get('refresh_token')
    if not _nonempty(refresh):
        raise CredentialsError('credentials_refresh_failed')
    response = _request_refresh(refresh)
    updated = copy.deepcopy(auth)
    for name in ('access_token', 'id_token', 'refresh_token'):
        value = response.get(name)
        if value is not None:
            if not _nonempty(value):
                raise CredentialsError('credentials_refresh_failed')
            updated['tokens'][name] = value
    if not _nonempty(response.get('access_token')) or _remaining(updated) < required:
        raise CredentialsError('credentials_refresh_failed')
    if response.get('account_id', tokens['account_id']) != tokens['account_id']:
        raise CredentialsError('credentials_account_changed')
    if _identity(updated) != _identity(auth):
        raise CredentialsError('credentials_account_changed')
    _check_previous(updated, previous)
    updated['last_refresh'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return updated


def _encode(auth):
    return (json.dumps(auth, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def access_credentials(source: Path, timeout_seconds: int, *, expected_identity=None):
    """Return access-only auth after a single, centrally locked refresh."""
    from .credential_identity import identity, check_identity
    try:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 0:
            raise ValueError('invalid execution timeout')
        source = Path(source)
        with directory(source.parent) as master:
            with refresh_lock(master, source.name + '.refresh.lock'):
                auth = _object(master.read(source.name))
                check_identity(identity(auth), expected_identity)
                if _kind(auth) == 'chatgpt':
                    required = timeout_seconds + 300
                    if _remaining(auth) < required:
                        auth = _refresh(auth, None, required)
                        master.write(source.name, _encode(auth))
                    auth = copy.deepcopy(auth)
                    auth['tokens']['refresh_token'] = ''
                # Do not forward incidental secrets or future refresh metadata.
                if _kind(auth) == 'apikey':
                    return {'auth_mode': 'apikey', 'OPENAI_API_KEY': auth['OPENAI_API_KEY']}
                result = {key: auth[key] for key in
                          ('auth_mode', 'OPENAI_API_KEY', 'last_refresh') if key in auth}
                result['tokens'] = {key: auth['tokens'][key] for key in
                                    ('id_token', 'access_token', 'refresh_token', 'account_id')}
                return result
    except CredentialsError:
        raise
    except TimeoutError:
        raise CredentialsError('credentials_busy') from None
    except Exception:
        raise CredentialsError() from None


def sync_credentials(source: Path, home: Path, timeout_seconds: int, *,
                     broker_socket=None, control=None, require_existing=False):
    """Refresh centrally once if needed, then atomically replace private auth.json.

    The caller must stop the private CLI before syncing. JWT claims here only
    constrain continuity of trusted server credentials; they do not verify tokens.
    """
    try:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 0:
            raise ValueError('invalid execution timeout')
        source, home = Path(source), Path(home)
        if os.path.normcase(os.path.abspath(source)) == os.path.normcase(
                os.path.abspath(home / '.codex' / 'auth.json')):
            raise ValueError('shared credential destination')
        from .credential_identity import binding, identity, check_identity
        with directory(home / '.codex', create=True) as private:
            raw = private.read('auth.json', optional=True)
            previous = _object(raw) if raw is not None else None
            with binding(control, home, previous, require_existing) as (expected, save):
                if broker_socket:
                    from .credential_broker_client import request_credentials
                    auth = request_credentials(broker_socket, timeout_seconds)
                else:
                    auth = access_credentials(source, timeout_seconds, expected_identity=expected)
                current = identity(auth)
                check_identity(current, expected)
                # Save the trusted binding first: a failed private write can recover
                # using this identity, never by silently trusting a future account.
                save(current)
                private.write('auth.json', _encode(auth))
    except CredentialsError:
        raise
    except TimeoutError:
        raise CredentialsError('credentials_busy') from None
    except Exception:
        raise CredentialsError() from None
