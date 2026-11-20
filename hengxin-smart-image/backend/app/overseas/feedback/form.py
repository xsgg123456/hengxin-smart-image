from fastapi import HTTPException, Request
from starlette.formparsers import MultiPartException, MultiPartParser

from app.modules.files.multipart import BodyTooLarge
from .schemas import CreateFeedback

SCREENSHOT_LIMIT = 5 * 1024 * 1024
BODY_LIMIT = SCREENSHOT_LIMIT + 64 * 1024

form_schema = CreateFeedback.model_json_schema()
form_schema['properties']['screenshot'] = {'type': 'string', 'format': 'binary',
                                         'description': '单张 PNG、JPEG 或 WebP，最大 5 MiB'}
FEEDBACK_BODY = {'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': form_schema}}}}


async def parse_form(request: Request):
    if request.headers.get('content-type', '').partition(';')[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(422, '请使用 multipart/form-data 提交反馈')

    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > BODY_LIMIT:
                # Multipart exceptions close files already spooled by the parser.
                raise BodyTooLarge('反馈请求超过大小限制')
            yield chunk

    try:
        return await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=4,
                                     max_part_size=64 * 1024).parse()
    except BodyTooLarge:
        raise HTTPException(413, '反馈截图不能超过 5 MiB') from None
    except (MultiPartException, ValueError):
        raise HTTPException(422, '反馈表单无效，最多可上传一张截图') from None
