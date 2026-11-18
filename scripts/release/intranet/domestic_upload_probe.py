"""Check both domestic upload ingress paths on the real LAN listener, without credentials."""
import json
import subprocess
import time


SIZE = 10_714_198
BASE = 'http://192.168.1.245:8080'
EMPTY_ID = '00000000-0000-4000-8000-000000000000'
PREFIX = '/api/v1/domestic-studio/'
ROUTES = {
    'task': PREFIX + f'tasks/{EMPTY_ID}/studio/files?conversationId={EMPTY_ID}',
    'workspace': PREFIX + f'workspaces/cable/files?conversationId={EMPTY_ID}',
    'control': PREFIX + 'upload-limit-probe',
}
BOUNDARY = 'hengxin-domestic-upload-probe'


def multipart(size):
    header = (f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="probe.bin"\r\n'
              'Content-Type: application/octet-stream\r\n\r\n').encode()
    end = f'\r\n--{BOUNDARY}--\r\n'.encode()
    return header + bytes(size - len(header) - len(end)) + end


def post(route, body):
    # -q disables local curl config, including any ambient credentials or redirects.
    result = subprocess.run([
        'curl', '-q', '--silent', '--show-error', '--noproxy', '*', '--max-time', '30',
        '-H', 'X-HX-Request: 1', '-H', f'Content-Type: multipart/form-data; boundary={BOUNDARY}',
        '--data-binary', '@-', '--write-out', '\n%{http_code} %{content_type}', BASE + route,
    ], input=body, capture_output=True, timeout=35, check=True)
    payload, _, metadata = result.stdout.rpartition(b'\n')
    status, _, content_type = metadata.partition(b' ')
    code = int(status)
    if code in (401, 403):
        if (content_type.split(b';')[0] != b'application/json'
                or not isinstance(json.loads(payload).get('message'), str)):
            raise RuntimeError('Expected application authentication response on domestic upload route')
    return code


def verify_probes(enabled):
    small, large = multipart(512), multipart(SIZE)
    tiny = {name: post(ROUTES[name], small) for name in ('task', 'workspace')}
    if any(status not in (401, 403) for status in tiny.values()):
        raise RuntimeError(f'Domestic upload authentication baseline differs: {tiny}')
    expected = dict(tiny if enabled else dict.fromkeys(tiny, 413), control=413)
    # A successful nginx signal returns before the new workers start accepting connections.
    deadline = time.monotonic() + 10
    while True:
        actual = {name: post(route, large) for name, route in ROUTES.items()}
        if actual == expected:
            return {'small': tiny, 'request_bytes': SIZE, 'status': actual}
        if time.monotonic() >= deadline:
            raise RuntimeError(f'Domestic upload gateway probes differ: expected {expected}, got {actual}')
        time.sleep(.4)
