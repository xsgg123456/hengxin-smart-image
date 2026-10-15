"""Real Linux namespaces, no model/network/business writes. Run as the worker user."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.execution.workspace import Workspace, prepare_workspace, sandbox_command
from app.overseas.execution.materials import prepare as prepare_materials
from app.overseas.studio.context_workspace import prepare


def run(workspace, binary, bwrap, code, *, readonly=False, input_data=None):
    args = sandbox_command(workspace, binary, [], bwrap)
    offset = args.index('--')
    flags = ['--unshare-net']
    if readonly:
        flags += ['--remount-ro', '/work', '--remount-ro', '/home/runner']
    result = subprocess.run(args[:offset] + flags + ['--', '/usr/bin/python3', '-c', code],
        text=True, capture_output=True, timeout=120, input=input_data)
    if result.returncode:
        raise RuntimeError('Sandbox probe failed: ' + result.stderr[-1500:])
    return json.loads(result.stdout)


def asset(name, data):
    identity = str(uuid4())
    return dict(id=identity, name=name, bucket='isolated-fixture', object_key=identity,
        content_type='application/octet-stream', size_bytes=len(data), checksum=hashlib.sha256(data).hexdigest())


def three_rounds(binary, bwrap):
    with tempfile.TemporaryDirectory(prefix='hx-context-probe-') as temporary:
        root = Path(temporary)
        auth = root / 'auth.json'
        auth.write_text('{}')
        conversation, history, originals, objects = uuid4(), [], [], {}
        for extension in ('pptx', 'xlsx', 'pdf', 'png', 'ttf', 'zip', 'py'):
            data = ('fixture-' + extension).encode()
            item = asset('original.' + extension, data)
            originals.append(item)
            objects[item['object_key']] = data
        other = prepare_workspace(root / 'execution', uuid4(), uuid4(), auth)
        (other.work / 'private.txt').write_text('other conversation')
        results, paths, first_work = [], [], None
        for number in range(3):
            turn = uuid4()
            ws = prepare_workspace(root / 'execution', conversation, turn, auth)
            current = originals if number == 0 else []
            if number == 2:
                item = asset('original.pptx', b'new same-named document')
                objects[item['object_key']] = b'new same-named document'
                current = [item]
            paths += prepare(ws, history, current, lambda row: objects[row['object_key']])
            first_work = first_work or ws.work
            assert ws.work == first_work
            skill = {'name': 'probe', 'files': {'SKILL.md': 'test skill'}} if number == 0 else None
            prepare_materials(SimpleNamespace(payload={'inputs': current, 'skill': skill}), ws)
            expected = {entry['path']: ('new same-named document' if index == 7 else
                'fixture-' + Path(entry['name']).suffix[1:]) for index, entry in enumerate(paths)}
            code = '''import json
from pathlib import Path
expected=EXPECTED
for name,value in expected.items():
 assert Path(name).read_text()==value, name
assert not Path(OTHER).exists()
assert not Path(CONTROL).exists()
assert Path('/work/skills/probe/SKILL.md').exists()==SELECTED
if NUMBER==0:
 Path('/work/research').mkdir()
 Path('/work/research/note.txt').write_text('keep derived files')
else:
 assert Path('/work/research/note.txt').read_text()=='keep derived files'
try:
 Path(next(iter(expected))).write_text('overwrite')
 raise AssertionError('Original was writable')
except OSError:
 pass
print(json.dumps({'round':NUMBER+1,'originals':len(expected),'derived':True,'readonly':True,'isolated':True}))
'''.replace('EXPECTED', repr(expected)).replace('OTHER', repr(str(other.work / 'private.txt'))).replace(
                'CONTROL', repr(str(ws.control))).replace('SELECTED', repr(number == 0)).replace('NUMBER', str(number))
            results.append(run(ws, binary, bwrap, code))
            history.append(dict(turn_id=str(turn), inputs=current))
        return results


def hashes(root, prefix=''):
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked restored file')
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative.split('/')[0] in {'inputs', 'skills', 'input.json', '.context-files.json'} and not prefix:
                continue
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            result[prefix + relative] = digest.hexdigest()
    return result


def verify_sources(base, plan, expected):
    from app.overseas.studio import context_fs as fs
    index = fs.load(base / 'persistent/context-index.json')
    for item in plan['files']:
        origin = base / 'rounds' / str(UUID(item['turn_id'])) / fs.relative(item['relative'])
        if fs.digest(origin) != (item['checksum'], item['size_bytes']):
            raise ValueError('Legacy source changed after inspection')
        if item.get('original'):
            matches = [row for row in index['inputs'] if row.get('checksum') == item['checksum']
                       and item['turn_id'] in row['sources'] and row.get('path')]
        else:
            matches = [row for row in index['files'] if row['sourceChecksum'] == item['checksum']
                       and row['logicalPath'] == '/work/' + item['logical']
                       and item['turn_id'] in row['sources']]
        if not matches:
            raise ValueError('Legacy source missing from restored index')
        for row in matches:
            if not row['path'].startswith('/work/') or expected.get(
                    fs.relative(row['path'].removeprefix('/work/'))) != item['checksum']:
                raise ValueError('Restored target does not match legacy source')
    if len(plan['inputs']) != plan['inputFiles']:
        raise ValueError('Frozen source input coverage mismatch')
    for row in plan['inputs']:
        if not row['path'].startswith('/work/inputs/') or expected.get(
                fs.relative(row['path'].removeprefix('/work/'))) != row['checksum']:
            raise ValueError('Frozen input missing or changed in restored work')
    return dict(sourceDigest=plan['digest'], sourceFilesVerified=len(plan['files']),
                sourceInputsVerified=len(plan['inputs']))


def restored(root, conversation, binary, bwrap, source_plan):
    base = root / 'studio' / str(UUID(conversation))
    persistent = base / 'persistent'
    with tempfile.TemporaryDirectory(prefix='hx-context-readonly-') as temporary:
        control = Path(temporary)
        (control / 'input.json').write_text('{}')
        ws = Workspace(base / 'home', persistent / 'work', control, use_skill=False)
        ws.persistent = True
        ws.inputs_root = persistent / 'inputs'
        ws.context_index = persistent / 'context-index.json'
        expected = {**hashes(ws.work), **hashes(ws.inputs_root, 'inputs/')}
        if not expected:
            raise ValueError('No restored files to verify')
        coverage = verify_sources(base, source_plan, expected)
        code = '''import hashlib,json,sys
from pathlib import Path
expected=json.load(sys.stdin)
for name,value in expected.items():
 digest=hashlib.sha256()
 with (Path('/work')/name).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 assert digest.hexdigest()==value,name
print(json.dumps({'readableFiles':len(expected),'allHashesMatch':True}))
'''
        checks = [run(ws, binary, bwrap, code, readonly=True,
                      input_data=json.dumps(expected)) for _ in range(3)]
        return dict(conversationId=conversation, independentSandboxReads=checks, **coverage)


def legacy_restoration(binary, bwrap):
    from app.overseas.studio.context_workspace import inspect
    from app.overseas.studio.context_assets import identity, safe_name
    with tempfile.TemporaryDirectory(prefix='hx-context-legacy-') as temporary:
        root, conversation, history = Path(temporary), uuid4(), []
        auth = root / 'auth.json'; auth.write_text('{}')
        inputs = []
        for number in range(2):
            ws = prepare_workspace(root / 'studio', conversation, uuid4(), auth)
            data = ('old original ' + str(number)).encode()
            item = asset('original.csv', data)
            (ws.work / 'inputs').mkdir()
            (ws.work / 'inputs/1.csv').write_bytes(data)
            (ws.work / 'notes.txt').write_text('old research version ' + str(number))
            history.append(dict(turn_id=ws.work.name, inputs=[item]))
            inputs.append(dict(path='/work/inputs/' + identity(item) + '/' + safe_name(item['name']),
                checksum=item['checksum'], size_bytes=len(data)))
        ws = prepare_workspace(root / 'studio', conversation, uuid4(), auth)
        plan = inspect(ws, history)
        plan['inputs'] = inputs
        def no_download(_):
            raise AssertionError('Expected verified legacy local originals')
        prepare(ws, history, [], no_download)
        return restored(root, str(conversation), binary, bwrap, plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary')
    parser.add_argument('--bwrap')
    parser.add_argument('--conversation')
    parser.add_argument('--source-plan-stdin', action='store_true')
    args = parser.parse_args()
    from app.core.config import get_settings
    settings = get_settings()
    binary, bwrap = args.binary or settings.codex_binary, args.bwrap or settings.codex_bwrap_binary
    if args.conversation and not args.source_plan_stdin:
        parser.error('Restored verification requires an independently inspected source plan')
    result = (restored(Path(settings.codex_execution_root), args.conversation, binary, bwrap, json.load(sys.stdin))
              if args.conversation else {'threeRounds': three_rounds(binary, bwrap),
                                         'legacyRecovery': legacy_restoration(binary, bwrap)})
    print(json.dumps(result))


if __name__ == '__main__':
    main()
