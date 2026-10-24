"""One automatic receipt pass; file failures never change successful execution."""
from datetime import datetime
import logging
from uuid import UUID
from sqlalchemy import select

from app.overseas.execution import claims
from app.overseas.tasks.models import Task, TaskDeletion
from .models import Conversation, ConversationDeletion, Turn, Picture, OutputFile
from . import output_store
from . import context_fs as fs, delivery_context as context, delivery_snapshot as snapshots

log = logging.getLogger(__name__)


class OwnershipLost(ValueError):
    pass


def guarded(session, job_id, token):
    from app.overseas.execution.models import Job
    task_id = session.scalar(select(Job.task_id).where(Job.id == job_id))
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    job = claims.locked_job(session, job_id)
    if not task or not claims.valid(job, token) or not job.process_exited:
        raise OwnershipLost('Delivery ownership lost')
    turn = session.get(Turn, UUID(job.payload['turnId']))
    if (not turn or turn.job_id != job.id or turn.task_id != task.id
            or str(turn.conversation_id) != job.payload['conversationId']
            or session.get(TaskDeletion, task.id)
            or session.get(ConversationDeletion, turn.conversation_id)):
        raise OwnershipLost('Delivery was cancelled or deleted')
    return job, turn


def progress(factory, job_id, token, summary, state, expected, order=()):
    with factory.begin() as session:
        job, turn = guarded(session, job_id, token)
        channel = session.get(Conversation, turn.conversation_id)
        if not channel or channel.session_id not in (None, summary.session_id):
            raise OwnershipLost('Delivery session mismatch')
        channel.session_id = summary.session_id
        turn.reply, turn.delivery_error = summary.final_text, None
        saved = [identity for model in (Picture, OutputFile) for identity in
                 session.scalars(select(model.id).where(model.turn_id == turn.id))]
        result = dict(job.result or {})
        result.update(reply=summary.final_text, sessionId=summary.session_id,
            deliveryStatus=dict(state=state, expected=expected, saved=len(saved)))
        if order:
            result['deliveryOrder'] = list(order)
        if job.result != result:
            job.result = result
            job.version += 1
            from app.overseas.execution.events import record
            record(session, job)
        return len(saved)


def row_data(job, target, image, item):
    return output_store.row_data(job, target, image, UUID(item['pictureId']))


def upload(factory, job, token, store, data, image):
    return output_store.save(factory, job, data['source_path'], image, data['id'], store,
                             lambda session: guarded(session, job.id, token))


def finish(factory, job_id, token, summary, expected=None, issues=()):
    """Settle the proven model result independently of missing files."""
    with factory.begin() as session:
        job, turn = guarded(session, job_id, token)
        channel = session.get(Conversation, turn.conversation_id)
        if not channel or channel.session_id not in (None, summary.session_id):
            raise OwnershipLost('Delivery session mismatch')
        channel.session_id = summary.session_id
        turn.reply = summary.final_text
        turn.delivery_error = '；'.join(dict.fromkeys(issues)) or None
        saved = sum(len(list(session.scalars(select(model.id).where(model.turn_id == turn.id))))
                    for model in (Picture, OutputFile))
        result = dict(job.result or {})
        result.pop('deliveryRetryAt', None)
        result.pop('deliveryAttempts', None)
        state = 'partial' if issues or expected is None or saved < expected else 'complete'
        result.update(reply=summary.final_text, sessionId=summary.session_id,
            deliveryStatus=dict(state=state, expected=expected, saved=saved))
        claims.end(session, job, 'succeeded', result=result)
        if result.get('deliveryOriginalCompletedAt'):
            job.completed_at = datetime.fromisoformat(result['deliveryOriginalCompletedAt'])
            from app.overseas.execution.models import JobOutbox
            outbox = session.get(JobOutbox, job.id)
            if outbox:
                outbox.completed_at = job.completed_at
    return state == 'complete'


def finish_failed(factory, job_id, token, summary):
    return finish(factory, job_id, token, summary,
                  issues=['自动收取未完成，请通过“取回文件”保存尚存原件；无需重新生成'])


def deliver(factory, job, token, workspace, summary, store, *, recovering=False):
    from .delivery import enumerate_delivery, collect_reference
    progress(factory, job.id, token, summary, 'capturing', None)
    root = workspace.control / 'delivery'
    if recovering and snapshots.load(root) is None:
        return finish_failed(factory, job.id, token, summary)
    with factory.begin() as session:
        guarded(session, job.id, token)
        context.close_native(workspace, summary.session_id)
        manifest = snapshots.load(root)
        if manifest is None:
            selection_path = workspace.control / 'delivery-selection.json'
            if selection_path.exists():
                selection = fs.load(selection_path)
            else:
                references, proven, warnings = enumerate_delivery(workspace, summary)
                selection = dict(references=references, proven=proven, issues=warnings)
                fs.save(selection_path, selection)
            manifest = snapshots.begin(root, context.identity(job), summary.final_text,
                                       summary.session_id, [row[0] for row in selection['references']])
        else:
            if manifest['identity'] != {**context.identity(job), 'sessionId': summary.session_id}:
                raise OwnershipLost('Frozen delivery does not belong to this invocation')
            if manifest['finalText'] != summary.final_text:
                raise ValueError('Frozen final reply changed')
    selection = fs.load(workspace.control / 'delivery-selection.json')
    expected = len(manifest['targets'])
    issues = list(selection.get('issues', []))
    for item in manifest['items']:
        if item['status'] == 'captured':
            continue
        if recovering:
            issues.append(f"{item['target']}: 原件尚未保留，请通过‘取回文件’选择尚存文件")
            continue
        try:
            with factory.begin() as session:
                guarded(session, job.id, token)
                selection = fs.load(workspace.control / 'delivery-selection.json')
                target = item['target']
                logical = next(row[1] for row in selection['references'] if row[0] == target)
                image = collect_reference(workspace, summary, target, logical, selection['proven'])
                snapshots.capture(root, target, image)
        except OwnershipLost:
            raise
        except Exception:
            issues.append(f"{item['target']}: 原件尚未保留，请通过‘取回文件’重试")
            log.warning('Studio file capture failed job=%s item=%s', job.id, item['order'])
    manifest = snapshots.load(root)
    order = [item['pictureId'] for item in manifest['items'] if item['status'] == 'captured']
    progress(factory, job.id, token, summary, 'saving' if manifest['ready'] else 'capturing', expected, order)
    from .delivery_snapshot_fs import read_image
    for item in manifest['items']:
        if item['status'] != 'captured':
            continue
        try:
            target = item['target']
            image = read_image(root, item)
            upload(factory, job, token, store, row_data(job, target, image, item), image)
            progress(factory, job.id, token, summary, 'saving', expected, order)
        except OwnershipLost:
            raise
        except Exception:
            issues.append(f"{item['name']}: 自动保存失败，请通过‘取回文件’重试")
            log.warning('Studio file save failed job=%s item=%s', job.id, item['order'])
    return finish(factory, job.id, token, summary, expected, issues)
