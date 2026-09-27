"""Real PostgreSQL/MinIO/two-proxy display and private revalidation checks."""
import hashlib

import httpx


def check_variants(stack, data, outer, inner):
    headers = {'Cookie': 'hx_session=' + data['token']}
    results = []
    with httpx.Client(trust_env=False, timeout=40) as client:
        for item in (row for row in data['images'] if row['large']):
            path = item['path'] + '?variant=256'
            original = client.get(outer + path, headers=headers)
            assert original.status_code == 200, original.text[:100]
            assert hashlib.sha256(original.content).hexdigest() == item['sha256']
            # Protocol checks also uploaded originals: drain that finite fixture backlog.
            for _ in range(6):
                processed = stack.run('exec', '-T', 'api', 'python', '-m',
                    'app.modules.files.variant_worker', '--once')
            for origin in (outer, inner):
                response = client.get(origin + path, headers=headers)
                assert response.status_code == 200 and len(response.content) < item['size'] / 10, (response.status_code, len(response.content), processed.stdout, processed.stderr)
                assert response.headers['cache-control'] == 'private, no-cache'
                assert response.headers['content-type'].startswith('image/webp')
                assert 'cookie' in response.headers['vary'].lower()
                tag = {'If-None-Match': response.headers['etag']}
                hit = client.get(origin + path, headers={**headers, **tag})
                assert hit.status_code == 304 and not hit.content
                denied = client.get(origin + path, headers=tag)
                assert denied.status_code == 401 and denied.headers['cache-control'] == 'private, no-store'
                full = client.get(origin + item['path'] + '?download=true', headers=headers)
                assert hashlib.sha256(full.content).hexdigest() == item['sha256']
            stack.seed('disable', data['uid'], 'disabled')
            assert client.get(outer + path, headers={**headers, **tag}).status_code == 403
            stack.seed('disable', data['uid'], 'active')
            results.append({'domain': item['domain'], 'original': item['size'], 'display': len(response.content),
                            'revalidation_status': hit.status_code, 'revalidation_bytes': len(hit.content)})
    return results
