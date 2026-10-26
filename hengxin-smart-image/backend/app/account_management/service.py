"""Host service: access-only worker socket and separate per-business control sockets."""
import argparse
from contextlib import ExitStack
import fcntl
import os
from pathlib import Path
import signal
import socketserver
import threading
import time
from uuid import UUID

from app.execution.credential_broker import BrokerServer, peer_uid
from app.execution.credential_broker_client import receive, send
from app.execution.managed_credentials import access_credentials, CredentialsError
from app.execution.managed_credentials_files import directory
from .manager import AccountManager
from .store import AccountError, AccountStore

FIELDS = {'status': set(), 'check': set(), 'start': {'intent', 'revision'},
          'poll': {'id'}, 'retry': {'id'}, 'activate': {'id', 'acknowledged'},
          'cancel': {'id'}, 'remove': {'revision'}}


def dispatch(manager, request):
    action = request.get('action')
    if not isinstance(action, str) or action not in FIELDS or set(request) != {'action', 'actor'} | FIELDS[action]:
        raise AccountError(400, '无效的账号管理请求')
    actor = request['actor']
    if (not isinstance(actor, dict) or set(actor) != {'id', 'name'}
            or not isinstance(actor['id'], str) or not isinstance(actor['name'], str)
            or not 1 <= len(actor['name']) <= 120):
        raise AccountError(400, '无效的操作者身份')
    try:
        UUID(actor['id'])
        if 'id' in request:
            UUID(request['id'])
    except (ValueError, TypeError, AttributeError):
        raise AccountError(400, '无效的授权流程标识') from None
    if 'revision' in request and (type(request['revision']) is not int or request['revision'] < 0):
        raise AccountError(400, '无效的配置版本')
    if 'acknowledged' in request and type(request['acknowledged']) is not bool:
        raise AccountError(400, '无效的确认信息')
    if action == 'status':
        return manager.status()
    if action == 'check':
        return manager.check(actor)
    if action == 'start':
        return manager.start(actor, request['intent'], request['revision'])
    if action == 'remove':
        return manager.remove(actor, request['revision'])
    if action == 'activate':
        return manager.activate(actor, request['id'], request['acknowledged'])
    return getattr(manager, action)(actor, request['id'])


class ControlHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            if peer_uid(self.request) not in self.server.allowed_uids:
                raise AccountError(403, '管理连接无权访问')
            request = receive(self.request, 16384, time.monotonic() + 5)
            response = {'data': dispatch(self.server.manager, request)}
        except AccountError as error:
            response = {'error': {'status': error.status, 'message': error.message}}
        except Exception:
            response = {'error': {'status': 503, 'message': '账号管理服务暂不可用，请稍后重试'}}
        try:
            send(self.request, response, 131072, time.monotonic() + 5)
        except Exception:
            pass


class ControlServer(BrokerServer):
    def __init__(self, path, manager, uid):
        self.manager = manager
        super().__init__(path, manager.store.legacy, {uid}, max_clients=8)
        self.RequestHandlerClass = ControlHandler


class BusinessBroker(BrokerServer):
    def __init__(self, path, managers, domestic_uid=1001, overseas_uid=999):
        if domestic_uid == overseas_uid:
            raise ValueError('business worker UIDs must differ')
        self.managers = {domestic_uid: managers['domestic'], overseas_uid: managers['overseas']}
        super().__init__(path, managers['domestic'].store.legacy, self.managers)

    def credentials(self, uid, timeout):
        try:
            store = self.managers[uid].store
            with store.lock:
                source = store.source()
            return access_credentials(source, timeout)
        except AccountError:
            raise CredentialsError() from None


def secure_dir(path, mode):
    with directory(path, create=True) as folder:
        info = os.fstat(folder.fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError('unsafe service directory')
        os.fchmod(folder.fd, mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--legacy-source', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--bwrap', default='/opt/hengxin-runtime/bwrap')
    parser.add_argument('--api-uid', type=int, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    secure_dir(args.root, 0o700)
    secure_dir(args.runtime, 0o750)
    with directory(args.root) as folder:
        lock = folder.open('service.lock', os.O_CREAT | os.O_RDWR)
    with os.fdopen(lock, 'wb'), ExitStack() as stack:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        managers, servers = {}, []
        for side in ('domestic', 'overseas'):
            secure_dir(args.runtime / side, 0o750)
            manager = AccountManager(AccountStore(args.root / side, args.legacy_source), args.binary, args.bwrap)
            managers[side] = manager
            stack.callback(manager.close)
            servers.append(stack.enter_context(ControlServer(args.runtime / side / 'control.sock', manager, args.api_uid)))
        servers.append(stack.enter_context(BusinessBroker(args.runtime / 'worker.sock', managers)))
        stopped = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *ignored: stopped.set())
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        stopped.wait()
        for manager in managers.values():
            manager.stopping.set()
        for server in servers:
            server.shutdown()


if __name__ == '__main__':
    main()
