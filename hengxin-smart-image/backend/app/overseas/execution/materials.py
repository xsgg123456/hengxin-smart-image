"""Write only frozen job inputs; no domestic business or Skill lookup."""
import json
import re
from pathlib import PurePosixPath


def prepare(job, workspace):
    # Queue copies JSON transactionally. Keep the exact input for later audit.
    encoded = json.dumps(job.payload, ensure_ascii=False, allow_nan=False)
    (workspace.control / 'input.json').write_text(encoded, encoding='utf-8')
    (workspace.work / 'input.json').write_text(encoded, encoding='utf-8')
    skill = job.payload.get('skill')
    workspace.use_skill = skill is not None
    if skill is None:
        return
    name, files = skill.get('name'), skill.get('files')
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name)
            or not isinstance(files, dict) or not files.get('SKILL.md')):
        raise ValueError('Invalid frozen Skill')
    workspace.skill_name = name
    root = workspace.work / 'skills' / name
    for relative, content in files.items():
        path = PurePosixPath(relative)
        if (not relative or path.is_absolute() or ':' in relative or '\\' in relative
                or any(part in ('', '.', '..') for part in relative.split('/'))
                or not isinstance(content, str)):
            raise ValueError('Invalid frozen Skill file')
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    workspace.local_skill = root
