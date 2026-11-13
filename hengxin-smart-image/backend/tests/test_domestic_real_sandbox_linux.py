"""Exercise the real Linux sandbox and executor with a local, non-model CLI stub."""
import base64
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import pytest
from sqlalchemy import select

from app.execution.workspace import sandbox_command
from app.models import Job
from app.modules.domestic_studio import runner, turn_service
from app.modules.domestic_studio.turn_models import Picture, Turn
from app.overseas.studio.schemas import Send
from files_helpers import image_bytes
from test_domestic_files_pg import Store
from test_domestic_runner_pg import prepare
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


@pytest.mark.skipif(not sys.platform.startswith('linux') or not shutil.which('bwrap'),
                    reason='requires the isolated Linux Bubblewrap runtime')
def test_real_sandbox_executes_stub_and_delivers_its_image(context, database, tmp_path, monkeypatch):
    real_run = subprocess.run
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    monkeypatch.setattr(runner.subprocess, 'run', real_run)
    monkeypatch.setattr(runner, 'sandbox_command', sandbox_command)
    settings = runner.get_settings()
    cli = tmp_path / 'codex-stub'
    encoded = base64.b64encode(image_bytes()).decode('ascii')
    cli.write_text("#!/usr/bin/python3\n"
        "import base64,json,pathlib,sys,time\n"
        "if '--version' in sys.argv:\n print('codex-cli test'); sys.exit(0)\n"
        "prompt=sys.stdin.read()\n"
        "resume='resume' in sys.argv\n"
        "marker=pathlib.Path('/work/first.marker')\n"
        "if resume: assert marker.read_text()=='preserved' and 'session-1' in sys.argv\n"
        "else: marker.write_text('preserved')\n"
        "pathlib.Path('/work/actual-prompt.txt').write_text(prompt)\n"
        "sessions=pathlib.Path('/home/runner/.codex/sessions'); sessions.mkdir(parents=True,exist_ok=True)\n"
        "rollout=sessions/'rollout-test-session-1.jsonl'\n"
        "if not rollout.exists(): rollout.write_text(json.dumps({'type':'session_meta','payload':{'id':'session-1'}})+'\\n')\n"
        "time.sleep(.4)\n"
        "name='final2.png' if resume else 'final.png'\n"
        f"pathlib.Path('/work',name).write_bytes(base64.b64decode('{encoded}'))\n"
        "events=[{'type':'thread.started','thread_id':'session-1'},"
        "{'type':'item.completed','item':{'id':'reply','type':'agent_message','text':'![结果](/work/'+name+')'}},"
        "{'type':'turn.completed'}]\n"
        "for event in events: print(json.dumps(event),flush=True)\n", encoding='utf-8')
    cli.chmod(0o755)
    helper = tmp_path / 'codex-code-mode-host'
    helper.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    helper.chmod(0o755)
    settings.codex_binary, settings.codex_bwrap_binary = str(cli), shutil.which('bwrap')
    store = Store()
    traces, original_settle = [], runner.settle
    def settle(*args, **kwargs):
        traces.append(traceback.format_exc())
        return original_settle(*args, **kwargs)
    monkeypatch.setattr(runner, 'settle', settle)
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    with factory() as session:
        job = session.get(Job, job_id)
        picture = session.scalar(select(Picture))
        assert job.status == 'succeeded', (job.error, traces)
        assert job.execution_count == 1 and picture is not None
        assert store.objects[(picture.bucket, picture.object_key)] == image_bytes()
    actor, channel = context[3], context[5]
    with factory.begin() as session:
        turn_service.send(session, actor, 'camera', channel, Send(text='继续修改'), 'resume-test', catalog)
        second_job = session.scalar(select(Turn.job_id).where(Turn.text == '继续修改'))
    runner.run_turn(second_job, factory, store=store, catalog=catalog)
    with factory() as session:
        job = session.get(Job, second_job)
        assert job.status == 'succeeded', (job.error, traces)
        assert len(list(session.scalars(select(Picture)))) == 2
    work = tmp_path / 'execution' / 'domestic-studio' / str(channel) / 'persistent' / 'work'
    assert (work / 'first.marker').read_text() == 'preserved'
    assert '继续修改' in (work / 'actual-prompt.txt').read_text()
