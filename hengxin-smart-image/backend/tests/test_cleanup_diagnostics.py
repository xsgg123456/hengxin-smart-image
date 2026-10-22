"""Operational failures stay useful without logging SQL, private paths or payloads."""
import errno
import json
import logging
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from app.execution.cleanup_diagnostics import report, ThumbnailOwnershipUnresolved
from app.execution.cleanup_paths import CleanupSafetyError


@pytest.mark.parametrize('error,stage,expected', [
    (CleanupSafetyError('UNEXPECTED_LINK'), 'history_filesystem', 'CLEANUP_UNEXPECTED_LINK'),
    (CleanupSafetyError('CROSS_DEVICE'), 'cache_filesystem', 'CLEANUP_CROSS_DEVICE'),
    (PermissionError(errno.EACCES, 'secret', '/private/auth.json'), 'history_filesystem',
     'CLEANUP_PERMISSION_DENIED'),
    (OSError('secret'), 'cache_filesystem', 'CLEANUP_IO_FAILED'),
    (OSError('secret'), 'object_remove', 'CLEANUP_OBJECT_STORAGE_FAILED'),
    (ThumbnailOwnershipUnresolved('secret'), 'history_database', 'CLEANUP_THUMBNAIL_BUSY'),
    (IntegrityError('private SQL', {'token': 'secret'}, Exception('secret')),
     'history_database', 'CLEANUP_DATABASE_CONSTRAINT'),
    (OperationalError('private SQL', {'token': 'secret'}, Exception('secret')),
     'scan', 'CLEANUP_DATABASE_FAILED'),
    (RuntimeError('secret'), 'task_delete', 'CLEANUP_UNEXPECTED_FAILURE'),
])
def test_failure_codes_never_emit_exception_payload(caplog, error, stage, expected):
    identifier = uuid4()
    with caplog.at_level(logging.ERROR, logger='app.execution.cleanup_diagnostics'):
        assert report(error, stage=stage, resource_id=identifier) == expected
    record = caplog.records[-1]
    payload = json.loads(record.getMessage().removeprefix('cleanup_deferred '))
    assert payload['resourceId'] == str(identifier)
    assert payload['stage'] == stage and payload['code'] == expected
    assert record.exc_info is None
    assert all(value not in record.getMessage() for value in ('secret', 'private', 'auth.json'))


@pytest.mark.parametrize('state', ['55P03', '40P01', '40001'])
def test_database_contention_has_stable_code(caplog, state):
    original = Exception('private DSN and SQL parameters')
    original.sqlstate = state
    error = OperationalError('SQL', {'token': 'secret'}, original)
    assert report(error, stage='history_database', resource_id=uuid4()) == 'CLEANUP_DATABASE_BUSY'
    assert 'secret' not in caplog.text and 'DSN' not in caplog.text


def test_unknown_context_and_exception_chain_are_sanitized(caplog):
    try:
        try:
            raise RuntimeError('secret-inner')
        except RuntimeError as inner:
            raise ValueError('secret-outer') from inner
    except ValueError as error:
        report(error, stage='private-path', resource_id='secret-id')
    payload = json.loads(caplog.records[-1].getMessage().removeprefix('cleanup_deferred '))
    assert payload['stage'] == 'worker_loop' and payload['resourceId'] == 'unknown'
    assert payload['locations'] == []  # Test paths outside app are not exported.
    assert 'secret' not in caplog.text and 'private-path' not in caplog.text


@pytest.mark.parametrize('deletions_only', [False, True])
def test_once_worker_exits_nonzero_without_raw_exception_traceback(deletions_only):
    script = '''
import sys
from types import SimpleNamespace
from sqlalchemy.exc import OperationalError
from app.retention import worker
from app.modules.api_image_edits import deletion
def fail(*args, **kwargs):
    raise OperationalError('synthetic_private_SQL', {'token': 'synthetic_secret_token'},
                           RuntimeError('synthetic_private_DSN'))
worker.run_once = fail
worker.session_factory = lambda: None
worker.get_store = lambda: None
deletion.run_pending = fail
worker.execute_loop(SimpleNamespace(once=True, deletions_only=sys.argv[1] == 'True', interval=1))
'''
    result = subprocess.run([sys.executable, '-c', script, str(deletions_only)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert 'CLEANUP_DATABASE_FAILED' in result.stderr
    assert all(secret not in result.stderr + result.stdout for secret in (
        'synthetic_private_SQL', 'synthetic_secret_token', 'synthetic_private_DSN', 'Traceback'))


@pytest.mark.parametrize('failure', ['heartbeat', 'shutdown', 'settings', 'factory'])
def test_main_lifecycle_never_emits_sensitive_traceback(failure):
    script = '''
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from sqlalchemy.exc import OperationalError
from app.retention import worker, service
failure = sys.argv[1]
def fail(*args, **kwargs):
    raise OperationalError('synthetic_private_SQL', {'token': 'synthetic_secret_token'},
                           RuntimeError('synthetic_private_DSN'))
worker.get_settings = lambda: SimpleNamespace(cli_retention_enabled=True)
worker.session_factory = lambda: None
worker.run_once = lambda: {'status': 'completed'}
service.heartbeat = lambda *args, **kwargs: None
if failure == 'heartbeat':
    service.heartbeat = fail
elif failure == 'settings':
    worker.get_settings = fail
elif failure == 'factory':
    worker.session_factory = fail
else:
    @contextmanager
    def closing(*args):
        yield
        fail()
    service.beating = closing
sys.argv = ['retention', '--once']
worker.main()
'''
    result = subprocess.run([sys.executable, '-c', script, failure],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert 'CLEANUP_DATABASE_FAILED' in result.stderr and 'worker_lifecycle' in result.stderr
    assert all(secret not in result.stderr + result.stdout for secret in (
        'synthetic_private_SQL', 'synthetic_secret_token', 'synthetic_private_DSN', 'Traceback'))
