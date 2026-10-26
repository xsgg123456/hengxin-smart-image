"""Validate immutable installed daemon sources and API images before service changes."""
from pathlib import Path


def test_installed(work, data, test_python, runtime):
    r = runtime
    host = Path(data['host']) / 'daemon'
    output = r.run('/usr/sbin/runuser', '-u', 'codex', '--', '/usr/bin/python3', '-B', '-m',
                   'app.account_management.service', '--help', cwd=host)
    r.require(all(x in output for x in ('--root', '--legacy-source', '--runtime', '--binary', '--bwrap', '--api-uid')),
              'Installed daemon CLI mismatch')
    r.require(test_python and Path(test_python).is_file(), 'An isolated pytest Python runtime is required')
    uid_test = 'test_real_two_worker_uids_share_access_without_reading_master'
    test_env = {'PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONPATH':str(host),'PYTHONDONTWRITEBYTECODE':'1'}
    output = r.run('/usr/sbin/runuser', '-u', 'codex', '--', str(test_python), '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   str(Path(data['host'])/'tests'), '-k', 'not ' + uid_test, cwd=host, timeout=180, env=test_env)
    r.require('passed' in output and 'failed' not in output and 'skipped' not in output, 'Installed Linux account tests incomplete')
    # This test must start as root to switch to real worker UIDs; it only uses temporary fixtures.
    uid_output = r.run(str(test_python), '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                      str(Path(data['host'])/'tests/test_credential_broker.py') + '::' + uid_test,
                      cwd=host, timeout=30, env=test_env)
    r.require('1 passed' in uid_output and 'skipped' not in uid_output, 'Real UID isolation test incomplete')
    output += '\nRoot-only UID isolation:\n' + uid_output
    r.private(work / 'installed-linux-tests.txt', output)
    # No production mounts, tokens, network or business DB in installation tests.
    for domain, saved in data['apis'].items():
        r.require(r.api_hashes(saved['image']) == {n:e['sha256'] for n,e in saved['files'].items()}, 'Installed API drift')
        env = ['-e', 'HX_BUSINESS_CONTEXT=' + domain]
        code = ("from app.account_management.router import router; from app.account_management.schemas import Account; "
                "from app.core.config import Settings; assert 'codex_account_management_socket' in Settings.model_fields; "
                "assert len(router.routes)==8; print('INSTALLED_API_IMPORT_PASS')")
        output = r.run('docker', 'run', '--rm', '--network=none', '--read-only', *env, '--entrypoint', 'python',
                       saved['image'], '-B', '-c', code)
        r.require(output == 'INSTALLED_API_IMPORT_PASS', 'Installed API import failed')
    r.private(work / 'INSTALL_TESTS_PASSED', dict(manifest=data['manifest'], images={d:v['image'] for d,v in data['apis'].items()}))
    return 'INSTALLED_DAEMON_AND_API_IMPORTS_PASS'

