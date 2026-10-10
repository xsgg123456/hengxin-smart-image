"""On-demand business evidence, separate from polling/list task queries."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.material_history import read_history
from app.execution.material_bindings import historical_inputs
from app.resource_models import FileRecord
from .attempts import ExecutionAttempt
from .models import RoundRecord, ImageVersion, ResultSlotRecord
from .queries import find_task, picture


def materials(session, task_id, round_id):
    task = find_task(session, task_id)
    row = session.get(RoundRecord, round_id)
    if not row or row.task_id != task.id:
        raise HTTPException(404, '轮次不存在')
    data = dict(taskId=str(task.id), roundId=str(row.id), note=row.note, status=row.status,
                systemPrompts=[], toolCalls=[], inputs=[], outputs=[], notices=[])
    expired = row.execution_config.get('historyExpired')
    evidence = row.execution_config.get('materials', {})
    for key in ('systemPrompts', 'toolCalls', 'notices'):
        data[key] = list(evidence.get(key, []))
    if expired:
        data['notices'].append('本轮会话历史已按 7 天保留规则清理，正式图片仍可查看。')
    attempt = session.scalar(select(ExecutionAttempt).where(ExecutionAttempt.round_id == row.id))
    if task.execution_source == 'cli' and attempt and not evidence.get('captured') and not row.execution_config.get('historyExpired'):
        next_start = session.scalar(select(ExecutionAttempt.started_at).where(
            ExecutionAttempt.task_id == task.id, ExecutionAttempt.started_at > attempt.started_at)
            .order_by(ExecutionAttempt.started_at).limit(1))
        end = row.finished_at or next_start
        history = read_history(get_settings().codex_execution_root, task.id, row.id, attempt.started_at, end)
        for key in ('systemPrompts', 'toolCalls'):
            if history[key]:
                data[key] = history[key]
        data['notices'].extend(history['notices'])
    if not expired and not data['systemPrompts']:
        data['notices'].append('系统任务提示词未采集，不使用现行模板重建历史内容。')
    if not expired and not data['toolCalls']:
        data['notices'].append('实际生图工具提示词尚未采集或无法回溯。')

    def add(role, label, file_id, version=None, output=False):
        try:
            file = session.get(FileRecord, UUID(str(file_id))) if file_id else None
        except ValueError:
            file = None
        item = {'role': role, 'label': label, 'picture': None}
        if file and file.status == 'ready' and not file.deleted_at:
            item['picture'] = picture(file, version)
        else:
            item['reason'] = '历史图片缺失或不可用'
        if version is not None:
            item['version'] = version
        data['outputs' if output else 'inputs'].append(item)

    manifest = evidence.get('manifest')
    if manifest:
        for index, item in enumerate(manifest.get('inputs', []), 1):
            add('source', f'素材 {index}', item.get('fileId'))
        for item in manifest.get('targets', []):
            index = item.get('taskSlot', item['slot']) + 1
            if item.get('originalFileId') or item.get('fileId'):
                add('original', f'原始底图 {index}', item.get('originalFileId') or item.get('fileId'))
            if item.get('currentPath'):
                add('base', f'基础成品 {index}', item.get('currentFileId'), item.get('currentVersion'))
    else:
        bindings = evidence.get('historicalInputs')
        if bindings is None:
            bindings = historical_inputs(session, task, row, get_settings().codex_execution_root, data['systemPrompts'])
        for item in bindings:
            add(item['role'], item['label'], item['fileId'])
        if any(not item['verified'] for item in bindings):
            data['notices'].append('部分图片仅为任务冻结关联文件，缺少本轮引用与文件校验凭据，不能确认实际输入。')
        if row.base_version_id:
            base = session.get(ImageVersion, row.base_version_id)
            add('base', '基础成品', base.file_id if base else None, base.version if base else None)
        elif session.scalar(select(RoundRecord.id).where(RoundRecord.task_id == task.id,
                RoundRecord.created_at < row.created_at).limit(1)):
            data['notices'].append('本轮未冻结基础成品版本，未使用当前版本替代历史。')
    if row.annotation_file_id:
        add('annotation', '标注参考图', row.annotation_file_id)
    elif not expired:
        data['notices'].append('本轮未提交标注图。')
    outputs = session.execute(select(ImageVersion, ResultSlotRecord.slot).join(ResultSlotRecord,
        ImageVersion.slot_id == ResultSlotRecord.id).where(ImageVersion.round_id == row.id,
        ResultSlotRecord.task_id == task.id).order_by(ResultSlotRecord.slot)).all()
    for version, slot in outputs:
        add('output', f'本轮结果 {slot + 1}', version.file_id, version.version, True)
    order = {'base': 0, 'original': 1, 'source': 2, 'annotation': 3}
    data['inputs'].sort(key=lambda item: order.get(item['role'], 4))
    texts = [p['text'] for p in data['systemPrompts']] + [p['prompt'] for p in data['toolCalls']]
    if any('[内部路径已隐藏]' in text or '[凭据已隐藏]' in text or '[已隐藏]' in text for text in texts):
        data['notices'].append('提示词中的凭据或服务器私有路径已脱敏；业务文字未截断。')
    data['notices'] = list(dict.fromkeys(data['notices']))
    return data
