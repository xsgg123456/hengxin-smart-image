import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from conftest import seed
from member_codec import read_json, write_json
from test_member_maintenance import approve, count

SCRIPTS = Path(__file__).resolve().parents[1]


def invoke(script, args, environment):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], env=environment,
                          text=True, capture_output=True, check=False, timeout=30)


def test_cli_audit_dry_run_apply_and_restore(database, tmp_path):
    engine, business, tables = database
    seed(engine, tables, business)
    env = {**os.environ, 'ISOLATED_MEMBER_TEST_URL': str(engine.url)}
    common = ['--business', business, '--database-url-env', 'ISOLATED_MEMBER_TEST_URL']
    audit_file, approved_file, output = tmp_path / 'audit.json', tmp_path / 'approved.json', tmp_path / 'result.json'
    result = invoke('audit-business-members.py', [*common, '--output', str(audit_file)], env)
    assert result.returncode == 0, result.stderr
    write_json(approved_file, approve(read_json(audit_file)))
    args = [*common, '--approved-list', str(approved_file), '--output', str(output)]
    result = invoke('reconcile-business-members.py', args, env)
    assert result.returncode == 0, result.stderr
    assert read_json(output)['results'][0]['outcome'] == 'would_delete'
    assert count(engine, tables['member']) == 1
    result = invoke('reconcile-business-members.py', [*args, '--apply', '--recovery-dir', str(tmp_path / 'recovery')], env)
    assert result.returncode == 0, result.stderr
    report = read_json(output)
    assert report['results'][0]['outcome'] == 'deleted'
    recovery_file = report['results'][0]['recoveryFile']
    result = invoke('reconcile-business-members.py', [*common, '--restore', recovery_file, '--apply', '--output', str(output)], env)
    assert result.returncode == 0, result.stderr
    assert read_json(output)['outcome'] == 'restored'


def test_cli_never_prints_database_credentials_or_exception_parameters(tmp_path):
    env = {**os.environ, 'ISOLATED_MEMBER_TEST_URL': 'postgresql+psycopg://person:do-not-leak@127.0.0.1:1/isolated_test?connect_timeout=1'}
    result = invoke('audit-business-members.py', ['--business', 'domestic', '--database-url-env',
        'ISOLATED_MEMBER_TEST_URL', '--output', str(tmp_path / 'report.json')], env)
    assert result.returncode == 2
    assert 'do-not-leak' not in result.stdout + result.stderr
    assert '127.0.0.1' not in result.stdout + result.stderr
    assert 'Traceback' not in result.stderr


def test_cli_requires_explicit_business_and_named_database(tmp_path):
    result = invoke('audit-business-members.py', ['--output', str(tmp_path / 'report.json')], os.environ)
    assert result.returncode == 2
    assert '--business' in result.stderr and '--database-url-env' in result.stderr
