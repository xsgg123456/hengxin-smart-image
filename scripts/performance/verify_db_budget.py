"""No production env, no paid calls; disposable PostgreSQL and current backend image."""
from copy import deepcopy
import json

from db_budget_config import check_budget, validate, EXPECTED
from media_stack import MediaStack, ROOT


def main():
    stack = MediaStack()
    result = {'passed': False}
    output = ROOT / 'output/performance-implementation-20260927/db-budget-1b.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        budget, services, native = check_budget(stack.path)
        mutations = ('overflow', 'replicas', 'worker_limit', 'postgres', 'native', 'service',
                     'api_env', 'media_env', 'api_command', 'media_command', 'entrypoint', 'outbox_command')
        for mutation in mutations:
            bad, bad_native = deepcopy(services), dict(native)
            if mutation == 'overflow': bad['outbox']['environment']['DB_MAX_OVERFLOW'] = '10'
            if mutation == 'replicas': bad['api']['scale'] = 2
            if mutation == 'worker_limit': bad['worker']['environment']['DB_WORKER_PROCESS_LIMIT'] = '6'
            if mutation == 'postgres': bad['postgres']['command'] = ['postgres', '-c', 'max_connections=60']
            if mutation == 'native': bad_native['DB_POOL_SIZE'] = '5'
            if mutation == 'service': bad['extra'] = {'environment': {'DATABASE_URL': 'test'}}
            if mutation == 'api_env': bad['api']['environment']['WEB_CONCURRENCY'] = '20'
            if mutation == 'media_env': bad['media-api']['environment']['UVICORN_WORKERS'] = '20'
            if mutation == 'api_command': bad['api']['command'] += ['--workers', '20']
            if mutation == 'media_command': bad['media-api']['command'] += ['--workers', '20']
            if mutation == 'entrypoint': bad['api']['entrypoint'] = ['sh', '-c', 'unexpected supervisor']
            if mutation == 'outbox_command': bad['outbox']['command'] = ['unexpected supervisor']
            try:
                validate(bad, bad_native)
                raise RuntimeError('unsafe composition accepted: ' + mutation)
            except AssertionError:
                pass
        result['budget'], result['negative_config_checks'] = budget, len(mutations)
        roles = [{'processes': count, 'size': size, 'label': label}
                 for name, (count, size, label) in EXPECTED.items() if name != 'migrate']
        (stack.path / 'db-budget.json').write_text(json.dumps(roles), encoding='utf-8')
        composition = json.loads(stack.compose_file.read_text())
        composition['services']['api']['volumes'].append(f'{stack.path}:/fixtures:ro')
        composition['services']['postgres']['command'] = services['postgres']['command']
        stack.compose_file.write_text(json.dumps(composition), encoding='utf-8')
        stack.run('up', '-d', 'postgres')
        probe = stack.run('run', '--rm', '--no-deps', '-T', 'api', 'python', '/checks/db_pool_probe.py', timeout=240)
        print(probe.stdout, flush=True)
        result['real_postgres'] = json.loads(probe.stdout.strip().splitlines()[-1])
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
