"""Run with python -m app.execution.credential_broker (Linux host only)."""
import argparse
import errno
import os
import socket
import socketserver
import stat
import struct
import threading
import time
from pathlib import Path

from .credential_broker_client import MAX_REQUEST, MAX_RESPONSE, receive, send, timeout_value
from .managed_credentials import CredentialsError, access_credentials
from .managed_credentials_files import directory

DEFAULT_SOURCE = '/home/codex/auth/auth.json'
DEFAULT_SOCKET = '/run/hengxin-codex-auth/broker.sock'
DEFAULT_UIDS = frozenset({1001, 999})


def peer_uid(connection):
    return struct.unpack('3i', connection.getsockopt(
        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))[1]


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            if peer_uid(self.request) not in self.server.allowed_uids:
                raise CredentialsError()
            value = receive(self.request, MAX_REQUEST, time.monotonic() + 5)
            if set(value) != {'timeout_seconds'}:
                raise ValueError('unsupported credential request')
            timeout = timeout_value(value['timeout_seconds'])
            result = {'auth': access_credentials(self.server.source, timeout)}
        except CredentialsError as error:
            result = {'error': error.code}
        except Exception:
            result = {'error': 'credentials_invalid'}
        try:
            send(self.request, result, MAX_RESPONSE, time.monotonic() + 5)
        except Exception:
            pass  # Disconnected peers never cause tracebacks containing credentials.


class BrokerServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = True
    request_queue_size = 16

    def __init__(self, path, source, allowed_uids=DEFAULT_UIDS, max_clients=16):
        self.source = Path(source)
        self.allowed_uids = frozenset(allowed_uids)
        if (not self.allowed_uids or not 1 <= max_clients <= 64
                or any(isinstance(uid, bool) or not isinstance(uid, int) or uid < 0
                       for uid in self.allowed_uids)):
            raise ValueError('invalid broker limits')
        self.slots = threading.BoundedSemaphore(max_clients)
        self.path = Path(path)
        self.socket_identity = None
        with directory(self.path.parent) as folder:
            info = os.fstat(folder.fd)
            if info.st_uid != os.geteuid() or info.st_mode & 0o027:
                raise ValueError('unsafe broker directory')
            self._remove_stale()
            super().__init__(str(self.path), Handler)
            os.chmod(self.path, 0o660)
            info = self.path.lstat()
            self.socket_identity = info.st_dev, info.st_ino

    def _remove_stale(self):
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('unsafe broker socket')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(1)
            try:
                probe.connect(str(self.path))
            except OSError as error:
                if error.errno != errno.ECONNREFUSED:
                    raise ValueError('cannot replace broker socket') from None
            else:
                raise ValueError('broker already running')
        self.path.unlink()

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # No exception objects or credential-bearing buffers in logs.

    def server_close(self):
        super().server_close()
        try:
            info = self.path.lstat()
            if self.socket_identity == (info.st_dev, info.st_ino):
                self.path.unlink()
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser(description='Local Codex access credential broker')
    parser.add_argument('--source', default=DEFAULT_SOURCE)
    parser.add_argument('--socket', default=DEFAULT_SOCKET)
    parser.add_argument('--allowed-uid', type=int, action='append')
    args = parser.parse_args()
    with BrokerServer(args.socket, args.source, args.allowed_uid or DEFAULT_UIDS) as server:
        server.serve_forever(poll_interval=0.2)


if __name__ == '__main__':
    main()
