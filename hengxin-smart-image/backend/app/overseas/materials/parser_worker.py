"""Disposable parser entry point; no application configuration or DB startup."""
import json
import os
import sys
from pathlib import Path


def main():
    if os.name == 'posix':
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from app.overseas.materials.document_formats import DocumentError, extract

    source, result = map(Path, sys.argv[1:3])
    try:
        payload = {'text': extract(source.read_bytes(), source.suffix)}
    except DocumentError as exc:
        payload = {'error': str(exc)}
    except Exception:
        # Library errors may contain local paths, source contents or internals.
        payload = {'error': '资料损坏、格式不受支持或超出安全限制，请检查文件后重试'}
    result.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
