"""A follow-up physical release must preserve the exact existing history bind."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('physical', Path(__file__).with_name('skill-physical-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ExistingHistoryBindTests(unittest.TestCase):
    def setUp(self):
        self.mount = dict(type='bind', source=p.EXECUTION_ROOT, target=p.EXECUTION_ROOT,
                          read_only=False, bind={'create_host_path': True})
        self.before = {'services': {'api': {'image': 'old-api'}, 'skill-publisher': {
            'image': 'old-publisher', 'user': '0:0',
            'environment': {'OVERSEAS_CODEX_EXECUTION_ROOT': p.EXECUTION_ROOT},
            'volumes': [copy.deepcopy(self.mount)]}}}
        self.images = dict(api='new-api', publisher='new-publisher')

    def updated(self):
        after = copy.deepcopy(self.before)
        overlay = p.overlay(self.before, self.images)
        self.assertEqual(overlay['services']['skill-publisher']['volumes'], [])
        after['services']['api']['image'] = self.images['api']
        after['services']['skill-publisher']['image'] = self.images['publisher']
        return after

    def test_upgrade_keeps_exact_bind_without_duplication(self):
        after = self.updated()
        p.check_overlay(self.before, after, self.images)
        self.assertEqual(after['services']['skill-publisher']['volumes'], [self.mount])

    def test_invalid_existing_source_type_permissions_or_environment_rejected(self):
        for field, value in (('source', '/tmp/empty'), ('type', 'volume'), ('read_only', True)):
            before = copy.deepcopy(self.before)
            before['services']['skill-publisher']['volumes'][0][field] = value
            with self.assertRaisesRegex(RuntimeError, 'invalid identity'):
                p.overlay(before, self.images)
        self.before['services']['skill-publisher']['environment']['OVERSEAS_CODEX_EXECUTION_ROOT'] = '/tmp/empty'
        with self.assertRaisesRegex(RuntimeError, 'invalid identity'):
            p.overlay(self.before, self.images)

    def test_duplicate_existing_bind_rejected(self):
        self.before['services']['skill-publisher']['volumes'].append(copy.deepcopy(self.mount))
        with self.assertRaisesRegex(RuntimeError, 'invalid identity'):
            p.overlay(self.before, self.images)

    def test_existing_bind_options_cannot_change(self):
        after = self.updated()
        after['services']['skill-publisher']['volumes'][0]['bind']['create_host_path'] = False
        with self.assertRaisesRegex(RuntimeError, 'options changed'):
            p.check_overlay(self.before, after, self.images)

    def test_unrelated_api_mount_cannot_change(self):
        after = self.updated()
        after['services']['api']['volumes'] = [self.mount]
        with self.assertRaisesRegex(RuntimeError, 'Unrelated'):
            p.check_overlay(self.before, after, self.images)


if __name__ == '__main__':
    unittest.main()
