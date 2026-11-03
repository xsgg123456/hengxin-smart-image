"""Fixed upstream metadata boundary. Never expose bearer or signed URLs."""
import json
import os
from pathlib import Path
import re
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.auth.models import Member
from app.overseas.tasks.queries import eligible
from app.overseas.upload_limits import MAX_UPLOAD_BYTES
from app.modules.files.validation import safe_name
from . import http_logging  # noqa: F401 - redact transport diagnostics before requests

ORIGIN = 'https://design.qhhengxin.top'
MAX_METADATA_BYTES = 8_000_000
PUBLIC_FIELDS = ('id', 'brandSeq', 'title', 'productName', 'language', 'lingxingSku',
                 'brandLineId', 'brandName', 'platformId', 'platformName', 'platformCode',
                 'status', 'priority', 'hours', 'quantity', 'setCount', 'expectedDate',
                 'operatorName', 'designerName', 'scheduleStart', 'scheduleEnd',
                 'designLink', 'shareLink', 'createdAt')


def fetch(sku):
    key = os.environ.get('OVERSEAS_DESIGN_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, '需求来源尚未配置，请联系管理员')
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False,
                          trust_env=False) as client:
            with client.stream('GET', ORIGIN + '/api/open/sku', params={'sku': sku},
                               headers={'Authorization': f'Bearer {key}'}) as response:
                if response.status_code != 200:
                    raise HTTPException(502, '获取需求失败，请稍后重试')
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_METADATA_BYTES:
                        raise HTTPException(502, '来源需求数据过大，请联系管理员')
                    chunks.append(chunk)
                data = json.loads(b''.join(chunks))
        if not isinstance(data, dict) or not isinstance(data.get('list'), list):
            raise ValueError('invalid metadata')
        if not all(isinstance(row, dict) and 'id' in row and isinstance(row.get('files', []), list)
                   and all(isinstance(file, dict) and 'id' in file and isinstance(file.get('filename'), str)
                           and isinstance(file.get('size'), int) for file in row.get('files', []))
                   for row in data['list']):
            raise ValueError('invalid requirements')
        return data
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(502, '需求来源暂时不可用，请稍后重试') from None


def public_metadata(session, sku, data):
    result = []
    for item in data['list']:
        # Explicit field allowlist prevents future upstream credentials leaking.
        row = {key: item[key] for key in PUBLIC_FIELDS if key in item}
        row['id'] = str(item['id'])
        for key in ('platformName', 'brandName', 'title', 'productName', 'language',
                    'designerName', 'status', 'createdAt'):
            row[key] = str(row.get(key) or '')
        row['files'] = [{key: file.get(key) for key in
            ('id', 'filename', 'size', 'contentType', 'category')} for file in item.get('files', [])]
        for file in row['files']:
            file['id'] = str(file['id'])
        name = str(item.get('designerName') or '').strip()
        candidates = [m for m in session.scalars(select(Member).where(Member.name == name,
            Member.directory_state == 'enrolled')) if eligible(session, m)] if name else []
        row['matchedDesigner'] = ({'id': str(candidates[0].id), 'name': candidates[0].name,
            'department': candidates[0].department} if len(candidates) == 1 else None)
        result.append(row)
    return {'sku': sku, 'count': data.get('count', len(result)),
            'truncated': bool(data.get('truncated', False)), 'list': result}


def selected(data, requirement_id):
    matches = [row for row in data['list'] if str(row['id']) == str(requirement_id)]
    if len(matches) != 1:
        raise HTTPException(409, '所选需求已变化，请重新获取需求')
    return matches[0]


def attachment_metadata(item):
    try:
        identifier, filename, size = str(item['id']), item['filename'], item['size']
        if not identifier or len(identifier) > 200 or not isinstance(filename, str):
            raise ValueError()
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_UPLOAD_BYTES:
            raise ValueError()
        suffix = Path(filename.replace('\\', '/')).suffix.lower()
        safe_suffix = re.sub(r'[^a-z0-9.]', '_', suffix)[:30]
        return {'source_file_id': identifier, 'filename': safe_name(filename, safe_suffix),
                'size': size, 'kind': 'requirement' if suffix in ('.ppt', '.pptx') else 'competitor'}
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, '来源附件信息无效，附件须非空且单份不超过 500 MB') from None
