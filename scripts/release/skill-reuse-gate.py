"""Close only overseas routes in both existing proxies; never restart API."""
import json
import os
from pathlib import Path
import re
import time

r = None  # Injected by skill-reuse-runtime.helper.
PROXIES = {'edge':('/opt/1panel/www/conf.d/zhitu.qhhengxin.top.conf','1Panel-openresty-w177'),
           'web':('/opt/hengxin-smart-image/infra/nginx.vps.conf','hengxin-vps-staging-web-1')}


def closed_config(original):
    changed, count = re.subn(r'location \^~ /api/overseas/v1/ \{[^{}]*\}',
        'location ^~ /api/overseas/v1/ { return 503; }',original)
    r.require(count == 1 and changed != original, 'Overseas location missing, ambiguous or already closed')
    return changed


def remaining(deadline):
    value = deadline-time.monotonic()
    r.require(value > 0, 'Proxy drain deadline; keep intake closed, do not stop native')
    return min(5,value)


def workers(container, deadline):
    rows = r.run('docker','top',container,'-eo','pid,args',timeout=remaining(deadline)).splitlines()[1:]
    return {line.split()[0] for line in rows if 'nginx: worker process' in line}


def save(work):
    result = {}
    for key,(name,container) in PROXIES.items():
        path = Path(name)
        r.helper('sku-native').safe(path)
        raw = path.read_text()
        closed_config(raw)
        r.private(work/(key+'-before.conf'),raw)
        live = json.loads(r.run('docker','inspect',container))[0]
        r.require(live['State']['Running'], 'Proxy not running')
        result[key] = dict(path=name,container=container,id=live['Id'],sha256=r.digest(path))
    return result


def guard(work,data):
    for key,saved in data['proxies'].items():
        original = (work/(key+'-before.conf')).read_text()
        r.require(r.digest(work/(key+'-before.conf')) == saved['sha256'], 'Proxy backup drift')
        r.require(Path(saved['path']).read_text() in (original,closed_config(original)), 'Proxy config drift')
        live = json.loads(r.run('docker','inspect',saved['container']))[0]
        r.require(live['Id'] == saved['id'] and live['State']['Running'], 'Proxy identity drift')


def wait_http(expected,deadline):
    while True:
        matched = True
        for origin in ('http://127.0.0.1:18080','https://zhitu.qhhengxin.top'):
            budget = remaining(deadline)
            code = r.run('curl','--max-time',str(budget),'-sS','-o','/dev/null','-w','%{http_code}',
                origin+'/api/overseas/v1/health/ready',timeout=budget)
            matched = matched and code == expected
        if matched:
            remaining(deadline)
            return
        time.sleep(min(.5,remaining(deadline)))


def set_gate(work,data,closed):
    guard(work,data)
    # Nginx keeps requests on old workers alive after reload; they must finish before native drain.
    deadline = time.monotonic()+360
    marker = work/'PROXY_DRAIN.json'
    old_workers = {key:workers(saved['id'],deadline) for key,saved in data['proxies'].items()}
    if closed and marker.exists():
        prior = json.loads(marker.read_text())
        r.require(prior['manifest'] == data['manifest'], 'Proxy drain proof drift')
        # Keep interrupted old workers and capture new workers after a previous successful reopen.
        old_workers = {k:v | set(prior['workers'][k]) for k,v in old_workers.items()}
    if closed:
        r.private(marker,dict(manifest=data['manifest'],workers={k:sorted(v) for k,v in old_workers.items()}))
    for key,saved in data['proxies'].items():
        path = Path(saved['path'])
        original = (work/(key+'-before.conf')).read_text()
        # Preserve the bind-mounted inode; atomic replacement would leave inner nginx on old bytes.
        with path.open('w') as stream:
            stream.write(closed_config(original) if closed else original)
            stream.flush()
            os.fsync(stream.fileno())
        r.run('docker','exec',saved['id'],'nginx','-t',timeout=remaining(deadline))
        r.run('docker','exec',saved['id'],'nginx','-s','reload',timeout=remaining(deadline))
    wait_http('503' if closed else '200',deadline)
    if closed:
        while any(old_workers[key] & workers(saved['id'],deadline) for key,saved in data['proxies'].items()):
            time.sleep(min(.5,remaining(deadline)))
        r.private(work/'INTAKE_CLOSED',dict(manifest=data['manifest']))
    else:
        for key,saved in data['proxies'].items():
            r.require(r.digest(saved['path']) == saved['sha256'], 'Proxy restoration differs')


def require_closed(work,data):
    guard(work,data)
    r.require(json.loads((work/'INTAKE_CLOSED').read_text()) == {'manifest':data['manifest']}, 'No closed intake proof')
    for key,saved in data['proxies'].items():
        r.require(Path(saved['path']).read_text() == closed_config((work/(key+'-before.conf')).read_text()),
                  'Intake no longer closed')
    wait_http('503',time.monotonic()+20)
