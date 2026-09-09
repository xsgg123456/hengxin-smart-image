from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.modules.skills.package_validator import MAX_ZIP

UPLOAD_BODY = {'requestBody': {'required': True, 'content': {'multipart/form-data': {
    'schema': {'type': 'object', 'required': ['file', 'mode', 'version'], 'properties': {
        'file': {'type': 'string', 'format': 'binary'}, 'mode': {'type': 'string'},
        'version': {'type': 'string'},
    }},
}}}}


async def parse_upload(request):
    async def bounded():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_ZIP + 65536:
                raise MultiPartException('ZIP 上传超过 20 MiB')
            yield chunk
    if request.headers.get('content-type', '').split(';')[0].strip() != 'multipart/form-data':
        raise HTTPException(422, '请使用 multipart/form-data')
    try:
        form = await MultiPartParser(request.headers, bounded(), max_files=1,
                                     max_fields=2, max_part_size=1024).parse()
    except (MultiPartException, ValueError):
        raise HTTPException(422, 'ZIP 上传无效或超过 20 MiB') from None
    if (len(form.multi_items()) != 3 or not isinstance(form.get('file'), UploadFile)
            or not isinstance(form.get('mode'), str) or not isinstance(form.get('version'), str)):
        await form.close()
        raise HTTPException(422, '需要 file、mode 和 version')
    return form
