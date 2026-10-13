from fastapi import HTTPException
from app.core.idempotency import fingerprint_payload, lookup_request
from app.overseas.members import service as members
from app.overseas.permissions import authorize_member
from .models import Task, TaskEvent, TaskOutbox, TaskRequest, TaskSku
from .queries import detail, eligible


def lock_actor(session, actor, permission):
    members.lock_permissions(session)
    actor = members.get_member(session, actor.id)
    authorize_member(session, actor, permission)
    return actor


def require_designer(session, designer_id):
    member = members.get_member(session, designer_id)
    if not eligible(session, member):
        raise HTTPException(422, '请选择有效的设计成员')
    return member


def record_change(session, task, actor, kind, before=None):
    event = TaskEvent(task_id=task.id, kind=kind, actor_id=actor.id, actor_name=actor.name,
                      title={'task.created': '提交图需' if task.status in ('submitted', 'analyzing', 'pending_review') else '保存图需', 'task.assigned': '改派设计',
                             'task.materials_submitted': '提交资料', 'task.analysis': '开始分析',
                             'task.plan_confirmed': '确认方案', 'task.generation_retry': '重试SKU生图',
                             'task.picture_approved': '审核图片通过', 'task.picture_revision': '发起单图返工',
                             'task.archived': '整套归档', 'task.requirements_approved': '图需审核通过',
                             'task.requirements_rejected': '图需退回运营', 'task.resubmitted': '修改图需并重新提交'}[kind],
                      before_designer_id=before, after_designer_id=task.designer_id, version=task.version)
    session.add(event)
    session.flush()
    session.add(TaskOutbox(event_id=event.id, topic=kind, payload={
        'taskId': str(task.id), 'eventId': str(event.id), 'version': task.version,
        'designerId': str(task.designer_id)}))


def request_record(session, actor, operation, target, key, body_hash, task):
    session.add(TaskRequest(user_id=actor.id, operation=operation, target=target, key=key,
                            body_hash=body_hash, task_id=task.id))


def create_task(session, actor, body, key):
    actor = lock_actor(session, actor, 'task.create')
    # Keep Phase19 request hashes replayable when materialIds was omitted.
    body_hash = fingerprint_payload(body.model_dump(mode='json', exclude_none=True))
    previous = lookup_request(session, TaskRequest, actor.id, 'create', '', key, body_hash)
    if previous:
        result = detail(session, previous.task_id, actor, lock=True)
        session.commit()
        return result, False
    require_designer(session, body.designerId)
    task = Task(name=body.name, product_name=body.productName, brand=body.brand,
                platform=body.platform, market=body.market, remarks=body.remarks,
                created_by=actor.id, designer_id=body.designerId, status='created', version=1, workflow='studio')
    session.add(task)
    session.flush()
    session.add_all([TaskSku(task_id=task.id, code=item.code, code_key=item.code.casefold(), position=i)
                     for i, item in enumerate(body.skus)])
    if body.materialIds is not None:
        from app.overseas.materials.service import bind
        bind(session, actor, task, body.materialIds)
    record_change(session, task, actor, 'task.created')
    request_record(session, actor, 'create', '', key, body_hash, task)
    session.flush()
    result = detail(session, task.id, actor)
    session.commit()
    return result, True
