"""Original bytes are retained; documents are downloaded without active rendering."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from zipfile import ZipFile, BadZipFile
from fastapi import HTTPException, Response
from app.core.config import get_settings
from app.modules.files.validation import safe_name
from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from app.overseas.tasks.service import lock_actor
from app.overseas.materials.parsers import CONTENT_TYPES
from .models import Upload
from . import queries, material_list

from app.overseas.upload_limits import MAX_UPLOAD_BYTES

MAX_BYTES = MAX_UPLOAD_BYTES
TYPES = {**CONTENT_TYPES, '.txt': 'text/plain', '.pptx':
         'application/vnd.openxmlformats-officedocument.presentationml.presentation',
         '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}


def validate(data, filename):
    extension = Path((filename or '').replace(chr(92), '/')).suffix.lower()
    if extension in ('.doc', '.ppt'):
        raise HTTPException(422, '旧版DOC/PPT请转换成DOCX/PPTX或PDF后上传')
    if extension not in TYPES or not data:
        raise HTTPException(422, '文件为空或格式不支持')
    if len(data) > MAX_BYTES:
        raise HTTPException(413, '单个附件不能超过 500 MB')
    signatures = {'.pdf': b'%PDF-', '.xls': bytes.fromhex('d0cf11e0a1b11ae1')}
    if extension in signatures and not data.startswith(signatures[extension]):
        raise HTTPException(422, '文件内容与扩展名不一致')
    if extension in ('.docx', '.pptx', '.xlsx'):
        try:
            with ZipFile(BytesIO(data)) as archive:
                prefix = {'.docx': 'word/', '.pptx': 'ppt/', '.xlsx': 'xl/'}[extension]
                if '[Content_Types].xml' not in archive.namelist() or not any(
                        name.startswith(prefix) for name in archive.namelist()):
                    raise ValueError()
                if sum(item.file_size for item in archive.infolist()) > 200 * 1024 * 1024:
                    raise ValueError()
        except (BadZipFile, ValueError):
            raise HTTPException(422, 'Office文件结构无效或解压后过大') from None
    if extension in ('.txt', '.csv'):
        if b'\x00' in data:
            raise HTTPException(422, '文本文件包含无效内容')
        try:
            data.decode('utf-8-sig')
        except UnicodeError:
            try:
                data.decode('gb18030')
            except UnicodeError:
                raise HTTPException(422, '文本须使用UTF-8或GB18030编码') from None
    if TYPES[extension].startswith('image/'):
        from PIL import Image
        try:
            with Image.open(BytesIO(data)) as image:
                expected = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}[extension]
                if image.format != expected or image.width * image.height > 60000000:
                    raise ValueError()
                image.verify()
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height * getattr(image, 'n_frames', 1) > 60000000:
                    raise ValueError()
                for frame in range(getattr(image, 'n_frames', 1)):
                    image.seek(frame)
                    image.load()
        except Exception:
            raise HTTPException(422, '图片无效或尺寸过大') from None
    return safe_name(filename, extension), TYPES[extension]


def read(store, row):
    stream = None
    try:
        stream = store.open(row)
        data = stream.read(MAX_BYTES + 1)
        if len(data) != row.size_bytes or sha256(data).hexdigest() != row.checksum:
            raise ValueError()
        return data
    except Exception:
        raise HTTPException(503, '文件读取或完整性校验失败') from None
    finally:
        if stream is not None:
            try:
                stream.close()
            finally:
                stream.release_conn()


def upload(session, store, actor, task_id, data, filename):
    name, content_type = validate(data, filename)
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    if task.status != 'studio':
        raise HTTPException(409, '当前任务不能上传工作台附件')
    identity = uuid4()
    row = Upload(id=identity, task_id=task.id, name=name, content_type=content_type,
        size_bytes=len(data), checksum=sha256(data).hexdigest(),
        bucket=get_settings().minio_bucket, object_key=f'studio/uploads/{task.id}/{identity}')
    try:
        store.put(row, data)
    except Exception:
        raise HTTPException(503, '附件存储失败，请重试') from None
    material_state = material_list.uploaded(session, task.id, row.checksum)
    session.add(row)
    session.flush()
    result = queries.asset(row, 'upload')
    result['materialState'] = material_state
    session.commit()
    return result


def content(session, store, actor, task_id, identity, is_picture=False, *, head=False, preview=False):
    task = queries.access(session, actor, task_id)
    row = (queries.picture(session, task, identity) if is_picture else
           queries.attachment(session, task, 'upload:' + str(identity))[0])
    row = FileDelivery.capture(row)
    session.close()
    if not is_picture:
        return deliver(store, row, head=head, preview=preview)
    if head:
        return deliver(store, row, head=True, preview=True)
    data = read(store, row)
    disposition = 'inline' if row.content_type.startswith('image/') or row.content_type == 'application/pdf' else 'attachment'
    return Response(data, media_type=row.content_type, headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': disposition + "; filename*=UTF-8''" + quote(row.name, safe='')})
