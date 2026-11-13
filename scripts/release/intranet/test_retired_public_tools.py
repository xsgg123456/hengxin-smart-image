"""Retirement must leave LAN and migration regression imports usable without commands."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def test_migration_backup_import_does_not_execute_commands():
    path = ROOT / 'scripts/release/retirement-backup.py'
    spec = importlib.util.spec_from_file_location('retired_backup_regression', path)
    module = importlib.util.module_from_spec(spec)
    with patch('subprocess.run', side_effect=AssertionError('Import executed a command')):
        spec.loader.exec_module(module)
        assert module.contract(ROOT / 'hengxin-smart-image')['version'] == 1
        assert module.projection('system_settings', {}) == 'to_jsonb(t)'


def test_old_worker_control_entry_refuses():
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/release/image-inputs-worker.py'),
                             'native-stop', '0'], capture_output=True)
    assert result.returncode != 0
    assert b'scripts/release/intranet/release.py' in result.stderr
    assert b'--scope' in result.stderr
