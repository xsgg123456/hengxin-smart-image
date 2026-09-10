"""Run on the dedicated Linux execution host; isolated smoke, never business DB."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from workspace import prepare_workspace, sandbox_command


def main():
    binary, auth = sys.argv[1:3]
    root = Path(tempfile.mkdtemp(prefix='phase9-isolation-'))
    try:
        first = prepare_workspace(root, uuid4(), uuid4(), auth)
        second = prepare_workspace(root, uuid4(), uuid4(), auth)
        sentinel = second.home / 'secret.txt'
        sentinel.write_text('TASK_B_PRIVATE')
        (first.control / 'secret.txt').write_text('CONTROL_PRIVATE')
        argv = sandbox_command(first, binary, [])
        # Substitute a harmless shell command at the exact same isolation boundary.
        split = argv.index('--')
        check = argv[:split + 1] + ['/bin/sh', '-c',
            'test ! -r "$1" && ! cat "$1" 2>/dev/null && '
            '! echo CORRUPT > "$1" 2>/dev/null && '
            'test ! -e "$2" && '
            'test ! -e /var/run/docker.sock && '
            'echo OWN > /work/own.txt && cat /work/own.txt', 'sh', str(sentinel), str(first.control)]
        result = subprocess.run(check, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert sentinel.read_text() == 'TASK_B_PRIVATE'
        assert (first.work / 'own.txt').read_text().strip() == 'OWN'
        print('PASS cross-task read/write denied; own workspace writable', flush=True)
        # Killing the namespace supervisor must stop even a detached descendant.
        command = argv[:split + 1] + ['/bin/sh', '-c',
            'setsid /bin/sh -c "while :; do echo tick >> /work/ticks; sleep .1; done" & wait']
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1)
            assert (first.work / 'ticks').is_file()
            process.kill()
            process.wait(timeout=5)
            time.sleep(.5)
            size = (first.work / 'ticks').stat().st_size
            time.sleep(.5)
            assert (first.work / 'ticks').stat().st_size == size
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        print('PASS detached process tree stops with namespace supervisor', flush=True)
        for index, workspace in enumerate((first, second)):
            command = sandbox_command(workspace, binary,
                ['exec', '--sandbox', 'workspace-write', '--skip-git-repo-check', '--json', '-'])
            prompt = 'Remember code ISOLATED-' + str(index) + '. Reply READY only, use no tools.'
            result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=120)
            (root / f'events-{index}.jsonl').write_text(result.stdout)
            print('CLI', index, 'EXIT', result.returncode, 'ERR', result.stderr[-500:], flush=True)
            events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            sid = next((e.get('thread_id') for e in events if e.get('type') == 'thread.started'), None)
            replies = [e['item'].get('text') for e in events if e.get('type') == 'item.completed'
                       and e.get('item', {}).get('type') == 'agent_message']
            print('SESSION', sid, 'REPLIES', replies, flush=True)
            assert result.returncode == 0 and sid and 'READY' in replies
            if index == 0:
                first_id = sid
                workspace = prepare_workspace(root, first.home.parent.name, uuid4(), auth)
                resumed = sandbox_command(workspace, binary, ['exec', '--sandbox', 'workspace-write',
                    'resume', '--skip-git-repo-check', '--json', sid, '-'])
                reply = subprocess.run(resumed, input='Return the code I asked you to remember. No tools.',
                                       capture_output=True, text=True, timeout=120)
                assert reply.returncode == 0 and 'ISOLATED-0' in reply.stdout, reply.stderr
                print('PASS persistent task home resumes exact session', flush=True)
            else:
                assert sid != first_id
        print('PASS distinct real sessions under outer isolation', flush=True)
    finally:
        # Exact mkdtemp path; no user task or original authentication is removed.
        assert root.parent == Path(tempfile.gettempdir()).resolve()
        shutil.rmtree(root)
        print('PASS isolated test homes cleaned', flush=True)


if __name__ == '__main__':
    main()
