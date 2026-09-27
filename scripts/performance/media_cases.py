"""Real HTTP behavior checks. All URLs supplied by disposable localhost mappings."""
import hashlib
from http.client import HTTPConnection
from io import BytesIO
import json
import socket
import time
from urllib.parse import urlsplit
from zipfile import ZipFile

import httpx


def check_protocol(stack, data, outer, inner, api):
    cookie = {'Cookie': 'hx_session=' + data['token']}
    with httpx.Client(timeout=40, trust_env=False) as client:
        for item in (x for x in data['images'] if not x['large']):
            for origin in (outer, inner):
                url = origin + item['path']
                response = client.get(url + '?download=true', headers=cookie)
                assert response.status_code == 200, (response.status_code, response.text[:200])
                assert hashlib.sha256(response.content).hexdigest() == item['sha256']
                assert response.headers['cache-control'] == 'private, no-store', response.headers.get('cache-control')
                assert response.headers['content-type'].startswith('image/png')
                assert 'attachment;' in response.headers['content-disposition']
                assert len(response.headers.get_list('content-disposition')) == 1
                assert '%E5%8E%9F' in response.headers['content-disposition']
                assert 'x-accel-redirect' not in response.headers and 'location' not in response.headers
                etag = response.headers['etag']
                head = client.head(url, headers=cookie)
                assert head.status_code == 200 and not head.content
                assert int(head.headers['content-length']) == item['size']
                partial = client.get(url, headers={**cookie, 'Range': 'bytes=1-5'})
                assert partial.status_code == 206 and partial.content == response.content[1:6]
                unchanged = client.get(url, headers={**cookie, 'If-None-Match': etag})
                assert unchanged.status_code == 304 and not unchanged.content
                invalid = client.get(url, headers={**cookie, 'Range': 'bytes=99999999-'})
                assert invalid.status_code == 416 and '<Error>' not in invalid.text and 'X-Amz-' not in invalid.text
                for method in ('GET', 'HEAD'):
                    anonymous = client.request(method, url, headers={'Range': 'bytes=0-2', 'If-None-Match': etag})
                    assert anonymous.status_code == 401
                    assert anonymous.headers['cache-control'] == 'private, no-store'
                    for identifier, status in [('00000000-0000-4000-8000-000000000099', 404), ('invalid', 422)]:
                        failed = client.request(method, origin + item['path'].replace(item['id'], identifier), headers=cookie)
                        assert failed.status_code == status and failed.headers['cache-control'] == 'private, no-store'
                # False client hand-off headers and alternate query values are ignored.
                spoof = client.get(url + '?object_key=skills/secret&bucket=other', headers={**cookie, 'X-Accel-Redirect': '/__hx_media/other/secret', 'X-Hengxin-Media-Gateway': 'attacker'})
                assert spoof.status_code == 200 and hashlib.sha256(spoof.content).hexdigest() == item['sha256']
                for path in ('/__hx_media/private/secret', '/__hx_media/%2e%2e/private/secret'):
                    assert client.get(origin + path, headers=cookie).status_code == 404
            fallback = client.get(api + item['path'], headers={**cookie, 'X-Hengxin-Media-Gateway': '1'})
            assert fallback.status_code == 200 and 'x-accel-redirect' not in fallback.headers
            assert hashlib.sha256(fallback.content).hexdigest() == item['sha256']
        result = client.get(outer + data['zip'], headers=cookie)
        assert result.status_code == 200
        with ZipFile(BytesIO(result.content)) as archive:
            assert archive.namelist() == ['01.png']
        stack.seed('disable', data['uid'], 'disabled')
        for item in data['images']:
            for method in ('GET', 'HEAD'):
                denied = client.request(method, outer + item['path'], headers={**cookie, 'Range': 'bytes=0-2', 'If-None-Match': '*'})
                assert denied.status_code == 403 and denied.headers['cache-control'] == 'private, no-store'
        stack.seed('disable', data['uid'], 'active')
        large = next(x for x in data['images'] if x['large'] and x['domain'] == 'originals')
        original = client.get(api + large['path'], headers=cookie).content
        assert 1024**2 < len(original) < 10 * 1024**2
        for path in ('/api/v1/files', '/api/v1/api-image-edits/files'):
            uploaded = client.post(outer + path, headers=cookie, files={'file': ('原图.png', original, 'image/png')})
            assert uploaded.status_code == 200, uploaded.text
            saved = client.get(outer + uploaded.json()['url'], headers=cookie)
            assert hashlib.sha256(saved.content).hexdigest() == large['sha256']


def hold(origin, path, cookie, method='GET', body=None):
    parsed = urlsplit(origin)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=45)
    conn.connect()
    # Bound the client receive window: unread bodies must really keep the
    # upstream request active instead of fitting entirely in OS socket buffers.
    conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    conn.request(method, path, body=body, headers={**cookie, 'Content-Type': 'application/json'})
    response = conn.getresponse()
    return conn, response


def check_admission(stack, data, outer, inner):
    cookie = {'Cookie': 'hx_session=' + data['token']}
    image = next(x for x in data['images'] if x['large'] and x['domain'] == 'originals')
    held = []
    with httpx.Client(timeout=45, trust_env=False) as client:
        with stack.slow_images(image['path'], cookie['Cookie']):
            for origin in (inner, outer):
                busy = client.head(origin + image['path'], headers=cookie)
                assert busy.status_code == 429 and busy.headers['retry-after'] == '1', busy.status_code
            assert client.get(outer + '/api/v1/auth/me', headers=cookie).status_code == 200
            assert stack.seed('idle') == '0', 'media stream holds a PostgreSQL transaction'
        time.sleep(1)
        assert client.head(outer + image['path'], headers=cookie).status_code == 200
        held = []
        try:
            for _ in range(2):
                conn, response = hold(outer, data['large_zip'], cookie)
                held.append((conn, response)); assert response.status == 200
            busy = client.post(inner + '/api/v1/files/download-zip', headers=cookie,
                               json={'fileIds': [image['id']], 'name': 'limited'})
            assert busy.status_code == 429
            assert client.get(outer + '/api/v1/auth/me', headers=cookie).status_code == 200
            assert stack.seed('idle') == '0'
        finally:
            for conn, response in held: response.close(); conn.close()
        time.sleep(.5)
        assert client.get(outer + data['zip'], headers=cookie).status_code == 200
        # Incomplete bodies occupy only the gateway's TWO upload slots.
        held_uploads = []
        try:
            for origin in (outer, inner):
                parsed = urlsplit(origin); conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
                conn.putrequest('POST', '/api/v1/files'); conn.putheader('Content-Length', str(8 * 1024 * 1024))
                conn.putheader('Cookie', cookie['Cookie']); conn.endheaders(b'x')
                held_uploads.append(conn)
            time.sleep(.3)
            for origin in (outer, inner):
                busy = client.post(origin + '/api/v1/api-image-edits/files', headers=cookie, content=b'x')
                assert busy.status_code == 429
            assert client.get(outer + '/api/v1/auth/me', headers=cookie).status_code == 200
        finally:
            for conn in held_uploads: conn.close()
        time.sleep(.5)
        assert client.post(inner + '/api/v1/files', headers=cookie, content=b'x').status_code == 422


def check_outage(stack, data, outer):
    path = next(x['path'] for x in data['images'] if x['large'])
    with httpx.Client(timeout=40, trust_env=False) as client:
        stack.run('stop', 'minio')
        response = client.get(outer + path, headers={'Cookie': 'hx_session=' + data['token']})
        assert response.status_code == 503 and 'X-Amz-' not in response.text and '<Error>' not in response.text
    logs = stack.run('logs', '--no-color', 'web', 'outer', 'media-api').stdout
    assert 'X-Amz-Signature' not in logs and 'X-Amz-Credential' not in logs


def check_private_storage(stack, data, outer, api):
    cookie = {'Cookie': 'hx_session=' + data['token']}
    items = [x for x in data['images'] if not x['large']]
    # Direct object URLs must be private even inside the isolated network.
    code = "import urllib.request,urllib.error,sys; " + \
           "r=urllib.request.Request(sys.argv[1]); " + \
           "\ntry: urllib.request.urlopen(r); raise AssertionError('anonymous object read')\n" + \
           "except urllib.error.HTTPError as e: assert e.code == 403\n"
    stack.run('exec', '-T', 'api', 'python', '-c', code,
              f'http://minio:9000/{stack.bucket}/originals/{items[0]["id"]}')
    with httpx.Client(timeout=40, trust_env=False) as client:
        stack.seed('policy', 'public')
        try:
            time.sleep(31)  # Exceed the real bounded policy cache; no mocked clock.
            for item in items:
                assert client.get(outer + item['path'], headers=cookie).status_code == 503
        finally:
            stack.seed('policy', 'private')
        time.sleep(2.1)  # Expire the failure backoff.
        for item in items:
            assert client.get(outer + item['path'], headers=cookie).status_code == 200
            stack.seed('remove', item['domain'], item['id'])
            for origin in (outer, api):
                for method in ('GET', 'HEAD'):
                    response = client.request(method, origin + item['path'], headers=cookie)
                    assert response.status_code == 503
                    assert response.headers['cache-control'] == 'private, no-store', (origin, method, response.headers.get('cache-control'))
                    assert '<Error>' not in response.text and 'X-Amz-' not in response.text
