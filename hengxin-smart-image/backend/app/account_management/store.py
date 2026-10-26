"""Host-only account bindings. Legacy grants are referenced, never duplicated."""
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from app.execution.managed_credentials import _object, _identity, _jwt, _remaining
from app.execution.managed_credentials_files import directory


class AccountError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def now():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


def read_auth(path):
    with directory(path.parent) as folder:
        auth = _object(folder.read(path.name))
    _identity(auth)
    return auth


def metadata(auth):
    account, _ = _identity(auth)
    claims = _jwt(auth['tokens']['id_token'])
    email = claims.get('email')
    return {'email': email if isinstance(email, str) and email else '已登录账号',
            'workspace': account}


class AccountStore:
    def __init__(self, root, legacy):
        self.root, self.legacy = Path(root), Path(legacy)
        self.lock = threading.RLock()
        with directory(self.root, create=True):
            pass
        with directory(self.root / 'grants', create=True):
            pass
        with self.lock:
            with directory(self.root) as folder:
                if folder.read('state.json', optional=True) is None:
                    # Missing/unreadable legacy credentials do not create a fresh grant.
                    self.save(dict(generation='legacy', revision=0, status='unchecked',
                                   checked='', updated='', audit=[]))

    def load(self):
        with directory(self.root) as folder:
            state = _object(folder.read('state.json'))
        generation = state['generation']
        if generation not in (None, 'legacy'):
            UUID(generation)
        if not isinstance(state['revision'], int) or state['revision'] < 0:
            raise ValueError('invalid account state')
        return state

    def save(self, state):
        with directory(self.root) as folder:
            folder.write('state.json', json.dumps(state, ensure_ascii=False).encode())

    def source(self, state=None):
        state = state or self.load()
        generation = state['generation']
        if generation is None:
            raise AccountError(409, '当前业务尚未配置 Codex 账号')
        if generation == 'legacy':
            return self.legacy
        return self.root / 'grants' / str(UUID(generation)) / 'auth.json'

    def identity(self, state=None):
        return _identity(read_auth(self.source(state)))

    def view(self, checking=False):
        with self.lock:
            state = self.load()
            result = {key: state[key] for key in ('revision', 'status', 'checked', 'updated', 'audit')}
            result.update(email='', workspace='', checking=checking)
            if state['generation'] is not None:
                try:
                    auth = read_auth(self.source(state))
                    result.update(metadata(auth))
                    # Expired access with a refresh token is not proof of invalid authorization.
                    if _remaining(auth) <= 0 and not auth['tokens'].get('refresh_token'):
                        result['status'] = 'expired'
                except Exception:
                    result.update(status='network', email='账号信息暂不可读')
            return result

    @staticmethod
    def audit(state, actor, action, result):
        state['audit'] = [dict(time=now(), operator=actor['name'], action=action, result=result),
                          *state['audit'][:99]]

    @staticmethod
    def expect(state, revision):
        if isinstance(revision, bool) or revision != state['revision']:
            raise AccountError(409, '配置已被更新，请刷新页面后重试')

    def activate(self, auth, revision, actor):
        with self.lock:
            state = self.load()
            self.expect(state, revision)
            generation = str(uuid4())
            path = self.root / 'grants' / generation
            with directory(path, create=True) as folder:
                folder.write('auth.json', json.dumps(auth).encode())
            state.update(generation=generation, revision=revision + 1, status='ready',
                         checked=now(), updated=now())
            self.audit(state, actor, '授权并启用', '成功')
            self.save(state)  # Atomic binding publication; old grants remain private for recovery.
            return self.view()

    def remove(self, revision, actor):
        with self.lock:
            state = self.load()
            self.expect(state, revision)
            state.update(generation=None, revision=revision + 1, status='empty', checked='', updated=now())
            self.audit(state, actor, '移除账号配置', '已移除，任务和历史记录保留')
            self.save(state)
            return self.view()
