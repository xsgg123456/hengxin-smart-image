"""Patch only the overseas location on both existing proxy hops; retain backups."""
import re

LOCATION = r'location \^~ /api/overseas/v1/ \{[^{}]*\}'
DIRECTIVES = {
    'client_max_body_size': '500065536', 'client_body_timeout': '300s',
    'proxy_send_timeout': '300s', 'proxy_read_timeout': '300s',
    'proxy_http_version': '1.1', 'proxy_request_buffering': 'off',
}


def patch(original, directives):
    assert directives == DIRECTIVES, 'Upload directive drift'
    matches = list(re.finditer(LOCATION, original))
    assert len(matches) == 1, 'Exactly one overseas proxy location required'
    match = matches[0]
    body = match.group()
    assert re.search(r'\bproxy_pass\s+http://[^;]+;', body), 'Existing upstream required'
    for name in directives:
        body = re.sub(r'\b' + name + r'\s+[^;{}]+;', '', body)
    body = body[:-1].rstrip() + '\n' + ''.join(
        f'        {name} {value};\n' for name, value in directives.items()) + '    }'
    return original[:match.start()] + body + original[match.end():]


def inner(m):
    return m.APP / 'infra/nginx.vps.conf'


def prepare(work, source, m):
    raw = (source / 'infra/nginx.overseas-upload.inc').read_text()
    directives = dict(re.findall(r'^(\w+)\s+([^;]+);$', raw, re.M))
    for label, path in (('edge', m.EDGE), ('inner', inner(m))):
        before = path.read_text()
        m.private(work / f'upload-{label}-before.conf', before)
        m.private(work / f'upload-{label}-after.conf', patch(before, directives))


def unchanged(work, m):
    for label, path in (('edge', m.EDGE), ('inner', inner(m))):
        assert path.read_text() == (work / f'upload-{label}-before.conf').read_text(), 'Proxy drift'


def install_inner(work, destination, m):
    assert (destination / 'COMPLETE').exists(), 'Verified backup required'
    before = (work / 'upload-inner-before.conf').read_text()
    assert inner(m).read_text() == before, 'Inner proxy drift'
    m.private(destination / 'upload-inner.conf', before)
    inner(m).write_text((work / 'upload-inner-after.conf').read_text())
    m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-t')


def restore_inner(work, m):
    # Only restore if this release actually installed its exact expected contents.
    if inner(m).read_text() == (work / 'upload-inner-after.conf').read_text():
        inner(m).write_text((work / 'upload-inner-before.conf').read_text())
        m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-t')
        m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-s', 'reload')


def verify(work, m, checks):
    for label, path in (('edge', m.EDGE), ('inner', inner(m))):
        assert path.read_text() == (work / f'upload-{label}-after.conf').read_text()
    # Header-only requests: auth rejects admitted bodies; never create business files.
    for origin in (m.r.ORIGIN, 'http://127.0.0.1:18080'):
        for size, expected in ((500000000, ('401', '403')), (500065537, ('413',))):
            code = m.run('curl', '--max-time', '20', '-sS', '-o', '/dev/null', '-w', '%{http_code}',
                         '-X', 'POST', '-H', f'Content-Length: {size}',
                         '-H', 'Content-Type: multipart/form-data; boundary=probe',
                         origin + '/api/overseas/v1/materials?kind=requirement', capture=True)
            assert code in expected, f'Upload proxy boundary failed: {code}'
    m.private(work / 'UPLOAD_PROXY_VERIFIED', 'Both proxy configs and public/inner admission boundaries PASS')
