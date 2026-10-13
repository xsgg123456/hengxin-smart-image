import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('overseas_topology', Path(__file__).with_name('overseas-topology.py'))
topology = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topology)


def env(path):
    return {key: value[1:-1] for key, value in
            (line.split('=', 1) for line in Path(path).read_text().splitlines())}


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / 'src'
        (self.source / 'infra').mkdir(parents=True)
        for name in ('compose.overseas.yaml', 'compose.identity.yaml'):
            (self.source / 'infra' / name).touch()
        self.destination = self.work / 'installed-worker.env'
        self.patcher = patch.object(topology, 'WORKER_DESTINATION', self.destination)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.domestic = dict(DINGTALK_CORP_ID='corp', DINGTALK_CLIENT_ID='client',
            DINGTALK_AGENT_ID='agent', DINGTALK_CLIENT_SECRET='provider-secret',
            CODEX_BINARY='/opt/hengxin-runtime/codex-0.156.1/codex',
            CODEX_BWRAP_BINARY='/opt/hengxin-runtime/bwrap', CODEX_VERSION='0.156.1',
            DATABASE_URL='domestic-database-secret', REDIS_URL='domestic-redis-secret',
            MINIO_SECRET_KEY='domestic-minio-secret', CODEX_AUTH_FILE='/domestic/auth.json')

    def prepare(self):
        return topology.prepare(self.work, self.source, 'hengxin-backend:release', self.domestic)

    def test_credentials_and_return_values_are_isolated(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result = self.prepare()
        self.assertEqual(out.getvalue(), '')
        identity, overseas, worker = (env(result[key]) for key in ('identity_env', 'overseas_env', 'worker_env'))
        all_files = '\n'.join(p.read_text() for p in self.work.iterdir() if p.is_file())
        for secret in ('domestic-database-secret', 'domestic-redis-secret', 'domestic-minio-secret', '/domestic/auth.json'):
            self.assertNotIn(secret, all_files)
        domestic = json.loads(Path(result['domestic_overlay']).read_text())['services']['api']['environment']
        self.assertEqual(domestic['IDENTITY_SERVICE_KEY'], identity['IDENTITY_DOMESTIC_SERVICE_KEY'])
        self.assertEqual(overseas['OVERSEAS_IDENTITY_SERVICE_KEY'], identity['IDENTITY_OVERSEAS_SERVICE_KEY'])
        self.assertNotEqual(domestic['IDENTITY_SERVICE_KEY'], overseas['OVERSEAS_IDENTITY_SERVICE_KEY'])
        self.assertNotIn(identity['IDENTITY_DOMESTIC_SERVICE_KEY'], Path(result['overseas_env']).read_text())
        self.assertNotIn('provider-secret', Path(result['worker_env']).read_text())
        self.assertEqual(identity['IDENTITY_DINGTALK_CLIENT_SECRET'], 'provider-secret')
        for key, value in overseas.items():
            if 'PASSWORD' in key or 'SECRET' in key:
                self.assertNotIn(value, json.dumps(result))
        secrets = [value for key, value in overseas.items() if 'PASSWORD' in key or 'SECRET' in key]
        self.assertEqual(len(secrets), len(set(secrets)))
        for key in ('OVERSEAS_OWNER_PASSWORD', 'OVERSEAS_POSTGRES_PASSWORD', 'OVERSEAS_MINIO_ROOT_PASSWORD'):
            self.assertNotIn(overseas[key], Path(result['worker_env']).read_text())
        self.assertIn(overseas['OVERSEAS_APP_PASSWORD'], worker['OVERSEAS_DATABASE_URL'])
        self.assertEqual(worker['OVERSEAS_CODEX_AUTH_FILE'], topology.AUTH_FILE)
        self.assertEqual(worker['OVERSEAS_CODEX_VERSION'], '0.156.1')
        self.assertEqual(worker['OVERSEAS_IDENTITY_SERVICE_URL'], 'http://127.0.0.1:18012')
        self.assertEqual(worker['OVERSEAS_ENABLE_CODEX_EXECUTOR'], 'true')
        self.assertEqual(overseas['OVERSEAS_APP_ENV'], 'production')
        self.assertFalse(self.destination.exists())
        if os.name == 'posix':
            for p in self.work.iterdir():
                if p.is_file():
                    self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_ports_networks_and_native_directory_isolation(self):
        result = self.prepare()
        overseas = json.loads(Path(result['overseas_overlay']).read_text())
        ports = [p for svc in overseas['services'].values() for p in svc.get('ports', [])]
        self.assertEqual(set(ports), {'127.0.0.1:15443:5432', '127.0.0.1:16398:6379', '127.0.0.1:15910:9000'})
        self.assertEqual(env(result['overseas_env'])['OVERSEAS_API_PORT'], '18018')
        self.assertEqual(env(result['identity_env'])['IDENTITY_HTTP_PORT'], '18012')
        self.assertNotIn('18008', json.dumps(overseas))
        for name in ('overseas-postgres', 'overseas-redis', 'overseas-minio'):
            self.assertNotIn('networks', overseas['services'][name])
        api = overseas['services']['api']
        self.assertEqual(set(api['networks']), {'overseas', 'hx-identity-overseas', 'hx-overseas-edge'})
        self.assertEqual(api['networks']['hx-overseas-edge']['aliases'], ['overseas-api'])
        self.assertNotIn('volumes', api)
        self.assertNotIn('roots-init', overseas['services'])
        self.assertEqual(result['directories'], list(topology.ROOTS.values()))
        identity = json.loads(Path(result['identity_overlay']).read_text())
        self.assertNotIn('networks', identity['services']['identity-redis'])
        self.assertEqual(set(identity['services']['identity-api']['networks']), {'identity', *topology.NETWORKS})

    def test_existing_staged_or_installed_configuration_refused(self):
        self.destination.write_text('existing-secret')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertFalse((self.work / 'identity.env').exists())
        self.destination.unlink()
        self.prepare()
        before = (self.work / 'identity.env').read_bytes()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(before, (self.work / 'identity.env').read_bytes())

    def test_invalid_secret_is_not_echoed_or_partially_written(self):
        self.domestic['DINGTALK_CLIENT_SECRET'] = 'secret\nENV=injection'
        with self.assertRaises(ValueError) as error:
            self.prepare()
        self.assertNotIn('secret', str(error.exception))
        self.assertFalse((self.work / 'identity.env').exists())

    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose unavailable')
    def test_actual_compose_merge_preserves_resource_network_isolation(self):
        self.source = Path(__file__).resolve().parents[2] / 'hengxin-smart-image'
        result = self.prepare()
        for context in ('overseas', 'identity'):
            run = subprocess.run(['docker', 'compose', '--env-file', result[context + '_env'],
                '-f', result[context + '_compose'], '-f', result[context + '_overlay'],
                'config', '--format', 'json'], capture_output=True, text=True)
            # Never include stderr/stdout in assertions: Compose can echo config.
            self.assertEqual(run.returncode, 0, 'Compose merge validation failed')
            config = json.loads(run.stdout)
            services = config['services']
            if context == 'overseas':
                for service in ('overseas-postgres', 'overseas-redis', 'overseas-minio'):
                    self.assertEqual(set(services[service]['networks']), {'overseas'})
                api = services['api']
                self.assertEqual(api['environment']['OVERSEAS_APP_ENV'], 'production')
                self.assertEqual(api['environment']['OVERSEAS_ENABLE_CODEX_EXECUTOR'], 'false')
                self.assertEqual([str(p['published']) for p in api['ports']], ['18018'])
                self.assertTrue(all(v['type'] == 'volume' for v in api['volumes']))
                self.assertTrue(all(v['type'] == 'volume' for v in services['roots-init']['volumes']))
                self.assertNotIn('OVERSEAS_OWNER_PASSWORD', api['environment'])
                self.assertNotIn('OVERSEAS_MINIO_ROOT_PASSWORD', api['environment'])
            else:
                self.assertEqual(set(services['identity-redis']['networks']), {'identity'})
                self.assertEqual([str(p['published']) for p in services['identity-api']['ports']], ['18012'])


if __name__ == '__main__':
    unittest.main()
