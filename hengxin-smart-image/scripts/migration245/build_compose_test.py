"""Synthetic-only tests: never read production snapshots or connect to services."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import build_compose as b


def fixture():
    containers = []
    for project, scope in b.PROJECTS.items():
        for name in b.EXPECTED[scope].split():
            net = 'hengxin-vps-staging_default' if scope == 'domestic' else scope + '-net'
            cfg = {'Labels': {'com.docker.compose.project': project, 'com.docker.compose.service': name},
                   'Env': ['LANG=C.UTF-8'], 'Cmd': ['server'], 'Entrypoint': ['/entrypoint'],
                   'User': 'app', 'WorkingDir': '/app'}
            host = {'RestartPolicy': {'Name': 'unless-stopped', 'MaximumRetryCount': 0}, 'PortBindings': {},
                    'Memory': 1024, 'MemorySwap': 2048, 'NanoCpus': 1000000000, 'GroupAdd': ['986'],
                    'SecurityOpt': ['no-new-privileges:true'], 'ReadonlyRootfs': True,
                    'Ulimits': [{'Name': 'nofile', 'Soft': 1024, 'Hard': 2048}], 'PidsLimit': 64}
            c = {'Name': '/' + project + '-' + name + '-1', 'Image': 'sha256:' + 'a' * 64,
                 'Config': cfg, 'HostConfig': host, 'Mounts': [],
                 'NetworkSettings': {'Networks': {net: {'Aliases': [project + '-' + name + '-1', name]}}}}
            prefix = '' if scope == 'domestic' else scope.upper() + '_'
            if name.endswith('postgres'):
                cfg['Env'] += ['POSTGRES_PASSWORD=old-pg-' + scope, 'POSTGRES_USER=user', 'POSTGRES_DB=db']
                port = '15433' if scope == 'domestic' else '15443'
                host['PortBindings'] = {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': port}]}
            if name.endswith('redis'):
                cfg['Cmd'] = ['redis-server', '--appendonly', 'yes']
                cfg['Healthcheck'] = {'Test': ['CMD', 'redis-cli', 'ping'], 'Interval': 5000000000, 'Retries': 20}
                cfg['Env'] += ['REDIS_PASSWORD=old-redis-' + scope]
                port = {'domestic': '16388', 'overseas': '16398', 'identity': '16400'}[scope]
                host['PortBindings'] = {'6379/tcp': [{'HostIp': '127.0.0.1', 'HostPort': port}]}
            if name.endswith('minio'):
                cfg['Env'] += ['MINIO_ROOT_USER=old-access', 'MINIO_ROOT_PASSWORD=old-minio-' + scope]
                port = '15900' if scope == 'domestic' else '15910'
                host['PortBindings'] = {'9000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': port}]}
            if name in ('api', 'identity-api'):
                host['PortBindings'] = {'8000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': {'domestic': '18008', 'overseas': '18018', 'identity': '18012'}[scope]}]}
                cfg['Env'] += [prefix + 'REDIS_URL=redis://:old-redis-' + scope + '@107.172.161.139:6379/0']
                if scope != 'identity':
                    cfg['Env'] += [prefix + 'DATABASE_URL=postgresql+psycopg://user:old-pg-' + scope + '@107.172.161.139:5432/db',
                                   prefix + 'MINIO_ENDPOINT=107.172.161.139:9000', prefix + 'MINIO_ACCESS_KEY=old-access',
                                   prefix + 'MINIO_SECRET_KEY=old-minio-' + scope, prefix + 'IDENTITY_SERVICE_KEY=old-identity-' + scope,
                                   prefix + 'IDENTITY_SERVICE_URL=http://107.172.161.139:18012',
                                   prefix + 'IDENTITY_PUBLIC_ORIGIN=https://zhitu.qhhengxin.top',
                                   'EXTERNAL_API_KEY=keep-$literal', 'API_IMAGE_BASE_URL=https://api.qhhengxin.top/v1']
                else:
                    cfg['Env'] += ['IDENTITY_DOMESTIC_SERVICE_KEY=old-identity-domestic', 'IDENTITY_OVERSEAS_SERVICE_KEY=old-identity-overseas']
            if name == 'skill-publisher':
                cfg['Env'] += ['OVERSEAS_REDIS_URL=redis://127.0.0.1:1/0', 'OVERSEAS_MINIO_ENDPOINT=127.0.0.1:1']
                c['NetworkSettings']['Networks'][net]['Aliases'].append('overseas-api')
            if name in ('api', 'skill-publisher') and scope == 'overseas':
                c['Mounts'].append({'Type': 'volume', 'Name': 'old_execution', 'Source': '/var/lib/docker/volumes/old_execution/_data',
                                    'Destination': '/var/lib/hengxin-overseas/execution', 'RW': True})
            if name.endswith(('redis', 'postgres', 'minio')):
                c['Mounts'].append({'Type': 'volume', 'Name': 'old_' + name, 'Source': '/var/lib/docker/volumes/old_' + name + '/_data',
                                    'Destination': '/data', 'RW': True})
            if name == 'web':
                c['Mounts'].append({'Type': 'bind', 'Source': b.NGINX, 'Destination': '/etc/nginx/conf.d/default.conf', 'RW': False})
            containers.append(c)
    return {'containers': containers, 'units': [{'name': 'hengxin-overseas-worker', 'environment': {
        'OVERSEAS_DATABASE_URL': 'postgresql+psycopg://user:old-pg-overseas@107.172.161.139:15443/db',
        'OVERSEAS_REDIS_URL': 'redis://:old-redis-overseas@107.172.161.139:16398/0',
        'OVERSEAS_MINIO_SECRET_KEY': 'old-minio-overseas', 'INVOCATION_ID': 'stale', 'JOURNAL_STREAM': 'stale'}}],
        'config_files': {b.NGINX: 'proxy_pass http://api:8000;\nproxy_set_header X-Forwarded-Proto $scheme;'}}


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.output = b.build(self.data)
        self.compose = self.output['compose.json']
        self.services = self.compose['services']

    def test_rotates_coherent_secrets_and_preserves_external(self):
        for scope in ('domestic', 'overseas'):
            prefix = '' if scope == 'domestic' else 'OVERSEAS_'
            api = self.services[scope + '-api']['environment']
            pg = self.services[scope + '-postgres']['environment']['POSTGRES_PASSWORD']
            redis = self.services[scope + '-redis']['environment']['REDIS_PASSWORD']
            self.assertEqual(unquote(urlsplit(api[prefix + 'DATABASE_URL']).password), pg)
            self.assertEqual(unquote(urlsplit(api[prefix + 'REDIS_URL']).password), redis)
            self.assertEqual(api[prefix + 'MINIO_SECRET_KEY'], self.services[scope + '-minio']['environment']['MINIO_ROOT_PASSWORD'])
            self.assertEqual(api[prefix + 'IDENTITY_SERVICE_KEY'], self.services['identity-api']['environment']['IDENTITY_' + scope.upper() + '_SERVICE_KEY'])
            self.assertEqual(api['EXTERNAL_API_KEY'], 'keep-$$literal')
            self.assertEqual(api['API_IMAGE_BASE_URL'], 'https://api.qhhengxin.top/v1')
        serialized = json.dumps(self.compose)
        for old in ('old-pg-', 'old-redis-', 'old-minio-', 'old-identity-', 'old-access', '107.172.161.139'):
            self.assertNotIn(old, serialized)
        native = self.output['native-env.json']['hengxin-overseas-worker']
        self.assertEqual(urlsplit(native['OVERSEAS_DATABASE_URL']).password,
                         self.services['overseas-postgres']['environment']['POSTGRES_PASSWORD'])
        self.assertEqual(urlsplit(native['OVERSEAS_DATABASE_URL']).hostname, '127.0.0.1')
        self.assertEqual(urlsplit(native['OVERSEAS_DATABASE_URL']).port, 15443)
        self.assertNotIn('INVOCATION_ID', native)
        self.assertNotEqual(self.services['overseas-redis']['environment']['REDIS_PASSWORD'],
                            self.services['domestic-redis']['environment']['REDIS_PASSWORD'])

    def test_uri_password_special_characters(self):
        result = b.endpoint('postgresql://user%40domain:old@prod:5432/db?sslmode=disable', 'domestic-postgres', 5432, '$a/b@: ?#%')
        uri = urlsplit(result)
        self.assertEqual(unquote(uri.password), '$a/b@: ?#%')
        self.assertEqual(unquote(uri.username), 'user@domain')
        self.assertEqual(uri.query, 'sslmode=disable')

    def test_networks_mounts_and_ports_isolated(self):
        self.assertEqual(len(self.services), 16)
        for service in self.services.values():
            self.assertEqual(service['pull_policy'], 'never')
            self.assertEqual(service['image'], 'sha256:' + 'a' * 64)
            for net in service['networks'].values():
                self.assertFalse(any(x.startswith('hengxin-') for x in net['aliases']))
            self.assertTrue(all(p['host_ip'] == '127.0.0.1' for p in service['ports']))
        publisher = self.services['overseas-skill-publisher']
        self.assertFalse(any('overseas-api' in n['aliases'] for n in publisher['networks'].values()))
        for name in ('overseas-api', 'overseas-skill-publisher'):
            mount = self.services[name]['volumes'][0]
            self.assertEqual(mount['type'], 'bind')
            self.assertEqual(mount['source'], '/var/lib/hengxin-overseas/execution')
            self.assertFalse(mount['bind']['create_host_path'])
        self.assertTrue(all(v['name'].startswith('hengxin-lan-') and not v.get('external') for v in self.compose['volumes'].values()))
        self.assertIn('http://domestic-api:8000', self.output['nginx.conf'])
        self.assertIn('$http_x_forwarded_proto', self.output['nginx.conf'])
        self.assertEqual(publisher['environment']['OVERSEAS_REDIS_URL'], 'redis://127.0.0.1:1/0')

    def test_runtime_and_interpolation_preserved(self):
        s = self.services['domestic-api']
        for key, expected in {'command': ['server'], 'entrypoint': ['/entrypoint'], 'user': 'app', 'working_dir': '/app',
                              'mem_limit': 1024, 'memswap_limit': 2048, 'cpus': 1.0, 'group_add': ['986'], 'pids_limit': 64}.items():
            self.assertEqual(s[key], expected)
        redis = self.services['domestic-redis']
        self.assertIn('--requirepass', redis['command'])
        self.assertIn('$$REDIS_PASSWORD', redis['healthcheck']['test'][1])
        self.assertEqual(redis['healthcheck']['interval'], '5000000000ns')
        self.assertEqual(b.escaped({'x': '$A ${B} $$'}), {'x': '$$A $${B} $$$$'})
        self.assertEqual(s['environment']['HTTP_PROXY'], 'http://172.30.245.1:7891')
        self.assertIn('api.dingtalk.com', s['environment']['NO_PROXY'])

    def test_reports_are_secret_free_and_build_is_pure(self):
        self.assertEqual(self.data, fixture())
        report = json.dumps(self.output['differences.json'])
        for secret in ('old-pg-', 'keep-$literal', self.services['domestic-postgres']['environment']['POSTGRES_PASSWORD']):
            self.assertNotIn(secret, report)

    def test_rejects_changed_inventory_and_mount_escape(self):
        data = copy.deepcopy(self.data)
        data['containers'].pop()
        with self.assertRaises(ValueError):
            b.build(data)

    def test_refuses_mutable_images_and_host_network(self):
        for field, value in [('Image', 'latest'), ('HostConfig', {'NetworkMode': 'host'})]:
            data = copy.deepcopy(self.data)
            if field == 'HostConfig':
                data['containers'][0][field].update(value)
            else:
                data['containers'][0][field] = value
            with self.assertRaises(ValueError):
                b.build(data)
        data = copy.deepcopy(self.data)
        data['containers'][0]['Mounts'] = [{'Type': 'bind', 'Source': '/etc/shadow', 'Destination': '/data', 'RW': True}]
        with self.assertRaises(ValueError):
            b.build(data)

    def test_exclusive_output_and_path_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'target'
            with patch.object(b, 'ROOT', root):
                with self.assertRaises(ValueError):
                    b.write_outputs(self.output, root.parent / 'wrong')
                b.write_outputs(self.output, root)
                before = (root / 'compose.json').read_bytes()
                with self.assertRaises(FileExistsError):
                    b.write_outputs(self.output, root)
                self.assertEqual((root / 'compose.json').read_bytes(), before)
                self.assertEqual(set(p.name for p in root.iterdir()), set(self.output))

    def test_wrong_host_refused_before_reads(self):
        with patch.object(b.socket, 'gethostname', return_value='production'), patch.object(b.Path, 'read_text') as read:
            with self.assertRaises(RuntimeError):
                b.main()
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
