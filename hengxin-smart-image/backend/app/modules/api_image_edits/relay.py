"""Exactly one upstream request; retry decisions belong to the durable worker."""
import base64
import binascii
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import urllib3
from urllib3.exceptions import ConnectTimeoutError, HTTPError, NewConnectionError, SSLError

from .config import PARAMETERS, get_api_settings


class RelayError(Exception):
    def __init__(self, kind, code, message, retry_after=None):
        super().__init__(message)
        self.kind, self.code, self.retry_after = kind, code, retry_after


@dataclass(frozen=True)
class RelayResult:
    result_url: str | None = field(default=None, repr=False)
    image_bytes: bytes | None = field(default=None, repr=False)
    request_id: str | None = None


def retry_after_seconds(value):
    if not value:
        return None
    try:
        seconds = int(value) if str(value).isdigit() else int(
            (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        return max(0, min(seconds, 86400))
    except (TypeError, ValueError, OverflowError):
        return None


def safe_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', value) else None


CHANNEL_CODES = frozenset({
    'insufficient_quota', 'quota_exceeded', 'credit_balance_exhausted',
    'insufficient_balance', 'billing_hard_limit_reached', 'invalid_api_key',
    'model_not_found', 'invalid_model', 'model_not_supported', 'model_unavailable',
})


def channel_rejection(response):
    # Error details are inspected locally, never persisted or returned to the UI.
    try:
        body, deadline = bytearray(), time.monotonic() + 3
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            connection = getattr(response, 'connection', None)
            if connection is not None and connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(1024, decode_content=True)
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > 16384:
                return False
        error = json.loads(body).get('error')
        return isinstance(error, dict) and any(
            isinstance(error.get(key), str) and error[key].lower() in CHANNEL_CODES
            for key in ('code', 'type'))
    except (ValueError, TypeError, AttributeError, HTTPError, OSError):
        return False


class RelayClient:
    def __init__(self, settings=None, pool=None):
        self.settings = settings or get_api_settings()
        self.pool = pool or urllib3.PoolManager(retries=False)

    def preflight(self, original_bytes, original_mime, material_bytes, material_mime, prompt,
                  parameters=None, additional_images=None):
        if not self.settings.api_key.get_secret_value():
            raise RelayError('channel', 'API_KEY_MISSING', 'API 换图密钥尚未配置')
        if parameters is not None and parameters != PARAMETERS:
            raise RelayError('permanent', 'INVALID_PARAMETERS', '任务模型参数不符合固定配置')
        if (original_mime not in ('image/jpeg', 'image/png', 'image/webp') or
                (material_bytes is not None and material_mime not in ('image/jpeg', 'image/png', 'image/webp'))):
            raise RelayError('permanent', 'INVALID_INPUT', '输入图片格式不受支持')
        if additional_images is not None and (len(additional_images) not in (1, 2) or
                material_bytes is None or any(not data or mime not in ('image/jpeg', 'image/png', 'image/webp')
                                               for data, mime in additional_images)):
            raise RelayError('permanent', 'INVALID_INPUT', '修改参照图片不完整或格式不受支持')

    def generate(self, original_bytes, original_mime, material_bytes, material_mime, prompt,
                 parameters=None, additional_images=None):
        self.preflight(original_bytes, original_mime, material_bytes, material_mime, prompt, parameters,
                       additional_images)
        config = self.settings
        images = []
        for data, mime in [(original_bytes, original_mime), (material_bytes, material_mime),
                           *(additional_images or [])]:
            if data is None:
                continue
            images.append({'image_url': f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')})
        body = json.dumps({**PARAMETERS, 'prompt': prompt, 'images': images}, ensure_ascii=False).encode()
        response = None
        started = time.monotonic()
        try:
            response = self.pool.request(
                'POST', config.base_url + '/v1/images/edits', body=body,
                headers={'Authorization': 'Bearer ' + config.api_key.get_secret_value(),
                         'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=urllib3.Timeout(connect=10, read=config.request_timeout_seconds,
                                        total=config.request_timeout_seconds),
                retries=False, redirect=False, preload_content=False)
            return self._parse(response, started)
        except RelayError:
            raise
        except (NewConnectionError, ConnectTimeoutError):
            raise RelayError('retryable', 'CONNECT_FAILED', '连接中转站失败，可稍后重试') from None
        except SSLError:
            # TLS failures can also occur while reading a response, after send.
            raise RelayError('uncertain', 'TLS_UNCERTAIN', '安全连接中断，需先核实上游执行状态') from None
        except (HTTPError, OSError, TimeoutError):
            raise RelayError('uncertain', 'REQUEST_UNCERTAIN', '请求结果尚未确认，请先核实上游执行状态') from None
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def _parse(self, response, started=None):
        status = response.status
        if status in (401, 402, 403, 404):
            raise RelayError('channel', 'CHANNEL_REJECTED', '中转站拒绝调用，请检查密钥、额度和模型配置')
        if 400 <= status <= 599 and channel_rejection(response):
            raise RelayError('channel', 'CHANNEL_REJECTED', '中转站拒绝调用，请检查密钥、额度和模型配置')
        if status == 429 or 500 <= status <= 599:
            raise RelayError('retryable', f'HTTP_{status}', '中转站繁忙或暂时不可用',
                             retry_after_seconds(response.headers.get('Retry-After')))
        if status == 408:
            raise RelayError('uncertain', 'UPSTREAM_TIMEOUT', '中转站请求超时，需核实是否已生成')
        if status != 200:
            raise RelayError('permanent', f'HTTP_{status}', '中转站未接受本次图片请求')
        limit = self.settings.max_download_bytes * 4 // 3 + 65536
        chunks, count = [], 0
        started = started if started is not None else time.monotonic()
        while True:
            remaining = self.settings.request_timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise RelayError('uncertain', 'RESPONSE_LIMIT', '结果响应超时，需核实上游结果')
            connection = getattr(response, 'connection', None)
            if connection is not None and connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(65536, decode_content=True)
            if not chunk:
                break
            count += len(chunk)
            if count > limit or time.monotonic() - started > self.settings.request_timeout_seconds:
                raise RelayError('uncertain', 'RESPONSE_LIMIT', '结果响应超出限制，需核实上游结果')
            chunks.append(chunk)
        try:
            payload = json.loads(b''.join(chunks))
            rows = payload['data']
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                raise ValueError()
            item = rows[0]
            request_id = safe_request_id(response.headers.get('x-request-id'))
            if isinstance(item.get('url'), str) and 0 < len(item['url']) <= 8192:
                return RelayResult(result_url=item['url'], request_id=request_id)
            if isinstance(item.get('b64_json'), str):
                image = base64.b64decode(item['b64_json'], validate=True)
                if not image or len(image) > self.settings.max_download_bytes:
                    raise ValueError()
                return RelayResult(image_bytes=image, request_id=request_id)
            raise ValueError()
        except (ValueError, KeyError, TypeError, binascii.Error):
            raise RelayError('uncertain', 'INVALID_RESULT', '中转站未返回可识别图片，需核实生成结果') from None
