"""Bounded private downloads; this module never opens a database session."""
from hashlib import sha256
import ipaddress
from pathlib import Path
import re
import socket
from tempfile import TemporaryFile
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
import httpx
from fastapi import HTTPException
from app.overseas.upload_limits import MAX_UPLOAD_BYTES
from app.overseas.materials.parsers import CONTENT_TYPES
from . import source


class TransferError(Exception):
    pass


def validate_url(url, *, initial=False):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise TransferError('来源附件下载地址无效')
    original = host == 'design.qhhengxin.top'
    r2 = host.endswith('.r2.cloudflarestorage.com') or host.endswith('.r2.dev')
    if not (original or (r2 and not initial)):
        raise TransferError('来源附件下载地址不受信任')
    if original and (not re.fullmatch(r'/api/files/[A-Za-z0-9_-]+/download', unquote(parsed.path))
                     or not parse_qs(parsed.query).get('token')):
        raise TransferError('来源附件签名无效，请重试')
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
            raise TransferError('来源附件下载地址不受信任')
    except OSError:
        raise TransferError('来源附件暂时无法连接，请重试') from None
    return url


def download(client, url, target, expected_size, progress):
    validate_url(url, initial=True)
    for redirect in range(4):
        validate_url(url, initial=redirect == 0)
        with client.stream('GET', url, headers={'Accept-Encoding': 'identity'}) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('location')
                if not location:
                    raise TransferError('来源附件下载重定向无效')
                url = urljoin(url, location)
                continue
            if response.status_code in (401, 403, 404):
                raise TransferError('来源附件签名已失效，请重试')
            if response.status_code != 200:
                raise TransferError('来源附件下载失败，请重试')
            length = response.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > MAX_UPLOAD_BYTES):
                raise TransferError('来源附件超过 500 MB 限制')
            size, digest = 0, sha256()
            for chunk in response.iter_bytes(chunk_size=256 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise TransferError('来源附件超过 500 MB 限制')
                target.write(chunk)
                digest.update(chunk)
                progress(min(90, int(size / max(1, expected_size) * 90)))
            if size == 0 or size != expected_size:
                raise TransferError('来源附件大小已变化，请重新获取需求')
            return size, digest.hexdigest()
    raise TransferError('来源附件下载重定向过多')


def put_file(store, record, file):
    """Use the existing private store client without loading a 500 MB bytes object."""
    store.ensure_private(record.bucket, force=False)
    store.client.put_object(record.bucket, record.object_key, file, record.size_bytes,
                            content_type=record.content_type)


def transfer(job, record, store, progress):
    try:
        metadata = source.fetch(job.sku)
        requirement = source.selected(metadata, job.requirement_id)
        files = [file for file in requirement.get('files', []) if str(file.get('id')) == job.source_file_id]
        if len(files) != 1:
            raise TransferError('来源附件已删除或变化，请重新获取需求')
        current = source.attachment_metadata(files[0])
        if current['size'] != job.size or current['filename'] != job.filename:
            raise TransferError('来源附件已变化，请重新获取需求')
        relative = files[0].get('downloadUrl')
        if not isinstance(relative, str) or not relative.startswith('/api/files/'):
            raise TransferError('来源附件缺少有效下载签名')
        url = urljoin(source.ORIGIN, relative)
        with TemporaryFile(prefix='overseas-draft-') as file:
            with httpx.Client(timeout=httpx.Timeout(60, connect=5), follow_redirects=False,
                              trust_env=False) as client:
                record.size_bytes, record.checksum = download(client, url, file, job.size, progress)
            record.content_type = CONTENT_TYPES.get(Path(job.filename).suffix.lower(), 'application/octet-stream')
            file.seek(0)
            progress(95)
            put_file(store, record, file)
    except HTTPException:
        raise TransferError('来源附件暂时不可用，请重试') from None
    except httpx.HTTPError:
        raise TransferError('来源附件传输中断，请重试') from None
