"""Stage the pinned CLI and a native-only patch, without changing live services."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

VERSION = '0.162.1'
INTEGRITY = 'cjK2mdHIfEepZ1lQ1MX3aTQC+8ncIsvnacl/6vI2dIIcfP8/MrhTQ2+qRlkXFNDzJSj1d36quIszP+3/4CUJWQ=='
RELEASE = 'codex-astra-20261014'
WORK = Path('/opt/hengxin-releases') / RELEASE
RUNTIME = Path('/opt/hengxin-runtime') / ('codex-' + VERSION)
TARGET = Path('/opt/hengxin-overseas-releases') / RELEASE / 'backend'
MODULE = 'app/overseas/studio/execution.py'
BASE_HASH = '182c48886f1a049774f294a24eb650df7b9fd12e8a8532bcbc9e6ffa0aed2eda'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
            if p.is_file() and not any(x in p.parts for x in ('.venv', '__pycache__', '.pytest_cache'))}


def stage_cli():
    archive = WORK / 'codex.tgz'
    if not archive.exists():
        with urllib.request.urlopen('https://registry.npmjs.org/@openai/codex/-/codex-0.162.1-linux-x64.tgz',
                                    timeout=90) as response, archive.open('xb') as out:
            shutil.copyfileobj(response, out)
    assert base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode() == INTEGRITY
    unpack = WORK / 'unpacked'
    if not unpack.exists():
        unpack.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(unpack, filter='data')
    binaries = list(unpack.rglob('codex'))
    binaries = [p for p in binaries if p.is_file()]
    assert len(binaries) == 1
    source = binaries[0].parent
    assert (source / 'codex-code-mode-host').is_file(), 'Missing matching helper'
    # Preserve the complete vendor layout and the established flat entry points.
    for relative, expected in tree(source.parent).items():
        path = RUNTIME / relative
        if path.exists():
            assert digest(path) == expected, 'Never overwrite a different runtime'
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source.parent / relative, path)
    for name in ('codex', 'codex-code-mode-host'):
        path = RUNTIME / name
        if path.exists():
            assert digest(path) == digest(source / name)
        else:
            shutil.copy2(source / name, path)
    for p in (RUNTIME, *RUNTIME.rglob('*')):
        assert not p.is_symlink(), 'Unexpected runtime link'
        p.chmod(0o755 if p.is_dir() or os.access(p, os.X_OK) else 0o644)
    actual = subprocess.check_output([str(RUNTIME / 'codex'), '--version'], text=True, timeout=15).strip()
    assert actual == 'codex-cli ' + VERSION
    return tree(RUNTIME)


def main():
    assert os.geteuid() == 0 and not __import__('sys').flags.optimize
    os.umask(0o022)
    WORK.mkdir(mode=0o755, exist_ok=True)
    assert not (WORK / 'prepared.json').exists()
    old = Path(subprocess.check_output(['systemctl', 'show', 'hengxin-overseas-worker',
                                      '-p', 'WorkingDirectory', '--value'], text=True).strip())
    assert old.is_relative_to('/opt/hengxin-overseas-releases')
    assert digest(old / MODULE) == BASE_HASH, 'Live source changed; inspect before proceeding'
    baseline = tree(old)
    runtime = stage_cli()
    assert not TARGET.exists()
    TARGET.parent.mkdir(mode=0o755)
    shutil.copytree(old, TARGET, ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache'))
    shutil.copyfile(WORK / 'execution.py', TARGET / MODULE)
    (TARGET / '.venv').symlink_to(old / '.venv', target_is_directory=True)
    after = tree(TARGET)
    assert set(after) == set(baseline)
    assert [name for name in after if after[name] != baseline[name]] == [MODULE]
    result = dict(release=RELEASE, old=str(old), target=str(TARGET), runtime=str(RUNTIME),
                  runtime_files=runtime, baseline=baseline, files=after)
    (WORK / 'prepared.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(staged=RELEASE, version=VERSION, runtime_files=len(runtime), native_files=len(after))))


if __name__ == '__main__':
    main()
