import importlib.util
import gzip
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package', Path(__file__).with_name('package-management.py'))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_static_assets_closed_allowlist_and_compressed_privacy(self):
        package.audit_asset('frontend/dist/main.css', b':root{--el-mask-color-extra-light:white}')
        package.audit_asset('frontend/dist/icon.png', b'\x89PNG\r\n\x1a\n\xff')
        with self.assertRaises(ValueError):
            package.audit_asset('frontend/dist/icon.png', b'\x89PNG' + ('sk-' + 'x' * 30).encode())
        for name in ('.env', 'credentials', 'auth.json', 'session.js', 'a.map', 'a.db', 'x.txt.gz'):
            with self.assertRaises(ValueError): package.audit_asset('frontend/dist/' + name, b'x')
        package.audit_asset('frontend/dist/assets/main.js.gz', gzip.compress(b'console.log(1)'))
        with self.assertRaises(ValueError):
            package.audit_asset('frontend/dist/assets/main.js.gz', gzip.compress(('sk-' + 'x' * 30).encode()))

    def test_allowlist_excludes_secrets_runtime_and_source_frontend(self):
        for name in ('backend/.env', 'backend/users.db', 'frontend/src/main.ts', 'backend/auth.json'):
            self.assertIsNone(package.selected('hengxin-smart-image/' + name))
        self.assertEqual(package.selected('hengxin-smart-image/backend/app/main.py'), 'backend/app/main.py')
        self.assertEqual(package.selected('scripts/release/management-deploy.py'), 'scripts/release/management-deploy.py')

    def test_privacy_and_archive_verification(self):
        with self.assertRaises(ValueError):
            package.common.privacy_check('frontend/dist/index.js', ('sk-' + 'x' * 30).encode())
        self.assertGreater(len(package.archive_bytes({'x/a.py': b'print(1)', 'index.html': b'<html/>'})), 0)
        with self.assertRaises(ValueError): package.archive_bytes({'../outside': b'x'})

    def test_only_preexisting_unstaged_skill_edit_is_allowed(self):
        package.require_clean_tracked(lambda *_: b' M .agents/skills/dev-builder/SKILL.md\n')
        self.assertIsNone(package.selected('.agents/skills/dev-builder/SKILL.md'))
        for status in (b'M  .agents/skills/dev-builder/SKILL.md', b' M backend/app/main.py', b' M .agents/skills/dev-builder/SKILL.md\n M other.py'):
            with self.assertRaises(ValueError):
                package.require_clean_tracked(lambda *_: status)

    def test_dirty_tracked_tree_rejected_before_review(self):
        original = package.common.git
        package.common.git = lambda *_: b' M file.py'
        try:
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ValueError, 'Commit tracked'):
                    package.build(Path(folder))
        finally:
            package.common.git = original


    def test_migration_version_and_helpers_are_required(self):
        files = {'infra/nginx.vps.conf': b'nginx', 'infra/nginx.media.conf': b'nginx',
                 'backend/app/modules/api_image_edits/image_edit_prompt.txt': b'image',
                'backend/app/modules/api_image_edits/text_edit_prompt.txt': b'edit',
                 'backend/app/modules/api_image_edits/text_repair_prompt.txt': b'repair',
                 'backend/migrations/versions/0023_api_cli_conversations.py': b'',
                 'frontend/package.json': b'{"version":"0.2.20"}',
                 **{'scripts/release/' + n: b'' for n in ('management-deploy.py', 'management-runtime.py', 'management-verify.py', 'image-inputs-worker.py')}}
        files.update({'backend/migrations/versions/' + n: b'' for n in ('0024_cli_retention.py', '0025_api_usage_facts.py', '0026_api_worker_heartbeat.py')})
        files.update({'backend/app/' + n: b'' for n in ('retention/worker.py', 'modules/management/api_stats/backfill.py', 'modules/management/api_usage.py', 'modules/management/api_monitor.py', 'modules/management/execution_settings.py')})
        package.validate(files)
        for name in files:
            with self.assertRaises((AssertionError, KeyError)):
                package.validate({k:v for k,v in files.items() if k != name})
        files['frontend/package.json'] = b'{"version":"0.2.10"}'
        with self.assertRaises(AssertionError): package.validate(files)

if __name__ == '__main__': unittest.main()
