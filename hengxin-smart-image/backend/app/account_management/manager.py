"""One pending authorization per business; publishing requires an explicit CAS."""
import shutil
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

from .device import device_login, VERIFICATION_URL
from .probe import probe
from .store import AccountError, AccountStore, metadata, now, read_auth
from app.execution.managed_credentials import _identity, _remaining


class AccountManager:
    def __init__(self, store: AccountStore, binary, bwrap, *, login=device_login, verify=probe):
        self.store, self.binary, self.bwrap = store, binary, bwrap
        self.login, self.verify = login, verify
        self.lock = threading.RLock()
        self.pending = None
        self.checking = False
        self.last_check = 0
        self.stopping = threading.Event()
        self.threads = []
        self.scratch = store.root / 'temporary'
        self.scratch.mkdir(mode=0o700, exist_ok=True)
        if self.scratch.is_symlink():
            raise ValueError('unsafe temporary directory')
        # The daemon is singleton; systemd kills its entire process group before restart.
        for path in self.scratch.iterdir():
            if path.is_symlink() or not path.is_dir():
                raise ValueError('unsafe leftover authorization')
            shutil.rmtree(path)

    def _spawn(self, function, *args):
        self.threads = [t for t in self.threads if t.is_alive()]
        thread = threading.Thread(target=function, args=args, daemon=True)
        self.threads.append(thread)
        thread.start()

    def status(self):
        return self.store.view(self.checking)

    def check(self, actor):
        with self.lock:
            if self.checking:
                return self.status()
            if time.monotonic() - self.last_check < 30:
                raise AccountError(409, '请稍后再检测，避免重复调用')
            with self.store.lock:
                state = self.store.load()
                source = self.store.source(state)
            self.checking = True
            self.last_check = time.monotonic()
            self._spawn(self._check, source, state['revision'], actor)
            return self.status()

    def _check(self, source, revision, actor):
        result = 'network'
        try:
            result = self.verify(source, self.scratch, self.binary, self.bwrap, self.stopping.is_set)
        except Exception:
            pass
        finally:
            with self.lock, self.store.lock:
                state = self.store.load()
                if state['revision'] == revision:
                    state.update(status=result, checked=now())
                    self.store.audit(state, actor, '检测连接',
                        {'ready': '可用', 'expired': '授权已失效'}.get(result, '连接异常，授权状态未确认'))
                    self.store.save(state)
                self.checking = False

    @staticmethod
    def view(pending):
        return {k: pending[k] for k in ('id', 'step', 'userCode', 'verificationUrl', 'expiresAt',
            'candidateEmail', 'candidateWorkspace', 'different', 'message')}

    def start(self, actor, intent, revision):
        with self.lock, self.store.lock:
            state = self.store.load()
            self.store.expect(state, revision)
            if self.pending and self.pending['step'] == 'expired':
                if self.pending.get('cleanupComplete'):
                    self.pending = None
                else:
                    raise AccountError(409, '授权流程正在结束，请稍后重试')
            if self.pending:
                if self.pending['cancel'].is_set():
                    raise AccountError(409, '授权流程正在结束，请稍后重试')
                if (self.pending['actor']['id'] == actor['id'] and self.pending['intent'] == intent
                        and not self.pending['cancel'].is_set()):
                    return self.view(self.pending)
                raise AccountError(409, '当前业务已有授权流程，请完成或取消后重试')
            configured = state['generation'] is not None
            if intent not in ('connect', 'renew', 'replace') or (intent == 'connect') == configured:
                raise AccountError(409, '账号配置已变化，请刷新页面后重试')
            previous = None
            if configured:
                try:
                    previous = self.store.identity(state)
                except Exception:
                    if intent == 'renew':
                        raise AccountError(409, '原账号身份暂不可读，请检查服务后重试') from None
            pending = dict(id=str(uuid4()), step='starting', userCode='', verificationUrl=VERIFICATION_URL,
                expiresAt=int(time.time()) + 600, candidateEmail='', candidateWorkspace='',
                different=False, message='', actor=actor, intent=intent, revision=revision,
                previous=previous, configured=configured, cancel=threading.Event(), retry=threading.Event())
            self.pending = pending
            self.store.audit(state, actor, '发起授权', '等待官方登录')
            self.store.save(state)
            self._spawn(self._authorize, pending)
            return self.view(pending)

    def _owned(self, actor, identifier):
        pending = self.pending
        if pending is None or pending['id'] != identifier:
            raise AccountError(404, '授权流程已结束，请重新开始')
        if pending['actor']['id'] != actor['id']:
            raise AccountError(403, '只能操作本人发起的授权')
        if pending['cancel'].is_set():
            raise AccountError(409, '授权流程正在结束，请稍后重试')
        return pending

    def poll(self, actor, identifier):
        with self.lock:
            pending = self._owned(actor, identifier)
            if time.time() >= pending['expiresAt']:
                pending['step'] = 'expired'
            return self.view(pending)

    def cancel(self, actor, identifier):
        with self.lock:
            pending = self._owned(actor, identifier)
            pending['cancel'].set()
            if pending.get('cleanupComplete'):
                self.pending = None
            return {'ok': True}

    def retry(self, actor, identifier):
        with self.lock:
            pending = self._owned(actor, identifier)
            if pending['step'] != 'failed' or 'source' not in pending or time.time() >= pending['expiresAt']:
                raise AccountError(409, '请重新获取授权码')
            pending.update(step='checking', message='')
            pending['retry'].set()
            return self.view(pending)

    def activate(self, actor, identifier, acknowledged):
        with self.lock, self.store.lock:
            pending = self._owned(actor, identifier)
            if pending['step'] != 'verified' or time.time() >= pending['expiresAt']:
                raise AccountError(409, '新授权尚未通过检测或已超时，请重试')
            if pending['different'] and (pending['intent'] != 'replace' or acknowledged is not True):
                raise AccountError(409, '更换账号前请确认旧会话的影响')
            auth = read_auth(pending['source'])
            if _identity(auth) != pending['identity'] or _remaining(auth) < 300:
                raise AccountError(409, '授权已变化或即将过期，请重新检测')
            self.store.expect(self.store.load(), pending['revision'])
            if pending['configured']:
                try:
                    current_identity = self.store.identity()
                except Exception:
                    raise AccountError(409, '原账号身份暂不可读，请刷新后重新授权') from None
                if current_identity != pending['previous']:
                    raise AccountError(409, '原账号身份已变化，请刷新后重新授权')
            result = self.store.activate(auth, pending['revision'], actor)
            pending['activated'] = True
            pending['cancel'].set()
            return result

    def remove(self, actor, revision):
        with self.lock:
            result = self.store.remove(revision, actor)
            if self.pending:
                self.pending['cancel'].set()
            return result

    def _authorize(self, pending):
        cancelled = lambda: (pending['cancel'].is_set() or self.stopping.is_set()
                             or time.time() >= pending['expiresAt'])
        try:
            with tempfile.TemporaryDirectory(prefix='login-', dir=self.scratch) as temporary:
                def publish(code):
                    with self.lock:
                        pending.update(userCode=code, step='waiting')
                success = self.login(Path(temporary), self.binary, cancelled, publish, pending['expiresAt'])
                if cancelled():
                    return
                if not success:
                    with self.lock:
                        pending.update(step='expired' if time.time() >= pending['expiresAt'] else 'failed',
                                       message='授权未完成，请重新获取授权码')
                else:
                    source = Path(temporary) / '.codex' / 'auth.json'
                    auth = read_auth(source)
                    identity, info = _identity(auth), metadata(auth)
                    with self.lock:
                        pending.update(source=source, identity=identity,
                            candidateEmail=info['email'], candidateWorkspace=info['workspace'],
                            different=pending['configured'] and identity != pending['previous'])
                        if pending['intent'] == 'renew' and pending['different']:
                            pending['step'] = 'mismatch'
                        else:
                            pending['retry'].set()
                while not cancelled() and time.time() < pending['expiresAt']:
                    if pending['retry'].wait(.25):
                        pending['retry'].clear()
                        with self.lock:
                            pending['step'] = 'checking'
                        try:
                            result = self.verify(pending['source'], self.scratch, self.binary, self.bwrap, cancelled)
                        except Exception:
                            result = 'network'
                        with self.lock:
                            pending.update(step='verified' if result == 'ready' else 'failed',
                                           message='' if result == 'ready' else '连接检测未通过，原配置保留')
                with self.lock:
                    pending['step'] = 'expired'
        except Exception:
            with self.lock:
                pending.pop('source', None)
                pending.update(step='failed', candidateEmail='', candidateWorkspace='',
                               message='授权服务暂不可用，请重新获取授权码')
            while not cancelled() and time.time() < pending['expiresAt']:
                time.sleep(.25)
        finally:
            with self.lock, self.store.lock:
                if self.pending is pending:
                    if not pending.get('activated'):
                        state = self.store.load()
                        self.store.audit(state, pending['actor'], '结束授权',
                            '已取消，原配置保留' if pending['cancel'].is_set() else '已超时，原配置保留')
                        self.store.save(state)
                    if pending['cancel'].is_set() or self.stopping.is_set():
                        self.pending = None
                    else:
                        pending.update(step='expired', userCode='', cleanupComplete=True)

    def close(self):
        self.stopping.set()
        for thread in self.threads:
            thread.join(timeout=5)
