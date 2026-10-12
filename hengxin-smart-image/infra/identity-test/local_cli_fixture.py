"""Explicit offline subprocess fixture; never used by a production worker."""
from contextlib import contextmanager
from pathlib import Path
import json
import sys
import tempfile


@contextmanager
def configured_runner(settings, document, *, output_name='plan.json', files=None, usage=None):
    from app.overseas.execution import runner
    old_command = runner.sandbox_command
    fields = ('enable_codex_executor', 'codex_binary', 'codex_auth_file', 'codex_execution_root')
    previous = {name: getattr(settings, name) for name in fields}
    with tempfile.TemporaryDirectory(prefix='overseas-offline-cli-') as directory:
        root = Path(directory)
        cli = root / 'fixture-cli'
        payload = root / 'plan-fixture.json'
        payload.write_text(json.dumps(document), encoding='utf-8')
        artifacts = root / 'artifacts'
        artifacts.mkdir()
        for name, data in (files or {}).items():
            target = artifacts / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        cli.write_text('#!' + sys.executable + '\n' + '''import json,sys,uuid,shutil
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli ''' + settings.codex_version + '''')
    raise SystemExit(0)
work, source, artifacts = map(Path, sys.argv[1:4])
assert sys.stdin.read().strip()
assert (work / 'input.json').is_file()
(work / sys.argv[4]).write_bytes(source.read_bytes())
for source_file in artifacts.rglob('*'):
    if source_file.is_file():
        target = work / source_file.relative_to(artifacts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
print(json.dumps({'type':'thread.started','thread_id':'fixture-'+uuid.uuid4().hex}))
event = {'type':'turn.completed'}
usage = json.loads(sys.argv[5])
if usage is not None:
    event['usage'] = usage
print(json.dumps(event))
''', encoding='utf-8')
        cli.chmod(0o700)
        auth = root / 'auth.json'
        auth.write_text('{"fixture":true}', encoding='utf-8')
        settings.enable_codex_executor = True
        settings.codex_binary = str(cli)
        settings.codex_auth_file = str(auth)
        settings.codex_execution_root = str(root / 'execution')
        runner.sandbox_command = lambda workspace, *args: [str(cli), str(workspace.work), str(payload), str(artifacts), output_name, json.dumps(usage)]
        try:
            yield payload
        finally:
            runner.sandbox_command = old_command
            for name, value in previous.items():
                setattr(settings, name, value)
