"""Real Linux processes; these are explicitly not validated by Windows runs."""
import json
import os
from pathlib import Path
import sys

import pytest

from app.execution.process import execute, same_process

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Requires Linux /proc and POSIX process groups')


@pytest.mark.parametrize('reason', ['timeout', 'cancelled'])
def test_real_sleep_process_is_stopped_and_receipt_persisted(tmp_path, reason):
    identities = []
    receipt = execute([sys.executable, '-c', 'import time; time.sleep(120)'],
                      'test input', tmp_path, .2 if reason == 'timeout' else 120,
                      lambda: reason == 'cancelled', lambda *identity: identities.append(identity))
    assert receipt['reason'] == reason
    assert receipt['exit_code'] != 0
    assert receipt['elapsed_seconds'] < 10
    assert len(identities) == 1 and not same_process(*identities[0])
    assert json.loads((tmp_path / 'exit.json').read_text()) == receipt


def test_real_process_gets_prompt_via_stdin_without_shell_interpolation(tmp_path):
    prompt = '$(touch should-not-exist); "quoted"\nsecond line'
    receipt = execute([sys.executable, '-c', 'import sys; print(sys.stdin.read(), end="")'],
                      prompt, tmp_path, 10, lambda: False, lambda *identity: None)
    assert receipt['reason'] is None and receipt['exit_code'] == 0
    assert (tmp_path / 'events.jsonl').read_text() == prompt
