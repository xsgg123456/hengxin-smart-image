"""Pinned 0.2.34 -> 0.2.35 studio hotfix; no migration or business deletion.

Reuse the tested upload cutover, preserving its installed 3 GiB / 500 MB settings
and the effective 99 native pointer. Failure requires inspected recovery, not replay.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('attachment_cutover', Path(__file__).with_name('overseas-upload-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
d.TARGET_VERSION, d.BASE_VERSION = '0.2.35', '0.2.34'
d.RELEASE_PATTERN = r'overseas-20261015-[0-9a-f]{7}'
d.u.DROP = '99-overseas-upload.conf'
SYSTEMD = Path('/etc/systemd/system')


def native_pointer(target, unit):
    command = (str(target / '.venv/bin/celery') + ' -A app.overseas.execution.worker:celery_app worker '
               '--pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
               if unit.endswith('worker') else str(target / '.venv/bin/python') + ' -m app.overseas.execution.outbox')
    return '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + command + '\n'


def proxy_baseline(body):
    matches = list(re.finditer(d.proxy.LOCATION, body))
    assert len(matches) == 1, 'Exactly one overseas proxy location required'
    location = matches[0].group()
    assert re.search(r'\bproxy_pass\s+http://[^;]+;', location), 'Existing upstream required'
    for key, value in d.proxy.DIRECTIVES.items():
        assert re.findall(r'\b' + key + r'\s+([^;{}]+);', location) == [value], 'Proxy baseline drift: ' + key


def preflight():
    assert json.loads((d.m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    assert json.loads((d.m.APP / 'OVERSEAS_RELEASE.json').read_text())['release'] == 'overseas-20261014-3b09fbc', 'Overseas release baseline drift'
    live = d.m.live(d.u.API)
    assert live['State']['Running'] and live['State']['Health']['Status'] == 'healthy'
    assert live['HostConfig']['Memory'] == d.resources.API_MEMORY, 'API memory baseline drift'
    for unit in d.u.UNITS:
        target = Path(d.m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True))
        folder = SYSTEMD / (unit + '.service.d')
        pointer = folder / d.u.DROP
        assert pointer.read_text() == native_pointer(target, unit), 'Native pointer baseline drift'
        # Include vendor/runtime drop-ins, not just files under /etc.
        effective = d.m.run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value', capture=True).split()
        assert str(pointer) in effective, 'Native pointer is not loaded'
        assert all(Path(path).name <= d.u.DROP for path in effective), 'Higher priority native override'
        assert all(path.name <= d.u.DROP for path in folder.glob('*.conf')), 'Unloaded native override'
    for path in (d.m.EDGE, d.proxy.inner(d.m)):
        proxy_baseline(path.read_text())


def prepare_proxy(work, source, m):
    directives = dict(re.findall(r'^(\w+)\s+([^;]+);$', (source / 'infra/nginx.overseas-upload.inc').read_text(), re.M))
    assert directives == d.proxy.DIRECTIVES, 'Packaged upload directive drift'
    for label, path in (('edge', m.EDGE), ('inner', d.proxy.inner(m))):
        before = path.read_text()
        proxy_baseline(before)
        # Preserve exact existing bytes; this release changes no proxy setting.
        for stage in ('before', 'after'):
            m.private(work / f'upload-{label}-{stage}.conf', before)


d.preflight = preflight
d.proxy.prepare = prepare_proxy
main = d.main


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
