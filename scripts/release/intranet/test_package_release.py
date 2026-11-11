"""Offline packaging checks; real Git fixtures, simulated frontend toolchain."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import package_release as p


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', '打包测试')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.files = {
            'backend/app/main.py': b'value = "committed"\n',
            p.RENDERER: b'#!/usr/bin/env python3\n',
            'backend/pyproject.toml': b'[project]\nname="fixture"\n',
            'backend/.env.example': b'EXAMPLE=only\n',
            'backend/.env': b'SECRET=private\n',
            'backend/config.env': b'SECRET=private\n',
            'backend/secrets.key': b'secret\n',
            'backend/tests/test_sample.py': b'assert False\n',
            'backend/__pycache__/test.pyc': b'cache',
            'frontend/package.json': json.dumps({'engines': {'node': '24.18.1'},
                                                'packageManager': 'pnpm@10.33.4'}).encode(),
            'frontend/pnpm-lock.yaml': b'lockfileVersion: 9\n',
            'frontend/src/main.ts': b'console.log("committed");\n',
            'frontend/.env.production': b'VITE_SECRET=private\n',
            'frontend/.npmrc': b'//registry.npmjs.org/:_authToken=secret\n',
            'frontend/node_modules/junk.js': b'old dependency',
            'frontend/dist/index.html': b'old frontend',
        }
        for name, data in self.files.items():
            self.write(p.PREFIX + name, data)
        self.write(p.RUNTIME_INPUTS[0], b'Runtime contract\n')
        self.commit = self.commit_all()
        self.output = self.root / 'release.tar.gz'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def write(self, name, data):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def commit_all(self):
        self.git('add', '.')
        self.git('commit', '-qm', '测试归档')
        return self.git('rev-parse', 'HEAD').decode().strip()

    def fake_build(self, source, scratch, commit):
        self.assertEqual((source / 'frontend/src/main.ts').read_bytes(), self.files['frontend/src/main.ts'])
        self.assertFalse((source / 'frontend/.env.production').exists())
        self.assertFalse((source / 'frontend/.npmrc').exists())
        self.assertFalse((source / 'frontend/dist').exists())
        dist = source / 'frontend/dist/assets'
        dist.mkdir(parents=True)
        (dist.parent / 'index.html').write_bytes(b'<script src="/assets/current.js"></script>')
        (dist / 'current.js').write_bytes(b'current build')
        return {'lockfile': 'pnpm-lock.yaml', 'lockfile_sha256': p.sha(self.files['frontend/pnpm-lock.yaml'])}

    def package(self, build=None):
        with patch.object(p, 'build_frontend', side_effect=build or self.fake_build):
            return p.package_release(self.repo, self.commit, self.output)

    def test_committed_bytes_manifest_filters_and_permissions(self):
        self.write(p.PREFIX + 'backend/app/main.py', b'dirty backend\r\n')
        self.write(p.PREFIX + 'frontend/src/main.ts', b'dirty frontend')
        self.write(p.PREFIX + 'backend/untracked.py', b'untracked')
        self.write(p.PREFIX + 'backend/local.env', b'local secret')
        manifest = self.package()
        self.assertEqual(manifest['commit'], self.commit)
        self.assertEqual(manifest['runtime_inputs'], {p.RUNTIME_INPUTS[0]: p.sha(b'Runtime contract\n')})
        with tarfile.open(self.output) as archive:
            members = archive.getmembers()
            self.assertTrue(all(m.isfile() and not m.issym() for m in members))
            self.assertEqual(archive.getmember(p.RENDERER).mode, 0o755)
            self.assertEqual(archive.getmember('backend/app/main.py').mode, 0o644)
            names = set(archive.getnames()) - {'release-manifest.json'}
            self.assertEqual(names, set(manifest['files']))
            for name in names:
                data = archive.extractfile(name).read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), manifest['files'][name])
                if name.startswith('backend/'):
                    self.assertEqual(data, self.files[name])
            self.assertEqual(archive.extractfile('release-manifest.json').read(),
                             (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
        self.assertIn('backend/.env.example', names)
        self.assertEqual(manifest['frontend_current_files'], {n: manifest['files'][n] for n in
                         ['frontend/assets/current.js', 'frontend/index.html']})
        self.assertFalse(any(p.excluded(n) for n in names))

    def test_revision_and_overwrite_guards(self):
        self.assertEqual(p.resolve_commit(self.repo, 'HEAD'), self.commit)
        with self.assertRaisesRegex(RuntimeError, 'full 40'):
            p.resolve_commit(self.repo, self.commit[:8])
        self.output.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            self.package()
        self.assertEqual(self.output.read_bytes(), b'keep')

    def test_export_subst_cannot_mislabel_git_bytes(self):
        self.write('.gitattributes', b'*.py export-subst\n')
        self.write(p.PREFIX + 'backend/app/main.py', b'commit = "$Format:%H$"\n')
        self.commit = self.commit_all()
        with self.assertRaisesRegex(RuntimeError, 'bytes differ from Git'):
            self.package()
        self.assertFalse(self.output.exists())

    def test_export_ignore_cannot_hide_runtime_source(self):
        self.write('.gitattributes', b'**/app/main.py export-ignore\n')
        self.commit = self.commit_all()
        with self.assertRaisesRegex(RuntimeError, 'omitted source'):
            self.package()

    def test_symlink_is_rejected_even_on_windows(self):
        oid = self.git('hash-object', '-w', p.PREFIX + 'backend/app/main.py')
        self.git('update-index', '--add', '--cacheinfo', '120000', oid.decode().strip(), p.PREFIX + 'backend/link')
        self.git('commit', '-qm', '测试链接')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(RuntimeError, 'Links/submodules'):
            self.package()

    def test_unsafe_archive_paths_are_rejected(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'a\\b', 'a/../b', 'a//b', './a'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                p.safe_path(name)

    def test_private_key_in_unusual_file_is_rejected(self):
        self.write(p.PREFIX + 'backend/secret.txt', b'-----BEGIN OPENSSH PRIVATE KEY-----\nsecret')
        self.commit = self.commit_all()
        with self.assertRaisesRegex(RuntimeError, 'Private key'):
            self.package()

    def test_backend_mutation_during_build_is_rejected(self):
        def mutate(source, scratch, commit):
            build = self.fake_build(source, scratch, commit)
            (source / 'backend/app/main.py').write_bytes(b'mutated')
            return build
        with self.assertRaisesRegex(RuntimeError, 'Backend changed'):
            self.package(mutate)

    def test_dependency_lock_mutation_is_rejected(self):
        def mutate(source, scratch, commit):
            build = self.fake_build(source, scratch, commit)
            build['lockfile_sha256'] = p.sha(b'modified lock')
            return build
        with self.assertRaisesRegex(RuntimeError, 'lockfile changed'):
            self.package(mutate)

    def test_build_env_does_not_inherit_host_tokens_or_vite_values(self):
        with patch.dict(os.environ, {'VITE_SECRET': 'bad', 'NPM_TOKEN': 'bad', 'NODE_OPTIONS': 'bad',
                                     'VITE_API_URL': 'https://public.invalid'}):
            env = p.build_environment(self.root, self.commit)
        self.assertEqual(env['VITE_API_URL'], '/api/v1')
        for key in ('VITE_SECRET', 'NPM_TOKEN', 'NODE_OPTIONS'):
            self.assertNotIn(key, env)
        self.assertEqual(Path(env['HOME']).parent, self.root)
        self.assertEqual(Path(env['npm_config_userconfig']).read_bytes(), b'')

    def test_build_uses_pinned_toolchain_and_frozen_lock(self):
        scratch = self.root / 'scratch'
        scratch.mkdir()
        source = scratch / 'source'
        p.extract_sources(self.repo, self.commit, source)
        with patch.object(p.shutil, 'which', side_effect=lambda name: '/tools/' + name), \
                patch.object(p.subprocess, 'check_output', side_effect=[b'v24.18.1\n', b'10.33.4\n',
                              str(self.root / 'shared-store/v10').encode()]), \
                patch.object(p.subprocess, 'run') as run:
            build = p.build_frontend(source, scratch, self.commit)
        commands = [c.args[0] for c in run.call_args_list]
        self.assertEqual(commands[0][1:3], ['install', '--frozen-lockfile'])
        self.assertEqual(commands[0][-2:], ['--store-dir', str(self.root / 'shared-store')])
        self.assertEqual(commands[1][1:], ['run', 'typecheck'])
        self.assertEqual(commands[2][1:], ['exec', 'vite', 'build', '--mode', 'production'])
        self.assertEqual(build['environment']['VITE_ACCESS_MODE'], 'frontend')
        self.assertTrue(all(c.kwargs['check'] for c in run.call_args_list))

    def test_failed_build_never_emits_archive(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.package(lambda *args: (_ for _ in ()).throw(subprocess.CalledProcessError(1, 'build')))
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
