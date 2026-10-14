"""Human requirements gate and versioned operator resubmissions."""
from fastapi import HTTPException
from sqlalchemy import delete, select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.permissions import principal_for, require_task_access
from .models import RequirementsReview, TaskRequest, TaskSku
from .queries import detail, get_task
from .service import lock_actor, record_change, request_record, require_designer


def mutation(session, actor, task_id, body, key, operation, permission):
    actor = lock_actor(session, actor, permission)
    digest = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, operation, str(task_id), key, digest)
    task = get_task(session, task_id, lock=True)
    principal = principal_for(session, actor)
    if permission == 'task.design':
        require_task_access(principal, task.created_by, task.designer_id, permission)
    elif task.created_by != actor.id and not principal.roles & {'operator_manager', 'super_admin'}:
        raise HTTPException(403, '只能修改本人创建的图需')
    if not previous and task.version != body.version:
        raise HTTPException(409, '任务已被修改，请刷新后重试')
    return actor, task, digest, previous


def finish(session, actor, task, operation, key, digest, event, before_designer=None):
    task.version += 1
    task.updated_at = utcnow()
    record_change(session, task, actor, event, before_designer)
    request_record(session, actor, operation, str(task.id), key, digest, task)
    session.flush()
    result = detail(session, task.id, actor)
    session.commit()
    return result


def replay(session, task, actor):
    result = detail(session, task.id, actor)
    session.commit()
    return result


def review(session, actor, task_id, body, key, store=None):
    actor, task, digest, previous = mutation(
        session, actor, task_id, body, key, 'requirements_review', 'task.design')
    if previous:
        return replay(session, task, actor)
    if task.status != 'pending_review':
        raise HTTPException(409, '只有待设计审核的图需可以审核')
    if body.decision == 'reject' and not body.comment.strip():
        raise HTTPException(422, '请填写退回原因')
    skus = session.scalars(select(TaskSku).where(TaskSku.task_id == task.id).order_by(TaskSku.position))
    session.add(RequirementsReview(task_id=task.id, actor_id=actor.id, actor_name=actor.name,
        decision=body.decision, comment=body.comment, version=task.version,
        submission={'name': task.name, 'productName': task.product_name, 'brand': task.brand,
            'platform': task.platform, 'market': task.market, 'remarks': task.remarks,
            'skus': [{'code': sku.code} for sku in skus], 'designerId': str(task.designer_id),
            'materialIds': list(task.material_ids or [])}))
    task.requirements_approved = body.decision == 'approve'
    task.status = 'submitted' if task.requirements_approved else 'returned'
    if task.requirements_approved and task.workflow == 'studio':
        task.status = 'studio'
    elif task.requirements_approved:
        from app.overseas.plans.service import enqueue_analysis
        enqueue_analysis(session, task, store=store)
    return finish(session, actor, task, 'requirements_review', key, digest,
                  'task.requirements_approved' if task.requirements_approved else 'task.requirements_rejected')


def resubmit(session, actor, task_id, body, key):
    actor, task, digest, previous = mutation(
        session, actor, task_id, body, key, 'requirements_resubmit', 'task.create')
    if previous:
        return replay(session, task, actor)
    if task.status != 'returned':
        raise HTTPException(409, '只有退回运营的图需可以修改重提')
    require_designer(session, body.designerId)
    before_designer = task.designer_id if body.designerId != task.designer_id else None
    # Reassignment remains governed by its existing dedicated permission.
    if body.designerId != task.designer_id:
        require_task_access(principal_for(session, actor), task.created_by, task.designer_id, 'task.reassign')
    from app.overseas.materials.service import bind
    bind(session, actor, task, body.materialIds, resubmit=True)
    task.name, task.product_name, task.brand = body.name, body.productName, body.brand
    task.platform, task.market, task.remarks = body.platform, body.market, body.remarks
    task.designer_id = body.designerId
    session.execute(delete(TaskSku).where(TaskSku.task_id == task.id))
    session.add_all([TaskSku(task_id=task.id, code=sku.code, code_key=sku.code.casefold(), position=i)
                     for i, sku in enumerate(body.skus)])
    return finish(session, actor, task, 'requirements_resubmit', key, digest, 'task.resubmitted', before_designer)
