"""Exercise private listeners using disposable, uniquely labelled Docker services."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

import engine
from joint_studio_private_config import NGINX_SOURCE, verify_nginx_dump


def run(args, timeout=90):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout).stdout.strip()


def port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return str(listener.getsockname()[1])


def wait(probe):
    deadline = time.monotonic() + 30
    while True:
        try:
            return probe()
        except (OSError, subprocess.CalledProcessError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(.3)


def smoke(*, temp_root=Path('/var/tmp'), volume_gate=False):
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    engine.u.safe(NGINX_SOURCE)
    base = NGINX_SOURCE.read_text(encoding='utf-8')
    if base.count('server {') != 1:
        raise RuntimeError('Unexpected gateway configuration')
    images = [run(['docker', 'inspect', '--format', '{{.Image}}', name])
              for name in ('hengxin-lan-domestic-web', 'hengxin-lan-domestic-api')]
    if any(not re.fullmatch(r'sha256:[0-9a-f]{64}', item) for item in images):
        raise RuntimeError('Invalid existing image identity')
    marker = uuid4().hex
    project, label = 'hxstudiogate' + marker[:12], 'hengxin.studio-test=' + marker
    volume = 'hxstudiogate' + marker

    def ids(kind):
        command = ['docker', 'ps', '-aq'] if kind == 'container' else ['docker', 'network', 'ls', '-q']
        return run([*command, '--filter', 'label=com.docker.compose.project=' + project]).split()

    if ids('container') or ids('network'):
        raise RuntimeError('Disposable project already exists')
    app_source = Path(__file__).resolve().parents[3] / 'hengxin-smart-image/backend/app'
    engine.u.safe(app_source)
    if not (app_source / 'execution/release_gate.py').is_file():
        raise RuntimeError('Candidate release gate source is missing')
    with tempfile.TemporaryDirectory(prefix='hx-private-gate-', dir=temp_root) as name:
        folder = Path(name).resolve()
        if folder.parent != temp_root.resolve() or not folder.name.startswith('hx-private-gate-'):
            raise RuntimeError('Invalid temporary test directory')
        folder.chmod(0o755)
        gate, signal_dir = folder / 'gate', folder / 'signal'
        gate.mkdir(mode=0o755)
        signal_dir.mkdir(mode=0o777)
        signal_dir.chmod(0o777)
        for gate_name in ('workers', 'ingress'):
            (gate / gate_name).write_bytes(b'closed\n')
            (gate / gate_name).chmod(0o644)
        private, public, ui, api = (folder / item for item in ('private.conf', 'public.conf', 'ui.conf', 'smoke_api.py'))
        private.write_text(base.replace('server {', 'server {\n    if ($remote_addr != 127.0.0.1) { return 503; }', 1))
        public.write_text(base)
        ui.write_text("server { listen 80; location / { return 200 'READY'; } }\n")
        api.write_text("import sys\nsys.path.insert(0, '/candidate')\nfrom fastapi import FastAPI\n"
                       "from app.execution.release_gate import ReleaseGateMiddleware\napp=FastAPI()\n"
                       "app.add_middleware(ReleaseGateMiddleware)\n@app.get('/')\n"
                       "def ready(): return {'ready': True}\n@app.get('/api/v1/health/ready')\n"
                       "def health(): return {'ready': True}\n")
        for path in (private, public, ui, api):
            path.chmod(0o644)
        gateway_port, api_port = port(), port()
        if gateway_port == api_port:
            raise RuntimeError('Temporary port allocation collided')
        config = {'name': project, 'services': {
            'gateway': {'image': images[0], 'labels': [label], 'ports': [],
                        'volumes': [{'type': 'bind', 'source': str(private),
                                     'target': '/etc/nginx/conf.d/default.conf', 'read_only': True}]},
            'domestic-api': {'image': images[1], 'labels': [label], 'working_dir': '/smoke', 'ports': [],
                'environment': {'HX_RELEASE_GATE_DIR': '/var/lib/hengxin-domestic/release-gate'},
                'volumes': [{'type': 'bind', 'source': str(api), 'target': '/smoke/smoke_api.py', 'read_only': True},
                            {'type': 'bind', 'source': str(app_source), 'target': '/candidate/app', 'read_only': True},
                            {'type': 'bind', 'source': str(gate), 'target': '/var/lib/hengxin-domestic/release-gate', 'read_only': True}],
                'command': ['uvicorn', 'smoke_api:app', '--host', '127.0.0.1', '--port', '8000']},
            'probe': {'image': images[1], 'labels': [label], 'command': ['python', '-c', 'import time;time.sleep(600)']},
            'worker': {'image': images[1], 'labels': [label],
                'environment': {'HX_RELEASE_GATE_DIR': '/var/lib/hengxin-domestic/release-gate'},
                'volumes': [{'type': 'bind', 'source': str(app_source), 'target': '/candidate/app', 'read_only': True},
                            {'type': 'bind', 'source': str(gate), 'target': '/var/lib/hengxin-domestic/release-gate', 'read_only': True},
                            {'type': 'bind', 'source': str(signal_dir), 'target': '/signal'}],
                'command': ['python', '-c', "import sys;sys.path.insert(0,'/candidate');"
                            "from app.execution.release_gate import wait_for_workers;"
                            "from pathlib import Path;wait_for_workers();Path('/signal/done').write_text('done')"]},
        }}
        if volume_gate:
            # Docker Desktop's Windows bind mounts expose every file as 0777.
            # An isolated labelled volume supplies real Linux modes locally.
            config['volumes'] = {'test-gate': {'external': True, 'name': volume}}
            for service_name in ('domestic-api', 'worker'):
                mounts = config['services'][service_name]['volumes']
                mounts[-1 if service_name == 'domestic-api' else -2] = {
                    'type': 'volume', 'source': 'test-gate',
                    'target': '/var/lib/hengxin-domestic/release-gate', 'read_only': True}
        for service in ('domestic-ui', 'overseas-ui', 'shared-ui'):
            config['services'][service] = {'image': images[0], 'labels': [label], 'volumes': [
                {'type': 'bind', 'source': str(ui), 'target': '/etc/nginx/conf.d/default.conf', 'read_only': True}]}
        compose = folder / 'compose.json'
        prefix = ['docker', 'compose', '-p', project, '-f', str(compose)]
        def save(): compose.write_text(json.dumps(config), encoding='utf-8')
        def service(service_name):
            value = run([*prefix, 'ps', '-q', service_name])
            if len(value.split()) != 1:
                raise RuntimeError('Disposable service missing')
            return value
        def python_in(service_name, code):
            return run(['docker', 'exec', service(service_name), 'python', '-c', code])
        def volume_write(opened):
            value = 'open' if opened else 'closed'
            code = ("import os,pathlib;d=pathlib.Path('/gate');d.chmod(0o755);"
                    "[(d/n).write_text('" + value + "\\n') for n in ('workers','ingress')];"
                    "[(d/n).chmod(0o644) for n in ('workers','ingress')]")
            return run(['docker', 'run', '--rm', '--network', 'none', '--user', '0:0',
                        '--mount', 'type=volume,src=' + volume + ',dst=/gate', images[1], 'python', '-c', code])
        try:
            if volume_gate:
                run(['docker', 'volume', 'create', '--label', 'com.docker.compose.project=' + project,
                     '--label', label, volume])
                volume_write(False)
            save()
            run([*prefix, 'config', '--quiet'])
            dump = run([*prefix, 'run', '--rm', '--no-deps', '--pull', 'never', '--entrypoint', 'nginx', 'gateway', '-T'])
            verify_nginx_dump(dump)
            run([*prefix, 'up', '-d', '--no-deps', '--pull', 'never',
                 'gateway', 'domestic-api', 'probe', 'worker', 'domestic-ui', 'overseas-ui', 'shared-ui'])
            for item in ('gateway', 'domestic-api'):
                row = json.loads(run(['docker', 'inspect', service(item)]))[0]
                if any((row['HostConfig'].get('PortBindings') or {}).values()) or any((row['NetworkSettings'].get('Ports') or {}).values()):
                    raise RuntimeError('Private test service published a port')
            for route in ('/', '/domestic/', '/overseas/', '/shared/'):
                wait(lambda: run(['docker', 'exec', service('gateway'), 'wget', '-qO-', 'http://127.0.0.1' + route]))
            assert wait(lambda: python_in('domestic-api', "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready',timeout=2).status)")) == '200'
            if (signal_dir / 'done').exists():
                raise RuntimeError('Background work ran while gate was closed')
            probe = """import urllib.request, urllib.error, socket
for path in ('/', '/domestic/', '/api/v1/health/ready'):
    req = urllib.request.Request('http://gateway' + path, headers={'X-Forwarded-For': '127.0.0.1'})
    try:
        urllib.request.urlopen(req, timeout=3)
        raise AssertionError('gateway accepted an external request')
    except urllib.error.HTTPError as error:
        assert error.code == 503
s = socket.socket()
s.settimeout(3)
assert s.connect_ex(('domestic-api', 8000)) != 0
print('ISOLATED')
"""
            assert python_in('probe', probe) == 'ISOLATED'
            config['services']['gateway']['volumes'][0]['source'] = str(public)
            config['services']['gateway']['ports'] = [{'target': 80, 'published': gateway_port, 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
            config['services']['domestic-api']['command'][3] = '0.0.0.0'
            config['services']['domestic-api']['ports'] = [{'target': 8000, 'published': api_port, 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
            save()
            run([*prefix, 'up', '-d', '--no-deps', '--pull', 'never', 'gateway', 'domestic-api'])
            opener = build_opener(ProxyHandler({}))
            assert wait(lambda: opener.open('http://127.0.0.1:' + gateway_port + '/', timeout=2).status) == 200
            assert wait(lambda: opener.open('http://127.0.0.1:' + api_port + '/api/v1/health/ready', timeout=2).status) == 200
            import urllib.error
            try:
                opener.open('http://127.0.0.1:' + api_port + '/', timeout=2)
                raise RuntimeError('Published test API accepted business while gated')
            except urllib.error.HTTPError as error:
                if error.code != 503:
                    raise
            if (signal_dir / 'done').exists():
                raise RuntimeError('Background work ran before formal checks')
            if volume_gate:
                volume_write(True)
            else:
                for gate_name in ('workers', 'ingress'):
                    tmp = gate / (gate_name + '.next')
                    tmp.write_bytes(b'open\n')
                    tmp.chmod(0o644)
                    os.replace(tmp, gate / gate_name)
            assert wait(lambda: opener.open('http://127.0.0.1:' + api_port + '/', timeout=2).status) == 200
            deadline = time.monotonic() + 20
            while not (signal_dir / 'done').exists() and time.monotonic() < deadline:
                time.sleep(.2)
            if (signal_dir / 'done').read_text() != 'done':
                raise RuntimeError('Gated background process did not resume')
            opened = ("import urllib.request; assert urllib.request.urlopen('http://gateway/',timeout=3).status==200; "
                      "assert urllib.request.urlopen('http://domestic-api:8000/',timeout=3).status==200;print('OPEN')")
            assert wait(lambda: python_in('probe', opened)) == 'OPEN'
        finally:
            containers = ids('container')
            if containers:
                rows = json.loads(run(['docker', 'inspect', *containers]))
                if len(rows) != len(containers):
                    raise RuntimeError('Disposable container inventory changed')
                for row in rows:
                    labels = row['Config'].get('Labels') or {}
                    if (labels.get('com.docker.compose.project') != project or labels.get('hengxin.studio-test') != marker
                            or labels.get('com.docker.compose.service') not in config['services']):
                        raise RuntimeError('Unrecognized container in disposable project')
                run(['docker', 'rm', '-f', *containers])
            networks = ids('network')
            if networks:
                for row in json.loads(run(['docker', 'network', 'inspect', *networks])):
                    if (row.get('Labels') or {}).get('com.docker.compose.project') != project or row.get('Containers'):
                        raise RuntimeError('Unrecognized network in disposable project')
                run(['docker', 'network', 'rm', *networks])
            if ids('container') or ids('network'):
                raise RuntimeError('Disposable resources remain')
            if volume_gate:
                volumes = run(['docker', 'volume', 'ls', '-q', '--filter', 'name=^' + volume + '$']).split()
                if volumes:
                    row = json.loads(run(['docker', 'volume', 'inspect', volume]))[0]
                    labels = row.get('Labels') or {}
                    if (volumes != [volume] or labels.get('com.docker.compose.project') != project
                            or labels.get('hengxin.studio-test') != marker):
                        raise RuntimeError('Unrecognized test volume')
                    run(['docker', 'volume', 'rm', volume])
    print(json.dumps({'status': 'PASS', 'private_network_blocked': True, 'background_gate_verified': True,
                      'public_request_gate_verified': True, 'public_readiness': True,
                      'test_resources_remaining': 0}), flush=True)


if __name__ == '__main__':
    smoke()
