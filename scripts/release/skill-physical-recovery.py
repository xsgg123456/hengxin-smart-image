"""Admission resume and pre-maintenance recovery; never rewind history."""
import hashlib
import json
import time
import urllib.request


def resume(d, work):
    r, p = d.r, d.p
    d.verify(work)
    data, source = d.state(work, tested=True, release=True)
    refs = ['index.html', *r.helper('archive-runtime').entry_refs((source/'frontend/dist/index.html').read_text())]
    deadline = time.monotonic()+45
    for ref in refs:
        budget = deadline-time.monotonic()
        r.require(budget > 0, 'Public static verification deadline')
        request = urllib.request.Request('https://zhitu.qhhengxin.top/'+ref,
            headers={'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=min(10, budget)) as response:
            r.require(response.status == 200 and hashlib.sha256(response.read()).hexdigest() ==
                      r.digest(source/'frontend/dist'/ref), 'Public static bytes differ')
    r.helper('skill-physical-maintenance').resume(work, data)
    r.helper('skill-reuse-gate').set_gate(work, data, False)
    r.helper('skill-folders-gateway').readiness(r)
    r.private(work/'RESUMED', {'manifest': data['manifest'], 'images': data['images']})
    return 'RELEASE_RESUMED_REQUIRES_BROWSER_VISUAL_ACCEPTANCE_GC_SEPARATE'


def recover(d, work):
    r, p = d.r, d.p
    r.require(not (work/'MAINTENANCE_STARTED').exists(),
              'Maintenance may have installed schema 2: keep new services and repair forward; never restore old readers')
    data, _ = d.state(work, tested=True, release=True)
    r.require(not (work/'RESUMED').exists(), 'Public release resumed: take fresh preservation baseline before recovery')
    if not (work/'GATE_STARTED').exists():
        api, publisher = r.inspect(), d.inspect(p.PUBLISHER)
        r.require(api['Id'] == data['oldId'] and publisher['Id'] == data['oldPublisher']['id'] and
                  api['State']['Running'] and publisher['State']['Running'],
                  'Ungated baseline changed')
        return 'UNGATED_RELEASE_CANCELLED'
    r.helper('skill-reuse-gate').set_gate(work, data, True)
    d.stop_container(r.API)
    d.stop_container(p.PUBLISHER)
    if not (work/'gate.json').exists():
        r.private(work/'gate.json', dict(node=json.loads((work/'GATE_STARTED').read_text())['node'],
            manifest=data['manifest'], phase='api-stopped-consumer-paused'))
    if (work/'NATIVE_PATCH_STARTED').exists() or (work/'NATIVE_RECOVERY.json').exists():
        r.helper('skill-physical-native').restore(work, data)
    elif (work/'NATIVE_STOP_STARTED').exists():
        r.helper('sku-native').start(work, data, recovery=True)
    else:
        r.worker('resume', json.loads((work/'gate.json').read_text())['node'])
    if (work/'frontend-backup/COMPLETE.json').exists():
        r.helper('sku-frontend').rollback(r.a.APP, work/'frontend-backup')
    # Original full compose chain retains the exact prior API/publisher images and mounts.
    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'skill-publisher', 'api')
    before = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json'))
    d.check_service(r.inspect(), before, 'api')
    d.check_service(d.inspect(p.PUBLISHER), before, 'skill-publisher')
    r.helper('skill-reuse-native').verify_baseline(data)
    preserve = work/'recovery-preserve' if (work/'recovery-preserve/CONVERSATION_BASELINE').exists() else work
    if (preserve/'CONVERSATION_BASELINE').exists():
        r.helper('skill-reuse-preserve').verify(preserve, data)
    r.run('docker', 'exec', data['proxies']['web']['id'], 'nginx', '-t')
    r.run('docker', 'exec', data['proxies']['web']['id'], 'nginx', '-s', 'reload')
    r.helper('skill-reuse-gate').set_gate(work, data, False)
    r.helper('skill-folders-gateway').readiness(r)
    r.private(work/'RECOVERED', {'manifest': data['manifest']})
    return 'BASELINE_RESTORED_NO_DATABASE_OR_HISTORY_REWIND'


def verify(d, work):
    r, p = d.r, d.p
    data, source = d.state(work, tested=True, release=True)
    r.helper('skill-reuse-gate').require_closed(work, data)
    config = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=work/'api-overlay.json'))
    for name, service in ((r.API, 'api'), (p.PUBLISHER, 'skill-publisher')):
        live = d.inspect(name)
        r.require(live['State']['Running'], 'New service not running')
        d.check_service(live, config, service)
    r.require(r.environment_hash(r.inspect()['Config']['Env']) == data['environment']['api'], 'API business environment drift')
    r.helper('sku-native').verified(work, data)
    d.publisher_ready(data)
    r.helper('skill-physical-maintenance').verify_history(work, data)
    for name, value in r.verify_package(source)['files'].items():
        if name.startswith('frontend/'):
            r.require(r.digest(r.a.APP/name) == value, 'Installed frontend bytes drift')
    for port, route in ((18018, '/api/overseas/v1/health/ready'), (18080, '/api/v1/health/ready')):
        r.helper('image-cache-runtime').readiness('http://127.0.0.1:'+str(port)+route)
    code = ('import os,pathlib; assert os.geteuid()==10001; p=pathlib.Path('+repr(p.SKILL_ROOT)+'); '
            'assert not os.access(p,os.W_OK); from app.overseas.management.installed_catalog import catalog; '
            'catalog(); print("READ_ONLY_CATALOG_OK")')
    r.require(r.run('docker', 'exec', r.API, 'python', '-B', '-c', code) == 'READ_ONLY_CATALOG_OK', 'API catalog probe failed')
    r.private(work/'VERIFIED', {'manifest': data['manifest'], 'images': data['images']})
    return 'API_PUBLISHER_NATIVE_FRONTEND_CONTEXT_VERIFIED_GATE_CLOSED'


