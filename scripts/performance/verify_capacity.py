"""Run isolated PostgreSQL/MinIO capacity verification; no production env or model calls."""
import json

from media_stack import MediaStack, ROOT


def main():
    stack = MediaStack()
    result = {'passed': False}
    output = ROOT / 'output/performance-implementation-20260927/capacity-1b.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        stack.run('up', '-d', 'postgres', 'minio')
        probe = stack.run('run', '--rm', '--no-deps', '-T', 'api', 'python', '/checks/capacity_probe.py', timeout=240)
        result['checks'] = json.loads(probe.stdout.strip().splitlines()[-1])
        result['passed'] = True
    finally:
        try:
            stack.close()
            result['cleanup'] = 'removed only disposable project containers/network/tmpfs'
        finally:
            output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
