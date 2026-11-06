"""Real Linux Bubblewrap probes; shell fixtures never call Codex or a model."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.execution.workspace import sandbox_command
from test_studio_skill_cache import fingerprint, new_workspace, prepare, source  # noqa: F401

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Real Linux Bubblewrap verification')


def test_real_sandbox_readonly_current_skill_and_history(tmp_path, source):
    executable = os.environ.get('HENGXIN_TEST_BWRAP', '/opt/hengxin-runtime/bwrap')
    if not Path(executable).is_file():
        executable = shutil.which('bwrap')
    if executable is None:
        pytest.fail('Linux release verification requires an installed Bubblewrap')
    first = new_workspace(tmp_path)
    old = prepare(first, source.skill('A', files={'SKILL.md': 'old-version'}))
    session = first.home / '.codex/sessions/history.jsonl'
    session.parent.mkdir()
    session.write_bytes(b'full-history-not-a-summary\n')
    work = first.work / 'existing-work.txt'
    work.write_bytes(b'previous-user-work\n')
    old_round = first.round_work / 'output.png'
    old_round.write_bytes(b'previous-output-image\x00\xff')
    current = new_workspace(tmp_path, first.home.parent.name)
    selected = prepare(current, source.skill('B', files={'SKILL.md': 'selected-version'}))
    cache_before = fingerprint(selected.parent.parent)
    preserved = {path: path.read_bytes() for path in (session, work, old_round)}
    binary = tmp_path / 'codex'
    helper = tmp_path / 'codex-code-mode-host'
    helper.write_text('#!/bin/sh\nexit 97\n')
    helper.chmod(0o755)
    binary.write_text('''#!/bin/sh
set -eu
[ "$(id -u)" = "$1" ]
[ "$(cat /work/existing-work.txt)" = 'previous-user-work' ]
[ "$(cat /home/runner/.codex/sessions/history.jsonl)" = 'full-history-not-a-summary' ]
[ ! -e "$2" ]
[ ! -e /work/skills/A ]
[ ! -e /home/runner/.agents/skills/A ]
if [ "$3" = selected ]; then
  [ "$(cat /work/skills/B/SKILL.md)" = 'selected-version' ]
  [ "$(cat /home/runner/.agents/skills/B/SKILL.md)" = 'selected-version' ]
  if (printf changed > /work/skills/B/SKILL.md) 2>/dev/null; then exit 21; fi
  if (touch /work/skills/B/new-file) 2>/dev/null; then exit 22; fi
  if (printf changed > /home/runner/.agents/skills/B/SKILL.md) 2>/dev/null; then exit 23; fi
else
  [ -z "$(ls -A /work/skills)" ]
  [ -z "$(ls -A /home/runner/.agents)" ]
fi
if (mkdir /work/skills/other) 2>/dev/null; then exit 24; fi
printf 'sandbox-ok uid=%s mode=%s\n' "$(id -u)" "$3"
''')
    binary.chmod(0o755)
    for mode in ('selected', 'none'):
        if mode == 'none':
            prepare(current, None)
        argv = sandbox_command(current, binary,
                               [str(os.getuid()), str(old.parent.parent), mode], bwrap=executable)
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert f'sandbox-ok uid={os.getuid()} mode={mode}' in result.stdout
        assert fingerprint(selected.parent.parent) == cache_before
        assert all(path.read_bytes() == value for path, value in preserved.items())
