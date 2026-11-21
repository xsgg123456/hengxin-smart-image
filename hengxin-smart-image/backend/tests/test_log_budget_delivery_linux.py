"""Both business runners must publish late image links after a noisy CLI invocation."""
import json
import sys

import pytest
from sqlalchemy import select

from app.execution.process import execute
from app.models import Job
from app.modules.domestic_studio import runner as domestic_runner
from app.modules.domestic_studio.turn_models import Picture, Transcript, Turn
from app.overseas.execution import runner as overseas_runner
from files_helpers import image_bytes
from studio_delivery_helpers import DeliveryCase, materials, overseas, studio
from test_domestic_files_pg import Store
from test_domestic_runner_pg import prepare
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='CLI uses POSIX process groups')
FINAL = '![Final](/work/final.png)'

# Each diagnostic block is exactly one MiB. Use printable non-Base64 text
# so that payload stripping alone cannot make this a below-budget test.
CHILD = """
import json, sys, time
from pathlib import Path
def event(**fields):
    print(json.dumps(fields), flush=True)
event(type='thread.started', thread_id='session-123')
event(type='turn.started')
line = (b'writer: step OK ' * 256)[:-1] + b'\\n'
block = line * 256
assert len(block) == 1048576
if sys.argv[4] == 'commands':
    diagnostic = 'step: ok ' * 32768
    for index in range(1028):
        event(type='item.completed', item=dict(type='command_execution', id=f'cmd-{index}',
              command='inspect final.png', aggregated_output=diagnostic, status='completed'))
else:
    for _ in range(257):
        sys.stderr.buffer.write(block)
sys.stderr.buffer.flush()
# Keep the child alive across the legacy runner's 200 ms limit check.
time.sleep(0.6)
Path(sys.argv[1]).write_bytes(bytes.fromhex(sys.argv[2]))
event(type='item.completed', item=dict(type='agent_message', id='reply', text=sys.argv[3]))
event(type='turn.completed', usage=dict(input_tokens=2, output_tokens=3))
"""


def noisy_cli(calls, source):
    def run(_command, prompt, control, timeout, monitor, started):
        calls.append(control)
        image = control.parents[1] / 'persistent' / 'work' / 'final.png'
        child = [sys.executable, '-c', CHILD, str(image), image_bytes().hex(), FINAL, source]
        return execute(child, prompt, control, timeout, monitor, started)
    return run


def check_log(calls):
    control, = calls
    with (control / 'events.jsonl').open(encoding='utf-8') as stream:
        types = [json.loads(line)['type'] for line in stream]
    assert types.count('platform.log_compacted') == 1
    assert types[-1] == 'turn.completed'
    stats = json.loads((control / 'detail-summary.json').read_text())
    assert stats['rawBytes'] > 256 * 1024 * 1024 and stats['omittedRecords'] > 0
    assert json.loads((control / 'exit.json').read_text())['exit_code'] == 0
    detailed = [p for p in control.iterdir() if p.is_file()
                and (p.name.startswith('detail') or p.name == 'stderr.log')]
    assert sum(p.stat().st_size for p in detailed) <= 128 * 1024 * 1024


def test_overseas_delivers_and_downloads_image_after_257_mib(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    calls = []
    monkeypatch.setattr(overseas_runner, 'execute', noisy_cli(calls, 'commands'))
    case.run()
    case.run()
    check_log(calls)
    case.complete(1)
    assert case.current()['reply'] == FINAL
    assert case.downloaded() == [image_bytes()]


def test_domestic_commits_image_and_notice_after_257_mib(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls, store = [], Store()
    monkeypatch.setattr(domestic_runner, 'execute', noisy_cli(calls, 'stderr'))
    for _ in range(2):
        domestic_runner.run_turn(job_id, factory, store=store, catalog=catalog)
    check_log(calls)
    with factory() as session:
        job = session.get(Job, job_id)
        assert job.status == 'succeeded' and job.execution_count == 1
        assert session.scalar(select(Turn)).reply == FINAL
        assert any('精简' in row.text for row in session.scalars(select(Transcript)))
        picture = session.scalars(select(Picture)).one()
        assert store.objects[(picture.bucket, picture.object_key)] == image_bytes()
