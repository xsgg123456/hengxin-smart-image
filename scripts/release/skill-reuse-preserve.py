"""Read-only conversation evidence after drain; never read or copy private file bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

r = None


def execution_root():
    state = r.a.worker('overseas')
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    values = dict(item.decode().split('=',1) for item in raw.split(b'\0') if item)
    root = Path(values['OVERSEAS_CODEX_EXECUTION_ROOT'])
    r.require(root.is_absolute() and root.is_dir() and root != Path('/'), 'Invalid execution root')
    return str(root.resolve(strict=True))


def metadata(root):
    rows = {}
    def visit(path):
        for entry in os.scandir(path):
            item = Path(entry.path)
            info = entry.stat(follow_symlinks=False)
            rows[item.relative_to(root).as_posix()] = [stat.S_IFMT(info.st_mode),info.st_size,
                info.st_mtime_ns,info.st_ino,info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode)]
            if stat.S_ISDIR(info.st_mode):
                visit(item)
    visit(Path(root))
    return rows


def snapshot(data):
    rows = metadata(Path(data['executionRoot']))
    tables = r.sql(r.DB,"SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND (tablename LIKE 'overseas_studio_%' OR tablename LIKE 'overseas_conversation%') ORDER BY tablename").splitlines()
    r.require(tables, 'Conversation tables not discovered')
    records = {}
    for name in tables:
        r.require(re.fullmatch('[a-z_0-9]+',name), 'Unsafe table')
        records[name] = r.sql(r.DB,'SELECT count(*)::text || \':\' || md5(coalesce(string_agg('
            'md5(to_jsonb(t)::text),\'\' ORDER BY md5(to_jsonb(t)::text)),\'\')) FROM "'+name+'" t')
    return dict(files=rows,tables=records)


def capture(work,data):
    path = work/'conversation-before.json'
    r.require(not path.exists(), 'Preservation baseline already fixed')
    result = snapshot(data)
    r.private(path,result)
    r.private(work/'CONVERSATION_BASELINE',dict(manifest=data['manifest'],sha256=r.digest(path)))


def verify(work,data):
    proof = json.loads((work/'CONVERSATION_BASELINE').read_text())
    r.require(proof == dict(manifest=data['manifest'],sha256=r.digest(work/'conversation-before.json')),
              'Preservation proof drift')
    expected = json.loads((work/'conversation-before.json').read_text())
    r.require(snapshot(data) == expected, 'Conversation files or records changed during native switch')
    r.private(work/'CONVERSATIONS_PRESERVED',dict(manifest=data['manifest'],
        fileCount=len(expected['files']),tables=expected['tables'],baselineSha256=proof['sha256']))
