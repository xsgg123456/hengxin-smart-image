from tempfile import SpooledTemporaryFile
from starlette.responses import StreamingResponse
from zipfile import ZipFile, ZIP_STORED
from fastapi import HTTPException
from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from sqlalchemy import select, func, or_
from app.overseas.tasks.models import Task
from app.overseas.tasks.queries import detail
from app.overseas.permissions import principal_for, require_task_access, task_filter
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import lock_gate
from app.overseas.plans.service import mutation, complete
from app.overseas.pictures.queries import slots, version
from app.overseas.studio.files import read
from .models import Archive, ArchiveAsset, ArchiveEvent
from .audit import record_confirmation, event_dto, history
from .snapshot import protect, metadata, assets
from . import deletion


def archive(session, actor, task_id, body, key, store):
    target = str(task_id)
    actor, task, digest, previous = mutation(session, actor, task_id, body, key, 'archived', target)
    if previous:
        session.refresh(previous)
        if previous.body_hash != digest:
            raise HTTPException(409, '该归档已删除，请使用新的请求重新归档')
        result = detail(session, task.id, actor)
        session.commit()
        return result
    lock_gate(session)
    pictures = slots(session, task.id)
    active = session.scalar(select(Job.id).where(Job.task_id == task.id, Job.status.not_in(TERMINAL)).limit(1))
    if (task.status == 'archived' or active or not pictures
            or any(not p.version or p.approved_version != p.version for p in pictures)):
        raise HTTPException(409, '全部当前图片通过且所有执行已结束后才能归档')
    record = Archive(task_id=task.id, versions=[str(version(session, p).id) for p in pictures])
    session.add(record)
    session.flush()
    protect(session, store, record, task)
    record_confirmation(session, record, actor, record.versions)
    task.status = 'archived'
    return complete(session, actor, task, 'archived', target, key, digest)


def picture_dto(row):
    return dict(id=str(row.id), name=row.name, sku=row.sku, width=row.width, height=row.height,
        contentType=row.content_type, sizeBytes=row.size_bytes,
        sourceConversationId=str(row.source_conversation_id) if row.source_conversation_id else None,
        sourceConversationName=row.source_conversation_name,
        url=f'/api/overseas/v1/archives/{row.archive_id}/pictures/{row.id}/content')


def dto(record, cover=None, latest=None):
    return dict(id=str(record.id), taskId=str(record.task_id) if record.task_id else None,
        sourceDeleted=record.task_id is None, productName=record.product_name, brand=record.brand,
        platform=record.platform, skus=record.skus or [], pictureCount=len(record.versions),
        createdAt=record.created_at, latestArchive=event_dto(latest) if latest else None, cover=picture_dto(cover) if cover else None)


def listing(session, actor, product='', brand='', sku='', search='', page=1, page_size=20):
    principal = principal_for(session, actor)
    filters = [task_filter(principal, Archive.created_by, Archive.designer_id)]
    for field, value in ((Archive.product_name, product), (Archive.brand, brand)):
        if value:
            filters.append(field.icontains(value, autoescape=True))
    sku_match = lambda value: Archive.sku_search.icontains(value, autoescape=True)
    if sku:
        filters.append(sku_match(sku))
    if search:
        filters.append(or_(Archive.product_name.icontains(search, autoescape=True),
                           Archive.brand.icontains(search, autoescape=True), sku_match(search)))
    total = session.scalar(select(func.count()).select_from(Archive).where(*filters))
    first_asset = (select(ArchiveAsset.id).where(ArchiveAsset.archive_id == Archive.id)
        .order_by(ArchiveAsset.position, ArchiveAsset.id).limit(1).correlate(Archive).scalar_subquery())
    last_event = (select(ArchiveEvent.id).where(ArchiveEvent.archive_id == Archive.id)
        .order_by(ArchiveEvent.created_at.desc(), ArchiveEvent.id.desc()).limit(1).correlate(Archive).scalar_subquery())
    rows = session.execute(select(Archive, ArchiveAsset, ArchiveEvent).outerjoin(ArchiveAsset, ArchiveAsset.id == first_asset)
        .outerjoin(ArchiveEvent, ArchiveEvent.id == last_event)
        .where(*filters).order_by(Archive.created_at.desc(), Archive.id)
        .offset((page - 1) * page_size).limit(page_size))
    return {'items': [{**dto(row, cover, latest), **deletion.fields(session, row)} for row, cover, latest in rows], 'total': total, 'page': page, 'pageSize': page_size}


def access(session, actor, archive_id, store, metadata_only=False, protect_originals=True):
    task, record, receipt = deletion.locked(session, archive_id)
    if record is None:
        raise HTTPException(404, '归档不存在')
    if record.created_by is None and task:
        metadata(session, record, task)
    require_task_access(principal_for(session, actor), record.created_by, record.designer_id)
    if receipt:
        if not metadata_only:
            deletion.available(session, record.id)
    elif protect_originals:
        protect(session, store, record, task)
    else:
        deletion.available(session, record.id)
    return record


def view(session, store, actor, archive_id):
    record = access(session, actor, archive_id, store, metadata_only=True)
    pictures = assets(session, record)
    audit = history(session, record.id)
    result = {**dto(record, pictures[0] if pictures else None), **audit,
        'latestArchive': audit['archiveHistory'][0] if audit['archiveHistory'] else None,
        'pictures': [picture_dto(row) for row in pictures], **deletion.fields(session, record)}
    session.commit()
    return result


def content(session, store, actor, archive_id, picture_id, *, head=False, thumbnail=False, if_none_match=None):
    # Listing/detail performs legacy snapshot protection. Delivery must check the
    # requested existing asset, without repairing a deleted row or reading every original.
    record = access(session, actor, archive_id, store, protect_originals=False)
    row = session.get(ArchiveAsset, picture_id)
    if not row or row.archive_id != record.id:
        raise HTTPException(404, '归档图片不存在')
    captured = FileDelivery.capture(row)
    session.commit()
    session.close()
    return deliver(store, captured, head=head, preview=True, thumbnail=thumbnail, if_none_match=if_none_match)


def download(session, store, actor, archive_id):
    record = access(session, actor, archive_id, store)
    output = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    total_bytes = 0
    try:
        with ZipFile(output, 'w', ZIP_STORED) as zipped:
            for index, row in enumerate(assets(session, record)):
                safe_sku = ''.join(c if c.isalnum() or c in '-_' else '_' for c in row.sku)[:80]
                extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[row.content_type]
                total_bytes += row.size_bytes
                if total_bytes > 1024 * 1024 * 1024:
                    raise HTTPException(413, '归档超过1 GiB限制')
                zipped.writestr(f'{index + 1:03d}_{safe_sku}{extension}', read(store, row))
        session.commit()
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
