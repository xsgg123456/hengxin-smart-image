"""Domestic gateway rendering and opt-in real Nginx multipart regression.

Set HX_TEST_NGINX to an nginx executable for the 500 MB loopback transfer.
HX_TEST_GATEWAY may point at a copy of the actual LAN gateway baseline.
"""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from threading import Thread
import time
import unittest

from domestic_upload_routes import render


LIMIT = 500_000_000 + 65_536
EXAMPLE = round(10.22 * 1024 * 1024)
TASK = '/api/v1/domestic-studio/tasks/t-1/studio/files'
WORKSPACE = '/api/v1/domestic-studio/workspaces/w-1/files'
GATEWAY = b'''server {
    listen 80;
    client_max_body_size 10m;
    location /api/ {
        set $upstream http://domestic-api:8000;
        proxy_pass $upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        proxy_read_timeout 75s;
    }
}
'''


class RenderTests(unittest.TestCase):
    def test_only_one_location_added(self):
        before, common = GATEWAY.split(b'    location /api/ {')
        content = render(GATEWAY)
        self.assertTrue(content.startswith(before))
        self.assertTrue(content.endswith(b'    location /api/ {' + common))
        added = content[len(before):content.index(b'    location /api/ {')]
        self.assertEqual(added.count(b'location '), 1)
        self.assertIn(b'client_max_body_size 500065536;', added)
        self.assertIn(b'proxy_request_buffering off;', added)
        self.assertIn(b'set $upstream http://domestic-api:8000;', added)
        for line in common.splitlines():
            if b'proxy_set_header' in line:
                self.assertIn(line, added)

    def test_rejects_unexpected_base_or_reapplication(self):
        for changed in (render(GATEWAY), GATEWAY * 2, GATEWAY.replace(b'10m;', b'20m;'),
                        GATEWAY.replace(b'domestic-api:', b'another-api:')):
            with self.subTest(config=changed), self.assertRaises((RuntimeError, ValueError)):
                render(changed)


class CountingUpstream(BaseHTTPRequestHandler):
    def do_POST(self):
        remaining = int(self.headers['Content-Length'])
        received = 0
        while remaining:
            block = self.rfile.read(min(remaining, 1024 * 1024))
            if not block:
                break
            received += len(block)
            remaining -= len(block)
        payload = json.dumps({'received': received, 'path': self.path,
                              'proto': self.headers.get('X-Forwarded-Proto')}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


@contextmanager
def local_gateway(config, upstream_port):
    with socket.socket() as addr:
        addr.bind(('127.0.0.1', 0))
        port = addr.getsockname()[1]
    # Only point the domestic upstream and test listener at local sockets.
    server = config.replace(b'listen 80;', f'listen 127.0.0.1:{port};'.encode())
    server = server.replace(b'http://domestic-api:8000', f'http://127.0.0.1:{upstream_port}'.encode())
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, 'nginx.conf').write_bytes(
            b'daemon off; master_process off; error_log stderr warn; pid nginx.pid;\n'
            b'events {}\nhttp { access_log off; client_body_temp_path body; proxy_temp_path proxy; '
            b'fastcgi_temp_path fastcgi; uwsgi_temp_path uwsgi; scgi_temp_path scgi;\n' + server + b'}\n')
        args = [os.environ['HX_TEST_NGINX'], '-e', 'stderr', '-p', folder, '-c', 'nginx.conf']
        subprocess.run([*args, '-t'], check=True, capture_output=True)
        with subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
            try:
                deadline = time.monotonic() + 10
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(process.stderr.read().decode())
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.5):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.05)
                yield port
            finally:
                process.terminate()
                process.wait(timeout=10)


def multipart(port, path, size, *, overhead=None, headers_only=False):
    end = b'\r\n--hx--\r\n'
    start = (b'--hx\r\nContent-Disposition: form-data; name="file"; filename="test.zip"\r\n'
             b'Content-Type: application/zip\r\nX-Test-Padding: ')
    if overhead:
        start += b'x' * (overhead - len(start) - len(end) - len(b'\r\n\r\n'))
    start += b'\r\n\r\n'
    client = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
    try:
        client.putrequest('POST', path)
        client.putheader('Content-Length', str(size))
        client.putheader('Content-Type', 'multipart/form-data; boundary=hx')
        client.putheader('X-Forwarded-Proto', 'https')
        client.endheaders()
        if not headers_only:
            client.send(start)
            remaining = size - len(start) - len(end)
            block = bytes(1024 * 1024)
            while remaining:
                chunk = block[:remaining]
                client.send(chunk)
                remaining -= len(chunk)
            client.send(end)
        response = client.getresponse()
        body = response.read()
        return response.status, json.loads(body) if response.status == 200 else None
    finally:
        client.close()


@unittest.skipUnless(os.environ.get('HX_TEST_NGINX'), 'set HX_TEST_NGINX for isolated real Nginx')
class NginxTests(unittest.TestCase):
    def test_upload_boundaries_and_neighboring_routes(self):
        baseline = Path(os.environ['HX_TEST_GATEWAY']).read_bytes() if 'HX_TEST_GATEWAY' in os.environ else GATEWAY
        with ThreadingHTTPServer(('127.0.0.1', 0), CountingUpstream) as upstream:
            thread = Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            try:
                with local_gateway(baseline, upstream.server_port) as port:
                    for route in (TASK, WORKSPACE):
                        self.assertEqual(multipart(port, route, EXAMPLE, headers_only=True), (413, None))
                with local_gateway(render(baseline), upstream.server_port) as port:
                    for route, size in ((TASK, EXAMPLE), (WORKSPACE + '/?test=1', EXAMPLE),
                                        (TASK, LIMIT), (WORKSPACE, LIMIT)):
                        with self.subTest(route=route, size=size):
                            overhead = 65536 if size == LIMIT else None
                            self.assertEqual(multipart(port, route, size, overhead=overhead),
                                             (200, {'received': size, 'path': route, 'proto': 'https'}))
                    for route in (TASK, WORKSPACE):
                        self.assertEqual(multipart(port, route, LIMIT + 1, headers_only=True), (413, None))
                    for route in (TASK + '/download', WORKSPACE + '/other', TASK.replace('/studio/', '/'),
                                  '/api/v1/health/ready', '/api/identity/v1/anything'):
                        self.assertEqual(multipart(port, route, EXAMPLE, headers_only=True), (413, None))
            finally:
                upstream.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main()
