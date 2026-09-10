from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import select, func, or_, and_, cast, String
from app.contracts import business as b
from app.resource_models import FileRecord
from .models import TaskRecord, TaskSource, RoundRecord, ResultSlotRecord, ImageVersion
from .attempts import ExecutionSession
from app.modules.archives.models import ArchiveRecord
from app.modules.revisions.service import eligibility

STATE = {'queued': '排队中', 'running': '执行中', 'collecting': '执行中', 'cancelling': '执行中',
         'uncertain': '失败', 'failed': '失败', 'cancelled': '失败', 'succeeded': '待查看',
         'partial': '部分失败'}


def stamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def picture(file, version=None):
    data = dict(name=file.name, fileId=str(file.id), url=f'/api/v1/files/{file.id}/content')
    if version is not None:
        data['version'] = version
    return data


def find_task(session, task_id):
    task = session.get(TaskRecord, task_id)
    if not task or task.deleted_at:
        raise HTTPException(404, '任务不存在')
    return task


def serialize(session, task):
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)
                            .order_by(RoundRecord.created_at)).all()
    current = next(r for r in rounds if r.id == task.current_round_id)
    sources = session.scalars(select(TaskSource).where(TaskSource.task_id == task.id)
                             .order_by(TaskSource.slot)).all()
    slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)
                           .order_by(ResultSlotRecord.slot)).all()
    images = []
    for slot in slots:
        if slot.current_version_id:
            version = session.get(ImageVersion, slot.current_version_id)
            images.append(picture(session.get(FileRecord, version.file_id), version.version))
    identity = session.get(ExecutionSession, task.id) if task.execution_source == 'cli' else None
    incomplete = any(slot.current_version_id is None or slot.error for slot in slots)
    state = '部分失败' if current.status == 'succeeded' and incomplete else STATE[current.status]
    data = dict(id=str(task.id), name=task.name, mode=task.mode, template='',
        skillVersionId=str(task.skill_version_id), ownerId=str(task.owner_id),
        sessionId=identity.session_id if identity else None,
        state=state, progress=100 if state == '待查看' else None,
        images=images, sources=[picture(session.get(FileRecord, source.file_id)) for source in sources],
        feedback=[r.note for r in rounds if r.note], time=stamp(task.created_at), archived=bool(
            session.scalar(select(ArchiveRecord.id).where(ArchiveRecord.task_id == task.id,
                ArchiveRecord.deleted_at.is_(None)).limit(1))),
        currentRoundId=str(current.id), sku=task.sku, outputCount=len(slots), error=current.error,
        executionSource=task.execution_source)
    if task.template_snapshot:
        snapshot = task.template_snapshot
        data.update(template=snapshot['name'], templateId=snapshot['id'],
                    templateVersion=snapshot['version'], templateSnapshot=snapshot)
    return b.Task(**data)


def detail(session, task_id):
    task = find_task(session, task_id)
    slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)
                           .order_by(ResultSlotRecord.slot)).all()
    result_slots = []
    for slot in slots:
        versions = session.scalars(select(ImageVersion).where(ImageVersion.slot_id == slot.id)
                                  .order_by(ImageVersion.version)).all()
        result_slots.append(b.ResultSlot(slot=slot.slot, currentVersionId=str(slot.current_version_id)
            if slot.current_version_id else None, error=slot.error, versions=[b.ResultVersion(
                **picture(session.get(FileRecord, v.file_id), v.version), id=str(v.id),
                roundId=str(v.round_id), createdAt=stamp(v.created_at)) for v in versions]))
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)
                            .order_by(RoundRecord.created_at)).all()
    current = next(r for r in rounds if r.id == task.current_round_id)
    can_revise, can_retry, reason = eligibility(session, task, current, rounds)
    return b.TaskDetailData(task=serialize(session, task), slots=result_slots, rounds=[b.Round(
        id=str(r.id), taskId=str(task.id), operatorId=str(r.operator_id), target=r.target,
        note=r.note, state=STATE[r.status], createdAt=stamp(r.created_at), startedAt=stamp(r.started_at),
        finishedAt=stamp(r.finished_at), error=r.error) for r in rounds],
        executionControl=b.ExecutionControl(canRevise=can_revise, canRetry=can_retry, blockedReason=reason))


def list_tasks(session, query):
    statement = select(TaskRecord).join(RoundRecord, RoundRecord.id == TaskRecord.current_round_id).where(
        TaskRecord.deleted_at.is_(None))
    def count(extra=None):
        selected = statement.where(extra) if extra is not None else statement
        return session.scalar(select(func.count()).select_from(selected.subquery()))
    incomplete = select(ResultSlotRecord.id).where(ResultSlotRecord.task_id == TaskRecord.id,
        or_(ResultSlotRecord.current_version_id.is_(None), ResultSlotRecord.error.is_not(None))).exists()
    ready = and_(RoundRecord.status == 'succeeded', ~incomplete)
    partial = or_(RoundRecord.status == 'partial', and_(RoundRecord.status == 'succeeded', incomplete))
    stats = b.TaskStats(total=count(), processing=count(RoundRecord.status.in_(
        ['queued', 'running', 'collecting', 'cancelling'])),
        ready=count(ready), archived=count(select(ArchiveRecord.id).where(
            ArchiveRecord.task_id == TaskRecord.id, ArchiveRecord.deleted_at.is_(None)).exists()))
    if query.mode:
        statement = statement.where(TaskRecord.mode == query.mode)
    if query.search:
        identifier = cast(TaskRecord.id, String).icontains(query.search, autoescape=True)
        if query.search.replace('-', ''):
            identifier = func.replace(cast(TaskRecord.id, String), '-', '').icontains(
                query.search.replace('-', ''), autoescape=True)
        statement = statement.where(or_(TaskRecord.name.icontains(query.search, autoescape=True),
            TaskRecord.sku.icontains(query.search, autoescape=True),
            identifier))
    if query.state:
        public = {'processing': ('排队中', '执行中'), 'error': ('失败', '部分失败')}.get(
            query.state, (query.state,))
        filters = [RoundRecord.status.in_([key for key, value in STATE.items()
                   if value in public and key not in ('succeeded', 'partial')])]
        if '待查看' in public:
            filters.append(ready)
        if '部分失败' in public:
            filters.append(partial)
        statement = statement.where(or_(*filters))
    total = count()
    rows = session.scalars(statement.order_by(TaskRecord.created_at.desc(), TaskRecord.id).offset(
        (query.page - 1) * query.pageSize).limit(query.pageSize)).all()
    return b.TaskPage(items=[serialize(session, task) for task in rows], page=query.page,
                      pageSize=query.pageSize, total=total, stats=stats)
