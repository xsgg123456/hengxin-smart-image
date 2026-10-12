from tempfile import SpooledTemporaryFile
from starlette.responses import StreamingResponse
from uuid import UUID
from zipfile import ZipFile, ZIP_STORED
from fastapi import HTTPException, Response
from sqlalchemy import select, func, or_
from app.overseas.tasks.models import Task, TaskSku
from app.overseas.tasks.queries import get_task, detail
from app.overseas.permissions import principal_for, require_task_access, task_filter
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import lock_gate
from app.overseas.plans.service import mutation, complete
from app.overseas.pictures.queries import slots, version
from app.overseas.pictures.models import PictureVersion, Picture
from app.overseas.pictures.files import read
from .models import Archive


def archive(session, actor, task_id, body, key):
    target = str(task_id)
    actor, task, digest, previous = mutation(session, actor, task_id, body, key, 'archived', target)
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    lock_gate(session)
    pictures = slots(session, task.id)
    active = session.scalar(select(Job.id).where(Job.task_id == task.id, Job.status.not_in(TERMINAL)).limit(1))
    if (task.status == 'archived' or active or not pictures
            or any(not p.version or p.approved_version != p.version for p in pictures)):
        raise HTTPException(409, '全部当前图片通过且所有执行已结束后才能归档')
    session.add(Archive(task_id=task.id, versions=[str(version(session, p).id) for p in pictures]))
    task.status = 'archived'
    return complete(session, actor, task, 'archived', target, key, digest)


def listing(session, actor, product='', brand='', sku='', search='', page=1, page_size=20):
    principal = principal_for(session, actor)
    filters = [task_filter(principal, Task.created_by, Task.designer_id)]
    for field, value in ((Task.product_name, product), (Task.brand, brand)):
        if value:
            filters.append(field.icontains(value, autoescape=True))
    sku_match = lambda value: select(TaskSku.id).where(TaskSku.task_id == Task.id,
        TaskSku.code.icontains(value, autoescape=True)).exists()
    if sku:
        filters.append(sku_match(sku))
    if search:
        filters.append(or_(Task.product_name.icontains(search, autoescape=True),
                           Task.brand.icontains(search, autoescape=True), sku_match(search)))
    query = select(Archive, Task).join(Task, Task.id == Archive.task_id).where(*filters)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(query.order_by(Archive.created_at.desc(), Archive.id)
                           .offset((page - 1) * page_size).limit(page_size))
    items = [{'id': str(a.id), 'taskId': str(t.id), 'productName': t.product_name, 'brand': t.brand,
              'skus': [{'code': code} for code in session.scalars(select(TaskSku.code)
                       .where(TaskSku.task_id == t.id).order_by(TaskSku.position))],
              'pictureCount': len(a.versions), 'createdAt': a.created_at} for a, t in rows]
    return {'items': items, 'total': total, 'page': page, 'pageSize': page_size}


def download(session, store, actor, archive_id):
    record = session.get(Archive, archive_id)
    if not record:
        raise HTTPException(404, '归档不存在')
    task = get_task(session, record.task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    output = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    total_bytes = 0
    try:
        with ZipFile(output, 'w', ZIP_STORED) as zipped:
            for index, identity in enumerate(record.versions):
                item = session.get(PictureVersion, UUID(identity))
                picture = session.get(Picture, item.picture_id) if item else None
                if not picture or picture.task_id != task.id:
                    raise HTTPException(503, '归档版本关联异常')
                safe_sku = ''.join(c if c.isalnum() or c in '-_' else '_' for c in picture.sku)[:80]
                extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[item.content_type]
                total_bytes += item.size_bytes
                if total_bytes > 1024 * 1024 * 1024:
                    raise HTTPException(413, '归档超过1 GiB限制')
                zipped.writestr(f'{index + 1:03d}_{safe_sku}_{picture.position + 1}{extension}', read(store, item))
    except Exception:
        output.close()
        raise
    output.seek(0)
    def chunks():
        try:
            while chunk := output.read(65536):
                yield chunk
        finally:
            output.close()
    return StreamingResponse(chunks(), media_type='application/zip', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f'attachment; filename="archive-{record.id}.zip"'})
