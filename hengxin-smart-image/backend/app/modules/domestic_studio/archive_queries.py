"""Shared domestic archive reads use only independent archive-owned copies."""
from fastapi import HTTPException
from sqlalchemy import func, select

from .archive_models import Archive, ArchiveDeletion, ArchiveFile
from .archive_service import file_dto, verify_snapshot
from .queries import timestamp


def available(session, identity):
    record = session.get(Archive, identity)
    if record is None or record.status != 'ready' or session.get(ArchiveDeletion, identity) is not None:
        raise HTTPException(404, '归档不存在或正在删除')
    return record


def files(session, identity, kind=None):
    query = select(ArchiveFile).where(ArchiveFile.archive_id == identity)
    if kind is not None:
        query = query.where(ArchiveFile.kind == kind)
    return list(session.scalars(query.order_by(ArchiveFile.position, ArchiveFile.id)))


def dto(session, record):
    pictures = files(session, record.id, 'picture')
    receipt = session.get(ArchiveDeletion, record.id)
    return dict(id=str(record.id), productName=record.product_name, workspace=record.workspace,
        conversationName=record.source_conversation_name, createdAt=timestamp(record.created_at),
        pictureCount=len(pictures), cover=file_dto(pictures[0]) if pictures and not receipt else None,
        deletionStatus=receipt.status if receipt else None, deletionError=receipt.error if receipt else None)


def listing(session, search='', workspace='', page=1, page_size=20):
    if workspace and workspace not in ('camera', 'case'):
        raise HTTPException(422, '归档来源无效')
    filters = [Archive.status == 'ready']
    if search.strip():
        filters.append(Archive.product_name.icontains(search.strip(), autoescape=True))
    if workspace:
        filters.append(Archive.workspace == workspace)
    total = session.scalar(select(func.count()).select_from(Archive).where(*filters))
    rows = session.scalars(select(Archive).where(*filters).order_by(Archive.created_at.desc(), Archive.id)
                           .offset((page - 1) * page_size).limit(page_size))
    return dict(items=[dto(session, row) for row in rows], total=total, page=page, pageSize=page_size)


def verified(session, identity):
    record = available(session, identity)
    rows = files(session, record.id)
    try:
        verify_snapshot(record, rows)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(503, '归档文件清单不完整，请联系管理员') from None
    return record, rows


def detail(session, identity):
    record, rows = verified(session, identity)
    records = {str(row.id): row for row in rows}
    turns = record.snapshot.get('turns') if isinstance(record.snapshot, dict) else None
    if not isinstance(turns, list):
        raise HTTPException(503, '归档资料校验失败，请联系管理员')
    result = []
    for turn in turns:
        if not isinstance(turn, dict):
            raise HTTPException(503, '归档资料校验失败，请联系管理员')
        data = {key: turn.get(key) for key in ('id', 'text', 'actorName', 'createdAt', 'reply', 'replyAt',
                                               'status', 'error', 'transcript')}
        data['imageEdits'] = turn.get('imageEdits', [])
        for field, expected in (('attachments', 'upload'), ('pictures', 'picture'),
                                ('referencePictures', 'picture'), ('outputs', 'output')):
            values = turn.get(field)
            if not isinstance(values, list):
                raise HTTPException(503, '归档资料校验失败，请联系管理员')
            mapped = []
            for value in values:
                row = records.get(value.get('id')) if isinstance(value, dict) else None
                if row is None or row.kind != expected:
                    raise HTTPException(503, '归档文件清单不完整，请联系管理员')
                mapped.append(file_dto(row))
            data[field] = mapped
        result.append(data)
    return {**dto(session, record), 'turns': result}


def file(session, archive_id, file_id):
    _, rows = verified(session, archive_id)
    row = next((item for item in rows if item.id == file_id), None)
    if row is None:
        raise HTTPException(404, '归档文件不存在')
    return row
