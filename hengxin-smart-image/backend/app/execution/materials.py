import hashlib
import io
import re
import zipfile
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from app.modules.skills.models import SkillVersionRecord
from app.modules.skills.package_validator import MAX_ZIP, validate_package
from app.modules.tasks.models import TaskSource, ResultSlotRecord, ImageVersion
from app.resource_models import FileRecord


class SkillDeploymentError(ValueError):
    pass


def read_object(store, record, limit):
    stream = store.open(record)
    try:
        data = stream.read(limit + 1)
    finally:
        stream.close()
        if hasattr(stream, 'release_conn'):
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
    single_base = None
    if round.target is not None:
        slot = session.scalar(select(ResultSlotRecord).where(
            ResultSlotRecord.task_id == task.id, ResultSlotRecord.slot == round.target))
        single_base = (round.base_version_id if round.execution_config.get('singleInputFrozen')
                       else slot.current_version_id if slot else None)
    inputs = [] if single_base and task.mode == 'text' else [{'fileId': str(s.file_id)} for s in sources]
    for category, items in [('inputs', inputs),
                            ('targets', [targets[i] for i in selected])]:
        original = category == 'targets' and bool(single_base) and task.mode == 'wallpaper'
        directory = workspace.work / ('original' if original else category)
        directory.mkdir()
        for index, item in enumerate(items):
            if category == 'targets' and single_base and not original:
                manifest['targets'].append({'slot': index})
                continue
            file = session.get(FileRecord, UUID(item['fileId']))
            if not file or file.status != 'ready' or file.deleted_at:
                raise ValueError('对应原始底图不可用' if original else '冻结图片不可用')
            data = read_object(store, file, 10 * 1024 * 1024)
            name = f'{index:02d}' + {'image/png': '.png', 'image/jpeg': '.jpg',
                                    'image/webp': '.webp'}[file.content_type]
            (directory / name).write_bytes(data)
            if original:
                manifest['targets'].append({'slot': index, 'originalPath': f'/work/original/{name}'})
            else:
                manifest[category].append({'slot': index, 'path': f'/work/{category}/{name}'})
    current_dir = workspace.work / 'current'
    current_dir.mkdir()
    for local_slot, task_slot in enumerate(selected):
        target = manifest['targets'][local_slot]
        target['taskSlot'] = task_slot
        slot = session.scalar(select(ResultSlotRecord).where(
            ResultSlotRecord.task_id == task.id, ResultSlotRecord.slot == task_slot))
        frozen = round.target is not None and round.execution_config.get('singleInputFrozen')
        version_id = round.base_version_id if frozen else (slot.current_version_id if slot else None)
        if version_id:
            image = session.get(ImageVersion, version_id)
            if not image or not slot or image.slot_id != slot.id:
                raise ValueError('冻结基础版本与目标图片不一致')
            file = session.get(FileRecord, image.file_id)
            if not file or file.status != 'ready' or file.deleted_at:
                raise ValueError('当前结果图片不可用')
            data = read_object(store, file, 10 * 1024 * 1024)
            name = f'{local_slot:02d}' + {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[file.content_type]
            (current_dir / name).write_bytes(data)
            target['currentPath'] = '/work/current/' + name
            target['currentVersion'] = image.version
            if frozen:
                target['baseVersionId'] = str(image.id)
    if round.target is not None:
        manifest['singleRevision'] = True
    if round.annotation_file_id:
        file = session.get(FileRecord, round.annotation_file_id)
        if not file or file.status != 'ready' or file.deleted_at:
            raise ValueError('冻结圈注截图不可用')
        directory = workspace.work / 'annotation'
        directory.mkdir()
        name = 'reference' + {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[file.content_type]
        (directory / name).write_bytes(read_object(store, file, 10 * 1024 * 1024))
        manifest['annotationPath'] = '/work/annotation/' + name
    if single_base:
        workspace.use_skill = False
        return manifest
    version = session.get(SkillVersionRecord, task.skill_version_id)
    if not version or version.version != task.skill_snapshot['version'] or version.skill.mode != task.mode:
        raise ValueError('Skill 与任务冻结版本不一致')
    name = version.skill.name
    workspace.skill_name = name if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name) else f'legacy-{version.id}'
    manifest['skillPath'] = workspace.skill_path + '/SKILL.md'
    if version.source_type == 'local':
        from app.worker.skill_check import validate_local
        try:
            tree = validate_local(version, task.skill_snapshot['checksum'])
        except Exception as error:
            raise SkillDeploymentError('skill_deployment_invalid') from error
        workspace.local_skill = tree.path
        return manifest
    raw = read_object(store, version, MAX_ZIP)
    if hashlib.sha256(raw).hexdigest() != task.skill_snapshot['checksum']:
        raise ValueError('Skill 与任务冻结版本不一致')
    package = validate_package(raw, task.mode, None if version.catalog_snapshot else task.skill_snapshot['version'])
    for name, data in package.files.items():
        destination = workspace.work / 'skills' / workspace.skill_name / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    if version.catalog_snapshot:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for entry in archive.infolist():
                destination = workspace.work / 'skills' / workspace.skill_name / entry.filename
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.chmod(0o600 | ((entry.external_attr >> 16) & 0o111))
    return manifest
