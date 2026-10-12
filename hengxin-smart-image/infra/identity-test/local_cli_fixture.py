"""Explicit offline subprocess fixture; never used by a production worker."""
from contextlib import contextmanager
from pathlib import Path
import json
import sys
import tempfile


@contextmanager
def configured_runner(settings, document):
    from app.overseas.execution import runner
    old_command = runner.sandbox_command
    fields = ('enable_codex_executor', 'codex_binary', 'codex_auth_file', 'codex_execution_root')
    previous = {name: getattr(settings, name) for name in fields}
    with tempfile.TemporaryDirectory(prefix='overseas-offline-cli-') as directory:
        root = Path(directory)
        cli = root / 'fixture-cli'
        payload = root / 'plan-fixture.json'
        payload.write_text(json.dumps(document), encoding='utf-8')
        cli.write_text('#!' + sys.executable + '\n' + '''import json,sys,uuid
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli ''' + settings.codex_version + '''')
    raise SystemExit(0)
work, source = map(Path, sys.argv[1:3])
assert sys.stdin.read().strip()
assert (work / 'input.json').is_file()
(work / 'plan.json').write_bytes(source.read_bytes())
print(json.dumps({'type':'thread.started','thread_id':'fixture-'+uuid.uuid4().hex}))
print(json.dumps({'type':'turn.completed'}))
''', encoding='utf-8')
        cli.chmod(0o700)
        auth = root / 'auth.json'
        auth.write_text('{"fixture":true}', encoding='utf-8')
        settings.enable_codex_executor = True
        settings.codex_binary = str(cli)
        settings.codex_auth_file = str(auth)
        settings.codex_execution_root = str(root / 'execution')
        runner.sandbox_command = lambda workspace, *args: [str(cli), str(workspace.work), str(payload)]
        try:
            yield payload
        finally:
            runner.sandbox_command = old_command
            for name, value in previous.items():
                setattr(settings, name, value)
