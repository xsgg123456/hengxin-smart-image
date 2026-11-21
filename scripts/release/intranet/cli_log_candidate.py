"""Rebuild a reviewed backend-only log maintenance package from main and its live base."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

import cli_log_maintenance as policy
import package_release


APPLICATION = '406eaf4abec3c6f8715d3e90e26d25d33ca218ae'
COMMON = (
    'execution/capture_json.py', 'execution/credential_errors.py', 'execution/detail_json.py', 'execution/event_file.py',
    'execution/events.py', 'execution/log_capture.py', 'execution/process.py', 'execution/safe_stream.py',
    'execution/workspace.py',
    'overseas/execution/events.py', 'overseas/generation/delivery.py', 'overseas/studio/completion.py',
    'overseas/studio/context_fs.py', 'overseas/studio/execution.py', 'overseas/studio/transcript.py',
)
GROUP = {
    'domestic': ('modules/api_image_edits/conversation_errors.py', 'modules/api_image_edits/conversation_runner.py',
                 'modules/api_image_edits/conversation_runtime.py', 'modules/domestic_studio/execution_workspace.py',
                 'modules/domestic_studio/runner.py', 'modules/domestic_studio/transcript.py'),
    'overseas': ('overseas/studio/image_recovery.py', 'overseas/studio/recovery.py'),
}


def compose(repo, destination, scope):
    """Write Git objects only under destination. The working checkout, index and refs stay intact."""
    base = policy.BASE[scope]
    git = package_release.git
    git(repo, 'init', '--bare', str(destination))
    objects = git(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'objects').decode().strip()
    (destination / 'objects/info/alternates').write_text(Path(objects).as_posix() + '\n', encoding='utf-8', newline='\n')
    git(destination, 'read-tree', base)
    paths = ['hengxin-smart-image/backend/app/' + name for name in (*COMMON, *GROUP[scope])]
    patch = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--binary', '--no-renames',
                '--full-index', APPLICATION + '^', APPLICATION, '--', *paths)
    subprocess.run(['git', '-C', str(destination), '-c', 'core.autocrlf=false', 'apply',
                    '--cached', '--3way', '--whitespace=nowarn', '-'], input=patch, check=True)
    changed = git(destination, 'diff', '--cached', '--name-only', base, '--').decode().splitlines()
    if set(changed) != set(paths):
        raise RuntimeError('Composed delta differs from the reviewed group paths')
    tree = git(destination, 'write-tree').decode().strip()
    date = git(repo, 'show', '-s', '--format=%ct', APPLICATION).decode().strip() + ' +0000'
    env = {**os.environ, 'GIT_AUTHOR_DATE': date, 'GIT_COMMITTER_DATE': date,
           'GIT_AUTHOR_NAME': 'Hengxin Release', 'GIT_COMMITTER_NAME': 'Hengxin Release',
           'GIT_AUTHOR_EMAIL': 'release@hengxin.invalid', 'GIT_COMMITTER_EMAIL': 'release@hengxin.invalid'}
    message = f'fix: 从{scope}生产基线合入单轮日志修复\n\n{APPLICATION}\n'
    return subprocess.check_output(['git', '-C', str(destination), '-c', 'commit.gpgSign=false',
                                    'commit-tree', tree, '-p', base], input=message.encode(), env=env).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', required=True, choices=policy.BASE)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix='hx-cli-log-git-') as scratch:
        objects = Path(scratch) / 'objects.git'
        commit = compose(repo, objects, args.scope)
        if commit != policy.CANDIDATE[args.scope]:
            raise RuntimeError('Composed commit differs from the reviewed group candidate')
        package_release.package_release(objects, commit, args.output, args.scope)
        print(args.scope, commit, args.output)


if __name__ == '__main__':
    main()
