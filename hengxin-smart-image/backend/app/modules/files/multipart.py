from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.modules.files.validation import MAX_UPLOAD_BYTES

MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024  # Multipart headers/boundaries only.
UPLOAD_BODY = {'requestBody': {'required': True, 'content': {'multipart/form-data': {
    'schema': {'type': 'object', 'required': ['file'], 'properties': {
        'file': {'type': 'string', 'format': 'binary'},
    }},
}}}}


class BodyTooLarge(MultiPartException):
    pass


async def parse_upload(request: Request):
    """Called only after identity dependencies; cap actual bytes even without a length."""
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(422, '请使用 multipart/form-data 上传图片')
    length = request.headers.get('content-length')
    if length is not None:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(422, '无效的请求长度') from None
        if size < 0:
            raise HTTPException(422, '无效的请求长度')
        if size > MAX_BODY_BYTES:
            raise HTTPException(413, '单张图片不能超过 10 MiB')

    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_BODY_BYTES:
                raise BodyTooLarge('上传请求超限')
            yield chunk

    try:
        form = await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=0).parse()
    except BodyTooLarge:
        raise HTTPException(413, '单张图片不能超过 10 MiB') from None
    except (MultiPartException, ValueError):
        raise HTTPException(422, '请上传一个完整的图片文件') from None
    file = form.get('file')
    if len(form.multi_items()) != 1 or not isinstance(file, UploadFile):
        await form.close()
        raise HTTPException(422, '缺少图片文件 file')
    return form, file
