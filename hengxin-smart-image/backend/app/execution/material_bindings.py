"""Verify historical input paths against immutable object checksums."""
import hashlib
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from app.resource_models import FileRecord
from app.modules.tasks.models import TaskSource
from .diagnostics import _safe_read


def historical_inputs(session, task, row, root, prompts):
    sources = session.scalars(select(TaskSource).where(TaskSource.task_id == task.id).order_by(TaskSource.slot)).all()
    targets = task.template_snapshot['images'] if task.template_snapshot else [{'fileId': str(s.file_id)} for s in sources]
    references = '\n'.join(p.get('text', '') for p in prompts)
    work = Path(root).absolute() / str(task.id) / 'rounds' / str(row.id)
    result = []

    def add(role, label, file_id, candidates):
        file = session.get(FileRecord, UUID(str(file_id)))
        verified = False
        if file:
            extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}.get(file.content_type)
            for prefix in candidates:
                path = prefix + extension if extension else ''
                if not path or path not in references:
                    continue
                try:
                    raw = _safe_read(work / path.removeprefix('/work/'), 10 * 1024 * 1024,
                                     allow_windows_fallback=True)
                    verified |= hashlib.sha256(raw).hexdigest() == file.checksum
                except (OSError, ValueError):
                    pass
        result.append({'role': role, 'label': label if verified else f'任务关联{label}（未核实本轮使用）',
                       'fileId': str(file_id), 'verified': verified})

    selected = list(range(len(targets))) if row.target is None else [row.target]
    for local, slot in enumerate(selected):
        if slot < len(targets):
            add('original', f'原始底图 {slot + 1}', targets[slot]['fileId'],
                [f'/work/targets/{local:02d}', f'/work/original/{local:02d}'])
    if task.mode != 'text':
        for index, source in enumerate(sources):
            add('source', f'素材 {source.slot + 1}', source.file_id, [f'/work/inputs/{index:02d}'])
    return result
