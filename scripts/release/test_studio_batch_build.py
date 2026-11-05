"""Build-source isolation and fail-closed package provenance checks."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from test_studio_batch_recovery import load

b = load('studio-batch-build')
r = load('studio-batch-runtime').r


class BuildTests(unittest.TestCase):
    def test_cleanup_removes_real_dependency_paths_beyond_windows_max_path(self):
        with b.build_directory() as root:
            nested = root/('dependency-'+'a'*60)/('dependency-'+'b'*60)/('dependency-'+'c'*60)
            path = Path('\\\\?\\'+str(nested)) if os.name == 'nt' else nested
            path.mkdir(parents=True)
            (path/'file.d.ts').write_text('nested dependency')
            self.assertGreater(len(str(nested/'file.d.ts')),260)
        self.assertFalse(root.exists())

    def test_cleanup_retries_only_its_created_directory(self):
        actual = b.shutil.rmtree
        seen = []
        def remove(root):
            seen.append(root)
            if len(seen) == 1:
                raise OSError('Windows directory temporarily busy')
            return actual(root)
        with patch.object(b.shutil,'rmtree',side_effect=remove),patch.object(b.time,'sleep'):
            with b.build_directory() as root:
                (root/'artifact').write_text('local')
            self.assertFalse(root.exists())
            self.assertEqual(len(seen),2)
            self.assertTrue(all(str(path).removeprefix('\\\\?\\') == str(root) for path in seen))

    def exercise(self, failure=False, tamper=False, drift=False):
        archive = io.BytesIO()
        package = {'engines':{'node':'24.18.1','pnpm':'10.33.4'}}
        with zipfile.ZipFile(archive,'w') as stream:
            for name,content in {'package.json':json.dumps(package),'pnpm-lock.yaml':'locked deps',
                'source.js':'current committed application'}.items():
                stream.writestr(b.PREFIX+name,content)
        commands = []
        def git(repo,*args):
            return archive.getvalue() if args[0] == 'archive' else b'c'*40
        actual_run = subprocess.run
        def run(args,**kwargs):
            commands.append(args)
            self.assertNotIn('VITE_API_URL',kwargs['env'])
            self.assertNotIn('NODE_OPTIONS',kwargs['env'])
            if args[1] == '--version':
                return subprocess.CompletedProcess(args,0,b'v24.18.1' if args[0] == 'node' else b'10.33.4')
            if args[1] == 'install':
                self.assertEqual(args[2:],('--frozen-lockfile','--prefer-offline','--prod=false'))
                return subprocess.CompletedProcess(args,0,b'locked installation\n')
            self.assertEqual(args[1:],('run','build'))
            self.assertFalse((kwargs['cwd']/'dist').exists())
            # Execute a real isolated builder; only pnpm/version transport is substituted.
            code = ('from pathlib import Path; p=Path("dist/assets"); p.mkdir(parents=True); '
                'Path("dist/index.html").write_text(\'<script src="/assets/current.js"></script>\'); '
                '(p/"current.js").write_bytes(Path("source.js").read_bytes()); ')
            if tamper:
                code += 'Path("source.js").write_text("changed during build"); '
            if failure:
                code += 'raise SystemExit(1)'
            return actual_run((sys.executable,'-c',code),**kwargs)
        collections = []
        def collect(dist):
            self.assertNotEqual(dist,workspace/'hengxin-smart-image/frontend/dist')
            assets = {'frontend/dist/'+p.relative_to(dist).as_posix():p.read_bytes()
                for p in dist.rglob('*') if p.is_file()}
            collections.append(assets)
            if drift and len(collections) == 1:
                (dist/'assets/current.js').write_text('tampered output')
            return assets
        helper = lambda name:SimpleNamespace(git=git) if name == 'package-delivery' else SimpleNamespace(collect_assets=collect)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            old = workspace/'hengxin-smart-image/frontend/dist'
            old.mkdir(parents=True)
            (old/'index.html').write_text('old build must not be packaged')
            with patch.object(r,'helper',side_effect=helper),patch.object(b.shutil,'which',return_value='pnpm'), \
                patch.object(b.subprocess,'run',side_effect=run), \
                patch.dict(os.environ,{'VITE_API_URL':'https://untrusted.invalid','NODE_OPTIONS':'untrusted'}):
                if failure or tamper or drift:
                    with self.assertRaisesRegex(RuntimeError,'command failed' if failure else 'source changed' if tamper else 'build changed'):
                        b.build(workspace,'a'*40,r)
                else:
                    assets,proof,log = b.build(workspace,'a'*40,r)
                    self.assertEqual(assets['frontend/dist/assets/current.js'],b'current committed application')
                    self.assertEqual(proof['commit'],'a'*40)
                    self.assertEqual(proof['sourceTree'],'c'*40)
                    self.assertEqual(set(proof['files']),set(assets))
                    self.assertIn(b'locked installation',log)
            self.assertEqual((old/'index.html').read_text(),'old build must not be packaged')
        self.assertEqual(len(commands),4)

    def test_old_workspace_dist_is_ignored_and_fixed_source_is_built(self):
        self.exercise()

    def test_build_failure_never_falls_back_to_existing_dist(self):
        self.exercise(failure=True)

    def test_source_mutation_during_build_is_rejected(self):
        self.exercise(tamper=True)

    def test_dist_mutation_during_collection_is_rejected(self):
        self.exercise(drift=True)


if __name__ == '__main__':
    unittest.main()
