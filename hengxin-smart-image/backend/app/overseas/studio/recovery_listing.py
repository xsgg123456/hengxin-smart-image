"""DB-bound candidate paths; never inspect another conversation or arbitrary home."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid5

from sqlalchemy import select
from app.core.config import get_settings
from app.execution.final_delivery import _PROTECTED
from app.overseas.execution.models import Job, TERMINAL
from . import context_fs as fs, delivery_context as context, delivery_snapshot as snapshots
from .delivery_snapshot_fs import canonical_target, snapshot_path, root_path, read_image
from .files import MAX_BYTES
from .models import Turn
from .output_files import validated

PRIVATE = _PROTECTED | {'input.json', '.context-files.json', 'context-index.json'}


class RecoveryError(ValueError):
    """Safe, user-facing receipt failure without private filesystem details."""


@dataclass
class Candidate:
    id: str
    job: Job
    path: Path
    target: str
    source: str
    name: str
    size: int
    version: str
    snapshot: dict | None = None
    control: Path | None = None

    def dto(self):
        return dict(id=self.id, name=self.name, path=self.target, source=self.source,
                    sizeBytes=self.size, version=self.version)


def stamp(path):
    info = fs.checked(path, directory=False).lstat()
    return sha256(repr(fs.stamp(info)).encode()).hexdigest(), info.st_size


def busy(session, channel):
    jobs = session.scalars(select(Job).join(Turn, Turn.job_id == Job.id)
        .where(Turn.conversation_id == channel.id))
    return any(job.status not in TERMINAL or
               (job.execution_count > 0 and not job.process_exited) for job in jobs)


def turns(session, channel):
    rows = session.execute(select(Turn, Job).join(Job, Turn.job_id == Job.id)
        .where(Turn.conversation_id == channel.id).order_by(Turn.created_at, Turn.id)).all()
    return [(turn, job) for turn, job in rows if job.task_id == channel.task_id
        and turn.task_id == channel.task_id and job.kind == 'studio'
        and isinstance(job.payload, dict) and job.payload.get('turnId') == str(turn.id)
        and job.payload.get('conversationId') == str(channel.id)]


def walk(root):
    """Skip unsafe/protected branches; a bad neighbor does not hide valid files."""
    try:
        directory = fs.checked(root, directory=True)
        children = sorted(directory.iterdir())
    except (OSError, ValueError):
        return
    for path in children:
        if path.name in PRIVATE:
            continue
        try:
            fs.checked(path)
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield path
        except (OSError, ValueError):
            continue


def _mutable(root, logical, source, turn, job):
    for path in walk(root):
        try:
            # checked() may add a Windows long-path prefix; normalize both roots.
            relative = path.relative_to(fs.checked(root, directory=True)).as_posix()
            target = canonical_target(logical + relative)
            version, size = stamp(path)
            if size > MAX_BYTES:
                continue
            identity = str(uuid5(turn.conversation_id, f'{source}:{root}:{target}'))
            yield Candidate(identity, job, path, target, source, path.name, size, version)
        except (OSError, ValueError):
            continue


def _snapshots(root, turn, job):
    control = root / 'control' / str(turn.id) / 'delivery'
    try:
        manifest = snapshots.load(control)
        if not manifest or any(manifest['identity'].get(k) != v
                               for k, v in context.identity(job).items()):
            return
        for row in manifest['items']:
            if row['status'] != 'captured':
                continue
            target = canonical_target(row['target'])
            identity = str(uuid5(turn.id, 'snapshot:' + target))
            yield Candidate(identity, job, snapshot_path(root_path(control), row), target,
                'snapshot', row['name'], row['sizeBytes'], row['checksum'], dict(row), control)
    except (OSError, ValueError):
        return


def candidates(session, channel, *, mutable=True):
    owned = turns(session, channel)
    if not owned:
        return {}
    root = Path(get_settings().codex_execution_root).absolute() / 'studio' / str(channel.id)
    result = {}
    for turn, job in owned:
        for item in _snapshots(root, turn, job):
            result[item.id] = item
    if not mutable:
        return result
    turn, job = owned[-1]
    # Current work belongs to the conversation even if a failed run left no receipt.
    work = root / 'persistent' / 'work'
    for item in _mutable(work, '/work/', 'work', turn, job):
        result[item.id] = item
    seen = {str(work)}
    for turn, job in owned:
        try:
            legacy = context.restore(job).work
        except (OSError, ValueError, KeyError, TypeError):
            legacy = root / 'rounds' / str(turn.id)
        if str(legacy) not in seen:
            seen.add(str(legacy))
            for item in _mutable(legacy, '/work/', 'work', turn, job):
                result[item.id] = item
    # Pre-round conversations used a single work folder within this same root.
    for item in _mutable(root / 'work', '/work/', 'work', *owned[-1]):
        result[item.id] = item
    linked = {channel.session_id: owned[-1]}
    linked.update({turn.event_session_id: (turn, job) for turn, job in owned if turn.event_session_id})
    for native_id, (turn, job) in linked.items():
        if not isinstance(native_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', native_id):
            continue
        directory = root / 'home' / '.codex' / 'generated_images' / native_id
        logical = '/home/runner/.codex/generated_images/' + native_id + '/'
        for item in _mutable(directory, logical, 'native', turn, job):
            result[item.id] = item
    return result


def read(item, version):
    if item.version != version:
        raise RecoveryError('文件已变化，请刷新列表后重新选择')
    if item.snapshot is not None:
        return read_image(root_path(item.control), item.snapshot)
    before, size = stamp(item.path)
    if before != version:
        raise RecoveryError('文件已变化，请刷新列表后重新选择')
    if size > MAX_BYTES:
        raise RecoveryError('单个文件不能超过 500 MB')
    with fs.reader(item.path) as stream:
        data = stream.read(MAX_BYTES + 1)
    after, _ = stamp(item.path)
    if before != after or len(data) != size:
        raise RecoveryError('文件在读取时发生变化，请刷新后重试')
    return validated(data, item.name)
