"""Verification rejects stale release evidence and incompatible schema fields."""
import contextlib
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('verify', Path(__file__).with_name('management-verify.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class VerifyTests(unittest.TestCase):
    def test_contract_heartbeat_failure_is_bounded_and_not_silenced(self):
        with patch.object(verify.subprocess, 'check_output', side_effect=verify.subprocess.CalledProcessError(1, ['docker'])) as call, \
             patch.object(verify.time, 'sleep') as sleep:
            with self.assertRaises(verify.subprocess.CalledProcessError):
                verify.verify_contracts()
        self.assertEqual(call.call_count, 20)
        self.assertEqual(sleep.call_count, 19)

    def test_manifest_requires_each_of_three_prompt_resources(self):
        files = dict.fromkeys(verify.REQUIRED_PROMPTS, 'digest')
        verify.validate_prompt_manifest({'files': files})
        for name in files:
            with self.subTest(name=name), self.assertRaises(AssertionError):
                verify.validate_prompt_manifest({'files': {k:v for k,v in files.items() if k != name}})

    def test_kind_column_requires_nullable_varchar20(self):
        verify.validate_kind_column(lambda _: 'YES:character varying:20')
        for actual in ('', 'NO:character varying:20', 'YES:character varying:10', 'YES:text:'):
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                verify.validate_kind_column(lambda _: actual)

    def test_all_active_markers_must_match_every_manifest_field(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder)
            manifest = {'release': 'management-20261010-abcdef0', 'commit': 'abcdef0',
                'migration': '0026', 'frontendVersion': '0.2.20', 'files': {'prompt.txt': 'digest'}}
            names = ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json', 'MANAGEMENT_RELEASE.json')
            for name in names: (app / name).write_text(json.dumps(manifest))
            (app / 'API_SIZE_RELEASE.json').write_text('unchanged historical marker')
            verify.validate_release_markers(app, manifest)
            for name in names:
                for field in manifest:
                    with self.subTest(name=name, field=field):
                        (app / name).write_text(json.dumps({**manifest, field: 'stale'}))
                        with self.assertRaises(AssertionError): verify.validate_release_markers(app, manifest)
                        (app / name).write_text(json.dumps(manifest))


class MainTests(unittest.TestCase):
    def exercise(self, package_version='0.2.20', installed_only=False, corruption=None, paused=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'app'
            release = 'management-20261010-abcdef0'
            releases = root / 'releases'
            work = releases / release
            (work / 'src').mkdir(parents=True)
            contents = {
                'backend/app/main.py': b'# code',
                'backend/app/modules/api_image_edits/image_edit_prompt.txt': b'image',
                'backend/app/modules/api_image_edits/text_edit_prompt.txt': b'edit',
                'backend/app/modules/api_image_edits/text_repair_prompt.txt': b'repair',
                'frontend/package.json': json.dumps({'version': package_version}).encode(),
                'frontend/dist/index.html': b'<script src="/assets/main.js"></script><link href="/assets/main.css">',
                'frontend/dist/assets/main.js': b'console.log(1)',
                'frontend/dist/assets/main.css': b'body{}',
            }
            for name, raw in contents.items():
                target = app / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            manifest = {'release': release, 'commit': 'abcdef0', 'migration': '0026',
                'frontendVersion': '0.2.20', 'files': {
                    name: hashlib.sha256(raw).hexdigest() for name, raw in contents.items()}}
            (work / 'src/release.json').write_text(json.dumps(manifest))
            for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json', 'MANAGEMENT_RELEASE.json'):
                (app / name).write_text(json.dumps(manifest))
            names = ('api', 'outbox', 'api-image-worker', 'api-image-outbox', 'image-variants')
            (work / 'old-compose.private.json').write_text(json.dumps({'services': {
                name: {'environment': {'PRESERVED': '1'}, 'command': ['worker', name]} for name in names}}))
            (work / 'INSTALL_TEST_IMAGE_ID').write_text('verified-image')
            if corruption == 'installed_hash':
                (app / 'backend/app/main.py').write_bytes(b'corrupted')
            queries = []

            def command(args, input=None, text=True):
                if args[:2] == ('docker', 'inspect'):
                    name = args[2].removeprefix('hengxin-vps-staging-').removesuffix('-1')
                    self.assertIn(name, names)
                    return json.dumps([{'State': {'Running': True}, 'Image': 'verified-image',
                        'Config': {'Env': ['PRESERVED=1'], 'Cmd': ['worker', name]}}])
                if args[:3] == ('docker', 'exec', '-i'):
                    files = json.loads(input)
                    self.assertEqual(len(files), 4)
                    return str(len(files))
                if 'psql' in args:
                    query = args[-1]
                    queries.append(query)
                    if query == 'SELECT version_num FROM alembic_version': return '0026'
                    if "column_name='kind'" in query: return 'YES:character varying:20'
                    if 'information_schema.columns' in query: return 'YES'
                    if query == 'SELECT paused FROM api_image_channel WHERE id=1':
                        return 't' if (installed_only if paused is None else paused) else 'f'
                    if query == 'SELECT enabled FROM capacity_gate WHERE id=1': return 'f'
                    if 'count(*)' in query: return 'succeeded|3'
                if args == ('systemctl', 'is-active', 'hengxin-vps-codex-worker'): return 'active'
                if args[:2] == ('curl', '-fsS'): return '{"status":"ready"}'
                if args[:2] == ('curl', '-sS'):
                    self.assertFalse(installed_only, 'Installed verification must not access public auth')
                    return '200' if corruption == 'public_auth' else '401'
                self.fail('Unexpected command: ' + repr(args))

            def urlopen(url, timeout):
                self.assertFalse(installed_only, 'Installed verification must not access public assets')
                path = url.removeprefix('https://zhitu.qhhengxin.top')
                key = 'frontend/dist/' + ('index.html' if path == '/' else path.lstrip('/'))
                response = io.BytesIO(b'corrupted' if corruption == 'public_hash' else contents[key])
                response.status = 200
                return response

            output = io.StringIO()
            with patch.object(verify, 'Path', side_effect=lambda value: {
                    '/opt/hengxin-releases': releases, '/opt/hengxin-smart-image': app}[value]), \
                 patch.object(verify.sys, 'argv', ['verify', release] + (['--installed-only'] if installed_only else [])), \
                 patch.object(verify.subprocess, 'check_output', side_effect=command), \
                 patch.object(verify.urllib.request, 'urlopen', side_effect=urlopen), \
                 patch.object(verify, 'verify_contracts', return_value={'verified': True}), \
                 contextlib.redirect_stdout(output):
                verify.main()
            self.assertEqual(sum("column_name='kind'" in query for query in queries), 1)
            return json.loads(output.getvalue())

    def test_main_success_checks_services_native_resources_schema_and_public_assets(self):
        result = self.exercise()
        self.assertEqual(result['frontendVersion'], '0.2.20')
        self.assertEqual(result['schema'], '0026')
        self.assertEqual(result['hashes'], {'native': 4, 'frontend': 4})
        self.assertEqual(len(result['services']), 5)
        self.assertEqual(len(result['public']), 3)
        self.assertEqual(result['anonymousAuthStatus'], '401')

    def test_main_rejects_wrong_installed_frontend_package_version(self):
        with self.assertRaises(AssertionError):
            self.exercise(package_version='0.2.13')

    def test_installed_only_checks_hashes_and_services_without_public_requests(self):
        result = self.exercise(installed_only=True)
        self.assertEqual(result['verification'], 'installed-only')
        self.assertEqual(len(result['services']), 5)
        self.assertEqual(result['hashes'], {'native': 4, 'frontend': 4})
        self.assertNotIn('public', result)

    def test_installed_hash_corruption_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.exercise(installed_only=True, corruption='installed_hash')

    def test_modes_require_expected_intake_state(self):
        for installed in (True, False):
            with self.subTest(installed=installed), self.assertRaises(AssertionError):
                self.exercise(installed_only=installed, paused=not installed)

    def test_public_hash_and_auth_failures_are_rejected(self):
        for corruption in ('public_hash', 'public_auth'):
            with self.subTest(corruption=corruption), self.assertRaises(AssertionError):
                self.exercise(corruption=corruption)


if __name__ == '__main__': unittest.main()
