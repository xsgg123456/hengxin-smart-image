"""Run: backend/.venv Python scripts/performance/verify_media.py, after image build."""
import json
from pathlib import Path
import time

import httpx

from media_stack import MediaStack, ROOT
from media_cases import check_protocol, check_admission, check_outage, check_private_storage
from media_config import check_composition


def main():
    stack = MediaStack()
    result = {'passed': False, 'checks': [], 'scope': 'disposable real PostgreSQL/MinIO/two Nginx hops; no generation'}
    output = ROOT / 'output/performance-implementation-20260927/media-1b.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        check_composition(stack.path)
        result['checks'].append('production overlay merges correctly; media has no public port and explicit resource limits')
        stack.run('up', '-d', 'postgres', 'redis', 'minio', 'api', 'media-api')
        for attempt in range(40):
            try:
                data = json.loads(stack.seed()); break
            except (RuntimeError, json.JSONDecodeError):
                if attempt == 39: raise
                time.sleep(1)
        stack.run('up', '-d', 'web', 'outer')
        outer, inner, api = stack.origin('outer'), stack.origin('web'), stack.origin('api', 8000)
        with httpx.Client(trust_env=False, timeout=5) as client:
            for attempt in range(30):
                try:
                    if client.get(outer + '/api/v1/health/live').status_code == 200: break
                except httpx.HTTPError:
                    pass
                time.sleep(.3)
            else: raise AssertionError('gateway startup failed')
        stack.run('exec', '-T', 'web', 'nginx', '-t')
        check_protocol(stack, data, outer, inner, api)
        from variant_cases import check_variants
        result['variants'] = check_variants(stack, data, outer, inner)
        result['checks'].append('GET/HEAD/Range/304 auth, hashes, private headers, internal denial and legacy fallback')
        print('PASS protocol and authorization', flush=True)
        check_admission(stack, data, outer, inner)
        result['checks'].append('32 image / 2 ZIP / 2 upload admission across workers and both hops; interactive API and DB release')
        print('PASS admission, disconnect and database release', flush=True)
        check_private_storage(stack, data, outer, api)
        result['checks'].append('anonymous S3 denied; changed public policy fails closed after bounded recheck; missing objects return sanitized GET/HEAD errors')
        print('PASS private storage and missing objects', flush=True)
        check_outage(stack, data, outer)
        result['checks'].append('storage failure returns sanitized 503, no signature in logs')
        result['passed'] = True
    finally:
        try:
            stack.close()
            result['cleanup'] = 'removed only disposable project containers/network/tmpfs'
        finally:
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
