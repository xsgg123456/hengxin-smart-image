"""Close only domestic paths at both reverse proxies, including regex SSE routes."""
import importlib.util
from pathlib import Path
import re
import subprocess
import time

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BLOCK = '    location ^~ /api/v1/ { return 503; }\n'
PATHS = ('/api/v1/health/ready',
         '/api/v1/api-image-edits/tasks/probe/items/probe/conversation/events')


def closed_config(original, edge=False):
    pattern = r'(?m)^[ \t]*location \^~ /api/v1/ \{[^{}]*\}\n?'
    if re.search(pattern, original):
        changed, count = re.subn(pattern, BLOCK, original)
        assert count == 1, 'Domestic location ambiguous'
        return changed
    anchor = '    ssl_prefer_server_ciphers off;\n' if edge else '    location /api/ {'
    assert original.count(anchor) == 1, 'Proxy insertion point ambiguous'
    return original.replace(anchor, anchor + '\n' + BLOCK if edge else BLOCK + '\n' + anchor, 1)


def reload_all():
    m.u.reload_edge()
    m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-t')
    m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-s', 'reload')


def save(work):
    m.private(work / 'edge-before.conf', m.EDGE.read_text())
    m.private(work / 'web-before.conf', (m.APP / 'infra/nginx.vps.conf').read_text())
    # Fail before touching either live file if one cannot be transformed safely.
    closed_config((work / 'edge-before.conf').read_text(), edge=True)
    closed_config((work / 'web-before.conf').read_text())


def close(work):
    m.EDGE.write_text(closed_config((work / 'edge-before.conf').read_text(), edge=True))
    (m.APP / 'infra/nginx.vps.conf').write_text(closed_config((work / 'web-before.conf').read_text()))
    reload_all()
    verify_closed()


def wait_routes(paths, expected, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        matched = True
        for path in paths:
            for origin, options in (
                ('http://127.0.0.1:18080', ()),
                (m.r.ORIGIN, ('--resolve', 'zhitu.qhhengxin.top:443:127.0.0.1')),
                (m.r.ORIGIN, ()),
            ):
                remaining = deadline - time.monotonic()
                assert remaining > 0, 'Domestic intake did not reach HTTP ' + expected
                limit = min(5, remaining)
                try:
                    code = m.run('curl', '--max-time', str(limit), '-sS', '-o', '/dev/null',
                                 '-w', '%{http_code}', *options, origin + path,
                                 capture=True, timeout=limit)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    code = ''
                matched = matched and code == expected
        assert time.monotonic() < deadline, 'Domestic intake did not reach HTTP ' + expected
        if matched:
            return
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def verify_closed(timeout=30):
    wait_routes(PATHS, '503', timeout)


def open_intake(work):
    m.EDGE.write_text((work / 'edge-before.conf').read_text())
    (m.APP / 'infra/nginx.vps.conf').write_text((work / 'web-before.conf').read_text())
    reload_all()
    wait_routes(PATHS[:1], '200')
