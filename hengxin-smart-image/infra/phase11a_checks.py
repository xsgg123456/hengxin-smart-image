"""Evidence collection for isolated live CLI verification; no raw model logs."""
import hashlib
import io
import json
import os
from pathlib import Path
import time
import zipfile
from uuid import UUID

from PIL import Image
from sqlalchemy import create_engine, text


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class Evidence:
    def __init__(self, environment):
        self.environment = environment
        self.engine = create_engine(environment.env['DATABASE_URL'])
        self.samples = []

    def rows(self, query, **values):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(query), values).mappings()]

    def attempts(self, task_id):
        return self.rows('SELECT a.id,a.round_id,a.process_id,a.process_start,a.boot_id,a.status,'
            'a.started_at,a.finished_at,a.exit_code,a.cli_version,a.workspace,u.data AS usage,'
            'r.job_id,j.execution_count,j.status AS job_status,r.status AS round_status '
            'FROM execution_attempts a JOIN execution_rounds r ON r.id=a.round_id '
            'JOIN job_records j ON j.id=r.job_id LEFT JOIN execution_usage u ON u.attempt_id=a.id '
            'WHERE a.task_id=:task ORDER BY a.started_at', task=UUID(task_id))

    def sample(self, task_ids):
        roots = {str(row['process_id']): task for task in task_ids for row in self.attempts(task)
                 if row['process_id'] and row['status'] == 'running'}
        table = {}
        for directory in Path('/proc').iterdir():
            if not directory.name.isdigit():
                continue
            try:
                fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
                table[directory.name] = {'parent': fields[1], 'birth': fields[19],
                    'cpuTicks': int(fields[11]) + int(fields[12]),
                    'rssBytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'),
                    'name': (directory / 'comm').read_text().strip()}
            except (OSError, ValueError, IndexError):
                continue
        found = {}
        for root, task in roots.items():
            family = {root}
            while True:
                children = {pid for pid, item in table.items() if item['parent'] in family}
                if children.issubset(family):
                    break
                family |= children
            processes = {pid: table[pid] for pid in family if pid in table}
            if processes:
                found[task] = processes
        if found:
            self.samples.append({'at': time.time(), 'tasks': found})

    def round_evidence(self, task_id, expected_rounds=None):
        rows = self.attempts(task_id)
        require(rows and all(row['execution_count'] == 1 for row in rows), 'Duplicate execution count')
        require(all(row['status'] == 'finished' for row in rows), 'CLI did not finish')
        rounds = [str(row['round_id']) for row in rows]
        require(len(set(rounds)) == len(rounds), 'Duplicate attempt for one round')
        if expected_rounds is not None:
            require(set(rounds) == set(map(str, expected_rounds)), 'Unexpected round set')
        require(all(row.get('process_id') and row.get('process_start') and row.get('cli_version')
                    for row in rows), 'Missing CLI execution identity')
        for row in rows:
            pid = row['process_id']
            if pid and Path(f'/proc/{pid}/stat').exists():
                birth = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
                require(birth != row['process_start'], 'CLI process remains after completion')
        for sample in self.samples:
            for pid, process in sample['tasks'].get(task_id, {}).items():
                path = Path('/proc') / pid / 'stat'
                if path.exists():
                    try:
                        birth = path.read_text().rsplit(')', 1)[1].split()[19]
                    except OSError:
                        continue
                    require(birth != process['birth'], 'CLI descendant remains after completion')
        return [{key: str(value) if key in ('id', 'round_id', 'started_at', 'finished_at', 'job_id') else value
                 for key, value in row.items() if key not in ('workspace', 'boot_id')} for row in rows]

    def close(self):
        self.engine.dispose()

    def ownership(self, client, detail):
        task = detail['task']
        row = next(row for row in self.attempts(task['id']) if str(row['round_id']) == task['currentRoundId'])
        control = Path(row['workspace'])
        work = control.parent.parent / 'rounds' / str(row['round_id'])
        manifest = json.loads((work / 'manifest.json').read_text())
        generated = control.parent.parent / 'home' / '.codex' / 'generated_images' / task['sessionId']
        require(len(manifest['outputs']) == len(task['images']), 'Output ownership count mismatch')
        for output, picture in zip(manifest['outputs'], task['images']):
            path = generated / output['file']
            require(path.resolve().is_relative_to(generated.resolve()), 'Output escaped task session')
            response = client.get(picture['url'])
            response.raise_for_status()
            require(hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(response.content).digest(),
                    'Published bytes do not belong to this task session')

    def isolation(self, task_ids):
        """Use the actual task mounts with a controlled read/write probe, no model charge."""
        for own, other in (task_ids, list(reversed(task_ids))):
            own_row, other_row = self.attempts(own)[0], self.attempts(other)[0]
            own_control, other_control = Path(own_row['workspace']), Path(other_row['workspace'])
            require(own_control.parent.parent != other_control.parent.parent, 'Shared task root')
            sentinel = other_control.parent.parent / 'home' / 'phase11a-sentinel'
            sentinel.write_text('isolation-check', encoding='utf-8')
            code = ('from pathlib import Path\nimport subprocess\n'
                'from app.execution.workspace import Workspace,sandbox_command\n'
                f'control=Path({str(own_control)!r})\n'
                'workspace=Workspace(control.parent.parent/"home",control.parent.parent/"rounds"/control.name,control)\n'
                f'args=sandbox_command(workspace,{self.environment.env["CODEX_BINARY"]!r},[],{self.environment.env["CODEX_BWRAP_BINARY"]!r})\n'
                f'probe="from pathlib import Path\\np=Path({str(sentinel)!r})\\nfor mode in (\'r\',\'r+\'):\\n try:\\n  p.open(mode).close()\\n except OSError: pass\\n else: raise RuntimeError(\'cross-task access\')\\nprint(\'ISOLATED\')"\n'
                'result=subprocess.run(args[:-1]+["/usr/bin/python3","-c",probe],capture_output=True,text=True,timeout=15)\n'
                'assert result.returncode==0 and result.stdout.strip()=="ISOLATED"\nprint("ISOLATED")\n')
            require(self.environment.command(['-c', code], app=True).strip() == 'ISOLATED', 'Sandbox probe failed')
            require(sentinel.read_text() == 'isolation-check', 'Other task sentinel modified')


def image_evidence(client, pictures, output, label):
    hashes = []
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for index, picture in enumerate(pictures):
            response = client.get(picture['url'])
            response.raise_for_status()
            data = response.content
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                shape = list(image.size)
                fmt = image.format
            name = f'{label}-{index + 1}.{fmt.lower()}'
            (output / name).write_bytes(data)
            archive.writestr(name, data)
            hashes.append({'fileId': picture.get('fileId'), 'sha256': hashlib.sha256(data).hexdigest(),
                           'size': shape, 'format': fmt})
    with zipfile.ZipFile(io.BytesIO(bundle.getvalue())) as archive:
        require(archive.testzip() is None, 'ZIP CRC failure')
        require([hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()]
                == [entry['sha256'] for entry in hashes], 'ZIP content changed')
    (output / f'{label}.zip').write_bytes(bundle.getvalue())
    return hashes


def save_report(path, report):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
