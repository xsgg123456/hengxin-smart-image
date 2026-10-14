"""Upload validation and bounded, disposable document parser processes."""
import json
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

from fastapi import HTTPException

from app.modules.files.validation import safe_name

from app.overseas.upload_limits import MAX_UPLOAD_BYTES

PARSER_VERSION = 'overseas-documents-v1'
MAX_DOCUMENT_BYTES = MAX_UPLOAD_BYTES
MAX_PARSE_BYTES = 20 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
PARSE_TIMEOUT_SECONDS = 15
PARSE_SLOTS = BoundedSemaphore(2)
CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.csv': 'text/csv',
}


class ParseError(ValueError):
    """Safe, user-facing failure; the original upload remains available."""


def validate_document(data: bytes, filename: str, kind: str) -> tuple[str, str]:
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, '单份资料不能超过 500 MB')
    if not data:
        raise HTTPException(422, '资料不能为空')
    extension = Path((filename or '').replace('\\', '/')).suffix.lower()
    if kind not in {'requirement', 'competitor'}:
        raise HTTPException(422, '资料类别无效')
    # Unknown formats are private downloadable originals, never inline content.
    return safe_name(filename, re.sub(r'[^a-z0-9.]', '_', extension)[:30]), CONTENT_TYPES.get(extension, 'application/octet-stream')



def parse_document(data: bytes, name: str) -> str:
    if not data or len(data) > MAX_PARSE_BYTES:
        raise ParseError('原件已保存，资料为空或超过自动解析的 20 MiB 限制，请下载原件查看；可直接提交审核')
    extension = Path(name).suffix.lower()
    if extension not in CONTENT_TYPES:
        raise ParseError('原件已保存，此格式暂不支持文字解析，请下载原件查看；可直接提交审核')
    # Files avoid unbounded stdout pipes and pipe backpressure/deadlocks.
    with PARSE_SLOTS, TemporaryDirectory(prefix='overseas-parse-') as folder:
        source = Path(folder) / ('source' + extension)
        result = Path(folder) / 'result.json'
        source.write_bytes(data)
        command = [sys.executable, '-m', 'app.overseas.materials.parser_worker',
                   str(source), str(result)]
        try:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        except OSError:
            raise ParseError('解析进程暂不可用，请重试') from None
        try:
            try:
                process.wait(timeout=PARSE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                raise ParseError('资料解析超时，请拆分文件后重试') from None
            if process.returncode or not result.is_file():
                raise ParseError('资料解析失败或超出资源限制，请检查文件后重试')
            if result.stat().st_size > MAX_TEXT_BYTES * 6 + 4096:
                raise ParseError('解析文字超出 2 MiB 限制，请拆分文件')
            payload = json.loads(result.read_text(encoding='utf-8'))
            if payload.get('error'):
                raise ParseError(payload['error'])
            text = payload['text']
            if not isinstance(text, str) or not text.strip():
                raise ParseError('资料中没有可读取的文字或数值')
            if len(text.encode('utf-8')) > MAX_TEXT_BYTES:
                raise ParseError('解析文字超出 2 MiB 限制，请拆分文件')
            return text
        except (OSError, ValueError, KeyError) as exc:
            if isinstance(exc, ParseError):
                raise
            raise ParseError('资料解析结果无效，请重试') from None
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
