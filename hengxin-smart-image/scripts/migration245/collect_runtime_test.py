from pathlib import Path
import tempfile
import unittest

from collect_runtime import file_hashes


class CodeInventoryTests(unittest.TestCase):
    def test_execution_source_is_kept_and_root_runtime_data_is_excluded(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            keep = ('app/execution/worker.py', 'app/overseas/execution/worker.py',
                    'app/sessions/router.py', 'pyproject.toml')
            excluded = ('execution/task.json', 'runtime/history.json', '.venv/site.py',
                        'app/__pycache__/worker.pyc', '.codex/auth.json', 'grants/auth.json')
            for name in keep + excluded:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'fixture')
            actual = {Path(p).relative_to(root).as_posix() for p in file_hashes({str(root)})}
            self.assertEqual(actual, set(keep))


if __name__ == '__main__':
    unittest.main()
