"""Offline security/behavior regression tests; no production inputs or connections."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_edge as b


def fixture():
    compose = {'name': 'hengxin-lan', 'services': {'domestic-web': {
        'image': 'sha256:' + 'a' * 64,
        'ports': [{'target': 80, 'published': '18080', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]}},
        'networks': {k: {'name': 'hengxin-lan-' + k} for k in b.NETWORKS}}
    inspected = [{'Name': 'hengxin-lan-' + k, 'Driver': 'bridge', 'Scope': 'local', 'EnableIPv6': False,
                  'Labels': {'com.docker.compose.project': 'hengxin-lan', 'com.docker.compose.network': k},
                  'IPAM': {'Config': [{'Subnet': subnet, 'Gateway': str(b.ipaddress.ip_network(subnet)[1])}]}}
                 for k, subnet in b.NETWORKS.items()]
    return compose, inspected


class EdgeTests(unittest.TestCase):
    def test_valid_scope_and_immutable_readonly_mounts(self):
        compose, inspected = fixture()
        originals = copy.deepcopy((compose, inspected))
        output = b.build(compose, inspected)
        self.assertEqual((compose, inspected), originals)
        edge = json.loads(output['edge-compose.json'])['services']['https']
        self.assertEqual(edge['image'], compose['services']['domestic-web']['image'])
        self.assertEqual(edge['network_mode'], 'host')
        self.assertEqual(edge['pull_policy'], 'never')
        self.assertEqual(edge['restart'], 'unless-stopped')
        self.assertNotIn('ports', edge)
        self.assertTrue(all(v['read_only'] and not v['bind']['create_host_path'] for v in edge['volumes']))
        self.assertEqual(len(edge['volumes']), 3)
        nginx = output['edge-nginx.conf']
        self.assertEqual([x.strip() for x in nginx.splitlines() if 'listen ' in x],
                         ['listen 192.168.1.245:443 ssl;'])
        for required in ('allow 192.168.1.0/24;', 'allow 192.168.2.0/23;', 'deny all;',
                         'client_max_body_size 512m;', 'proxy_buffering off;', 'proxy_request_buffering off;',
                         'proxy_set_header X-Forwarded-Proto https;', 'proxy_pass http://127.0.0.1:18080;',
                         'add_header X-Hengxin-Environment lan-245 always;'):
            self.assertIn(required, nginx)

    def test_unit_allowlist_exact_and_retries_missing_bridge(self):
        unit = b.build(*fixture())[b.UNIT]
        allowed = {s.split('=', 1)[1] for s in unit.splitlines() if s.startswith('IPAddressAllow=')}
        self.assertEqual(allowed, set(b.NETWORKS.values()) | {'127.0.0.0/8'})
        for line in ('IPAddressDeny=any', 'User=nobody', 'NoNewPrivileges=true', 'ProtectSystem=strict',
                     'ProtectHome=true', 'PrivateTmp=true', 'Restart=always', 'RestartSec=5s',
                     'StartLimitIntervalSec=0', 'Requires=docker.service mihomo.service'):
            self.assertIn(line, unit.splitlines())
        self.assertIn('bind=172.30.245.1', unit)
        self.assertNotIn('192.168.', unit)
        self.assertNotIn('ExecStop', unit)

    def test_readonly_root_uses_writable_tmp_for_every_nginx_temp_path(self):
        output = b.build(*fixture())
        edge = json.loads(output['edge-compose.json'])['services']['https']
        self.assertTrue(edge['read_only'])
        self.assertIn('/tmp:rw,nosuid,nodev,size=64m', edge['tmpfs'])
        paths = dict(b.re.findall(r'^\s*(\w+_temp_path)\s+([^;]+);', output['edge-nginx.conf'], b.re.M))
        self.assertEqual(paths, {'client_body_temp_path': '/tmp/client_temp',
                                'proxy_temp_path': '/tmp/proxy_temp',
                                'fastcgi_temp_path': '/tmp/fastcgi_temp',
                                'uwsgi_temp_path': '/tmp/uwsgi_temp',
                                'scgi_temp_path': '/tmp/scgi_temp'})

    def test_reject_network_drift_or_forged_ownership(self):
        mutations = [lambda n: n.pop(), lambda n: n.append(n[0]),
                     lambda n: n[0].update(Driver='host'), lambda n: n[0].update(EnableIPv6=True),
                     lambda n: n[0]['Labels'].update({'com.docker.compose.project': 'other'}),
                     lambda n: n[0]['IPAM']['Config'][0].update(Subnet='192.168.1.0/24'),
                     lambda n: n[0]['IPAM']['Config'][0].update(Subnet='172.16.0.0/12'),
                     lambda n: n[0]['IPAM']['Config'][0].update(Gateway='172.19.0.2')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                compose, inspected = fixture()
                mutate(inspected)
                with self.assertRaises(ValueError):
                    b.build(compose, inspected)

    def test_reject_external_web_or_mutable_image(self):
        for field, value in [('image', 'nginx:latest'), ('ports', []),
                             ('ports', [{'target': 80, 'published': '18080', 'host_ip': '0.0.0.0', 'protocol': 'tcp'}])]:
            compose, inspected = fixture()
            compose['services']['domestic-web'][field] = value
            with self.assertRaises(ValueError):
                b.build(compose, inspected)

    def test_host_and_root_guards_precede_reads(self):
        for host, uid in [('wrong-host', 0), ('hengxin-ai-245', 1000)]:
            with patch.object(b.socket, 'gethostname', return_value=host), \
                    patch.object(b.os, 'geteuid', return_value=uid, create=True), \
                    patch.object(b, 'protected') as protect, self.assertRaises(RuntimeError):
                b.main()
            protect.assert_not_called()

    def test_write_is_exclusive_and_batch_preflight_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'ROOT', Path(tmp)), \
                patch.object(b, 'protected'):
            output = b.build(*fixture())
            (Path(tmp) / b.UNIT).write_text('existing')
            with self.assertRaises(FileExistsError):
                b.write_outputs(output)
            self.assertFalse((Path(tmp) / 'edge-compose.json').exists())
            self.assertEqual((Path(tmp) / b.UNIT).read_text(), 'existing')
            (Path(tmp) / b.UNIT).unlink()
            b.write_outputs(output)
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, set(output))
            with self.assertRaises(FileExistsError):
                b.write_outputs(output)
            if os.name == 'posix':
                self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in Path(tmp).iterdir()))

    def test_protected_rejects_permissions_and_symlinks(self):
        from types import SimpleNamespace
        path = Path('/private')
        with patch.object(Path, 'resolve', return_value=path), patch.object(Path, 'is_symlink', return_value=False):
            for uid, mode in [(1, 0o100600), (0, 0o100644), (0, 0o40700)]:
                with patch.object(Path, 'stat', return_value=SimpleNamespace(st_uid=uid, st_mode=mode)), \
                        self.assertRaises(ValueError):
                    b.protected(path)
        with patch.object(Path, 'resolve', return_value=Path('/elsewhere')), self.assertRaises(ValueError):
            b.protected(path)


if __name__ == '__main__':
    unittest.main()
