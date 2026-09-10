import hashlib
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from app.modules.skills.models import SkillVersionRecord
from app.modules.skills.package_validator import MAX_ZIP, validate_package
from app.modules.tasks.models import TaskSource, ResultSlotRecord, ImageVersion
from app.resource_models import FileRecord


def read_object(store, record, limit):
    stream = store.open(record)
    try:
        data = stream.read(limit + 1)
    finally:
        stream.close()
        stream.release_conn()
    if len(data) > limit or hashlib.sha256(data).hexdigest() != record.checksum:
        raise ValueError('冻结文件校验失败')
    return data


def prepare_materials(session, store, task, round, workspace):
    manifest = {'mode': task.mode, 'inputs': [], 'targets': []}
    sources = session.scalars(select(TaskSource).where(TaskSource.task_id == task.id)
                              .order_by(TaskSource.slot)).all()
    template = task.template_snapshot
    targets = template['images'] if template else [{'fileId': str(s.file_id)} for s in sources]
    selected = list(range(len(targets))) if round.target is None else [round.target]
    for category, items in [('inputs', [{'fileId': str(s.file_id)} for s in sources]),
                            ('targets', [targets[i] for i in selected])]:
        directory = workspace.work / category
        directory.mkdir()
        for index, item in enumerate(items):
            file = session.get(FileRecord, UUID(item['fileId']))
            if not file or file.status != 'ready':
                raise ValueError('冻结图片不可用')
            data = read_object(store, file, 10 * 1024 * 1024)
            name = f'{index:02d}' + {'image/png': '.png', 'image/jpeg': '.jpg',
                                    'image/webp': '.webp'}[file.content_type]
            (directory / name).write_bytes(data)
            manifest[category].append({'slot': index, 'path': f'/work/{category}/{name}'})
    current_dir = workspace.work / 'current'
    current_dir.mkdir()
    for local_slot, task_slot in enumerate(selected):
        target = manifest['targets'][local_slot]
        target['taskSlot'] = task_slot
        slot = session.scalar(select(ResultSlotRecord).where(
            ResultSlotRecord.task_id == task.id, ResultSlotRecord.slot == task_slot))
        if slot and slot.current_version_id:
            image = session.get(ImageVersion, slot.current_version_id)
            file = session.get(FileRecord, image.file_id)
            if not file or file.status != 'ready' or file.deleted_at:
                raise ValueError('当前结果图片不可用')
            data = read_object(store, file, 10 * 1024 * 1024)
            name = f'{local_slot:02d}' + {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[file.content_type]
            (current_dir / name).write_bytes(data)
            target['currentPath'] = '/work/current/' + name
            target['currentVersion'] = image.version
    version = session.get(SkillVersionRecord, task.skill_version_id)
    raw = read_object(store, version, MAX_ZIP)
    if hashlib.sha256(raw).hexdigest() != task.skill_snapshot['checksum']:
        raise ValueError('Skill 与任务冻结版本不一致')
    package = validate_package(raw, task.mode, task.skill_snapshot['version'])
    for name, data in package.files.items():
        destination = workspace.work / 'skill' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return manifest
