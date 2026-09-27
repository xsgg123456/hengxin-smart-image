"""Batch dependencies for the existing Task contract; no per-row SQL."""
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.resource_models import FileRecord, UserRecord
from app.modules.archives.models import ArchiveRecord
from app.modules.skills.models import SkillVersionRecord
from .models import TaskSource, RoundRecord, ResultSlotRecord, ImageVersion
from .attempts import ExecutionSession


class ListBatch:
    def __init__(self, session, tasks):
        self.records = {}
        self.groups = {}
        self.archived = set()
        if not tasks:
            return
        ids = [task.id for task in tasks]
        for model in (TaskSource, RoundRecord, ResultSlotRecord):
            statement = select(model).where(model.task_id.in_(ids))
            if model is RoundRecord:
                statement = statement.options(load_only(model.id, model.task_id, model.status,
                    model.error, model.note, model.created_at, raiseload=True)).order_by(model.created_at)
            else:
                statement = statement.order_by(model.slot)
            groups = defaultdict(list)
            for row in session.scalars(statement):
                groups[row.task_id].append(row)
            self.groups[model] = groups
        slots = [slot for group in self.groups[ResultSlotRecord].values() for slot in group]
        versions = self._load(session, ImageVersion, ImageVersion.id.in_(
            {slot.current_version_id for slot in slots if slot.current_version_id}))
        sources = [source for group in self.groups[TaskSource].values() for source in group]
        self._load(session, FileRecord, FileRecord.id.in_(
            {source.file_id for source in sources} | {v.file_id for v in versions}))
        self._load(session, UserRecord, UserRecord.id.in_({task.owner_id for task in tasks}))
        self._load(session, ExecutionSession, ExecutionSession.task_id.in_(ids))
        self._load(session, SkillVersionRecord, SkillVersionRecord.id.in_(
            {task.skill_version_id for task in tasks}))
        self.archived = set(session.scalars(select(ArchiveRecord.task_id).where(
            ArchiveRecord.task_id.in_(ids), ArchiveRecord.deleted_at.is_(None))))

    def _load(self, session, model, predicate):
        rows = session.scalars(select(model).where(predicate)).all()
        self.records[model] = {getattr(row, 'task_id' if model is ExecutionSession else 'id'): row
                               for row in rows}
        return rows

    def get(self, model, identifier):
        return self.records.get(model, {}).get(identifier)

    def related(self, model, task_id):
        return self.groups.get(model, {}).get(task_id, [])
