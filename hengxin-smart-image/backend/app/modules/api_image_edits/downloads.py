"""Download result images without credentials, redirects, or untrusted network targets."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import urllib3

from .config import get_api_settings


class ResultDownloadError(Exception):
    pass


def approved_target(url, hosts):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or host not in hosts or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.fragment
                or any(ord(char) < 32 for char in url)):
            raise ValueError()
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError()
        # Pin the checked address; a second hostname lookup cannot rebind to a private IP.
        return host, addresses[0], (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
    except (ValueError, TypeError, OSError):
        raise ResultDownloadError('结果地址不可用或不在允许的图片域名范围') from None


def download_result(url, settings=None, pool_factory=None):
    settings = settings or get_api_settings()
    host, address, path = approved_target(url, settings.allowed_result_hosts)
    pool = (pool_factory or urllib3.HTTPSConnectionPool)(
        address, port=443, server_hostname=host, assert_hostname=host,
        cert_reqs='CERT_REQUIRED', retries=False,
        timeout=urllib3.Timeout(connect=10, read=settings.download_timeout_seconds,
                                total=settings.download_timeout_seconds))
    response = None
    try:
        response = pool.urlopen('GET', path, headers={'Host': host, 'Accept': 'image/*'},
                                retries=False, redirect=False, preload_content=False)
        if response.status != 200:
            raise ResultDownloadError('结果图片暂不可下载')
        declared = response.headers.get('Content-Length')
        if declared is not None and (not declared.isdigit() or int(declared) > settings.max_download_bytes):
            raise ResultDownloadError('结果图片大小超出限制')
        chunks, count, started = [], 0, time.monotonic()
        while True:
            remaining = settings.download_timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ResultDownloadError('结果图片下载超出时间限制')
            connection = getattr(response, 'connection', None)
            if connection is not None and connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(65536, decode_content=True)
            if not chunk:
                break
            count += len(chunk)
            if count > settings.max_download_bytes or time.monotonic() - started > settings.download_timeout_seconds:
                raise ResultDownloadError('结果图片下载超出大小或时间限制')
            chunks.append(chunk)
        if not count:
            raise ResultDownloadError('结果图片为空')
        return b''.join(chunks)
    except ResultDownloadError:
        raise
    except (urllib3.exceptions.HTTPError, OSError, ValueError):
        raise ResultDownloadError('结果图片下载失败，可重试收图') from None
    finally:
        if response is not None:
            response.close()
            response.release_conn()
        pool.close()
