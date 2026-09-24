"""Exercise the actual recovery function using shell stubs, never production commands."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def verify(source):
    script = source.read_text()
    recovery = 'recover() {' + script.split('recover() {', 1)[1].split('\ntrap recover ERR INT TERM', 1)[0]
    stub = r'''
set +e
release=test
work=.
backup=./backup
app=./app
native=./native
helper=./helper
wait_seconds=1
closed=1
api_started=1
native_changed=1
native_stopped=1
backed=1
old=(fake_compose)
new=(fake_compose)
record() { printf '%s\n' "$*" >> "$TEST_LOG"; }
fake_compose() {
  record "compose $*"
  if [[ "$FAIL_AT" = old_start && "$1" = up && "$*" = *api-image-worker* ]]; then return 1; fi
  if [[ "$FAIL_AT" = web_start && "$1" = up && "$*" = *web* ]]; then return 1; fi
}
sql() { record "sql $*"; }
docker() { record "docker $*"; if [[ "$1" = inspect ]]; then echo true; fi; }
systemctl() { record "systemctl $*"; if [[ "$1" = show ]]; then echo active; fi; }
api_control() { record "api_control $*"; [[ "$FAIL_AT" != "$1" ]]; }
python3() { record "python3 $*"; [[ "$FAIL_AT" != native_verify || "$2" != run-native-verify ]]; }
tar() {
  record "tar $*"
  [[ "$FAIL_AT" != native_restore || "$*" != *native.tar* ]] || return 1
  [[ "$FAIL_AT" != app_restore || "$*" != *application.tar* ]]
}
cp() { record "cp $*"; }
rm() { record "rm $*"; }
curl() { record "curl $*"; [[ "$FAIL_AT" != health ]]; }
verify_old_services() { record verify_old_services; [[ "$FAIL_AT" != old_verify ]]; }
'''
    failures = ['api-drain', 'native_restore', 'app_restore', 'old_start', 'old_verify', 'api-resume', 'api-verify', 'native_verify', 'health']
    with tempfile.TemporaryDirectory(prefix='hx-recovery-test-') as temporary:
        root = Path(temporary)
        for case in ['success', *failures, 'web_start']:
            log = root / (case + '.log')
            result = subprocess.run(['bash'], input=stub + recovery + '\nfalse\nrecover\n', text=True,
                                    cwd=root, env={**os.environ, 'TEST_LOG': str(log), 'FAIL_AT': case},
                                    capture_output=True, timeout=10)
            assert result.returncode == 1, (case, result.stdout, result.stderr)
            lines = log.read_text().splitlines()
            opened = [line for line in lines if 'paused=false' in line]
            web = [line for line in lines if line.startswith('compose up') and line.endswith(' web')]
            if case == 'success':
                assert opened and web, lines
                for step in ['verify_old_services', 'api_control api-verify', 'python3 ./helper run-native-verify 90']:
                    assert lines.index(step) < lines.index(opened[0]), (case, lines)
                assert 'ROLLBACK_BLOCKED' not in result.stdout
            elif case == 'web_start':
                assert lines[-2:] == ['compose stop -t 30 web api outbox api-image-outbox', 'sql update api_image_channel set paused=true where id=1'], lines
            else:
                assert not opened and not web, (case, lines)
                assert 'ROLLBACK_BLOCKED_NO_AUTOMATIC_REOPEN' in result.stdout
            print('PASS', case)


if __name__ == '__main__':
    verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('image-inputs-deploy.sh'))
