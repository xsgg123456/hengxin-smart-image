"""Upload validation and bounded, disposable document parser processes."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

from fastapi import HTTPException

from app.modules.files.validation import safe_name

PARSER_VERSION = 'overseas-documents-v1'
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
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
        raise HTTPException(413, '单份资料不能超过 20 MiB')
    if not data:
        raise HTTPException(422, '资料不能为空')
    extension = Path((filename or '').replace('\\', '/')).suffix.lower()
    if extension == '.doc':
        raise HTTPException(422, '暂不支持旧版 DOC，请另存为 DOCX 或 PDF 后上传')
    allowed = {'requirement': {'.pdf', '.docx'},
               'competitor': {'.xls', '.xlsx', '.csv'}}
    if extension not in allowed.get(kind, set()):
        raise HTTPException(422, '资料类型不匹配：图需支持 PDF/DOCX，竞品支持 XLS/XLSX/CSV')
    signatures = {'.pdf': b'%PDF-', '.docx': b'PK\x03\x04',
                  '.xlsx': b'PK\x03\x04', '.xls': b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'}
    if extension in signatures and not data.startswith(signatures[extension]):
        raise HTTPException(422, '文件内容与扩展名不一致')
    if extension == '.csv' and b'\x00' in data:
        raise HTTPException(422, 'CSV 必须是 UTF-8 或 GB18030 文本文件')
    return safe_name(filename, extension), CONTENT_TYPES[extension]


def parse_document(data: bytes, name: str) -> str:
    if not data or len(data) > MAX_DOCUMENT_BYTES:
        raise ParseError('资料为空或超过 20 MiB 限制')
    extension = Path(name).suffix.lower()
    if extension not in CONTENT_TYPES:
        raise ParseError('不支持的资料格式，请转换后重试')
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
