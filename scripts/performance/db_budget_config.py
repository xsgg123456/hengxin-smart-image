"""Validate the complete opt-in Compose + native CLI process budget."""
from media_config import resolved_services
from media_stack import ROOT


EXPECTED = {'api': (1, 5, 'hx-interactive'), 'media-api': (1, 4, 'hx-media'),
            'api-image-worker': (6, 4, 'hx-api-worker'), 'worker': (6, 3, 'hx-cli-worker'),
            'outbox': (1, 1, 'hx-cli-outbox'), 'api-image-outbox': (1, 1, 'hx-api-outbox'),
            'migrate': (1, 1, 'hx-migrate'), 'image-variants': (1, 1, 'hx-image-variants')}

COMMANDS = {
    'api': ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--workers', '1'],
    'media-api': ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--workers', '1', '--no-access-log'],
    'api-image-worker': ['celery', '-A', 'app.modules.api_image_edits.celery_app:celery_app',
                         'worker', '-Q', 'api_image_edits', '--concurrency=5', '--hostname=api-image@%h', '--loglevel=WARNING'],
    'worker': ['celery', '-A', 'app.worker.celery_app:celery_app', 'worker', '--loglevel=INFO', '--concurrency=1'],
    'outbox': ['python', '-m', 'app.worker.outbox'],
    'api-image-outbox': ['python', '-m', 'app.modules.api_image_edits.outbox'],
    'migrate': ['alembic', 'upgrade', 'head'],
    'image-variants': ['python', '-m', 'app.modules.files.variant_worker', '--backfill'],
}


def validate(services, native):
    database_services = {name for name, service in services.items()
                         if 'DATABASE_URL' in service.get('environment', {})}
    assert database_services == set(EXPECTED), 'database service missing from the process budget'
    total = 0
    for name, (processes, size, label) in EXPECTED.items():
        service = services[name]
        env = service['environment']
        assert service.get('command') == COMMANDS[name], f'{name}: process command changed; recalculate budget'
        assert service.get('entrypoint') in (None, []), f'{name}: unbudgeted entrypoint'
        if name in ('api', 'media-api'):
            assert service.get('entrypoint') == [], f'{name}: inherited image entrypoint'
            for key in ('WEB_CONCURRENCY', 'UVICORN_WORKERS'):
                assert str(env.get(key, '1')) == '1', f'{name}: unbudgeted {key}'
        assert int(env['DB_POOL_SIZE']) == size and int(env['DB_MAX_OVERFLOW']) == 0, name
        assert env['DB_APPLICATION_NAME'] == label, name
        assert service.get('scale', 1) == 1 and service.get('deploy', {}).get('replicas', 1) == 1, name
        if processes > 1:
            assert int(env['DB_WORKER_PROCESS_LIMIT']) == processes - 1, name
        total += processes * size
    assert services['worker']['profiles'] == ['container-worker'], 'native and container CLI must not both run'
    assert '--concurrency=5' in services['api-image-worker']['command']
    assert services['postgres']['command'] == ['postgres', '-c', 'max_connections=100', '-c', 'superuser_reserved_connections=3']
    for key in ('DB_POOL_SIZE', 'DB_MAX_OVERFLOW', 'DB_APPLICATION_NAME', 'DB_WORKER_PROCESS_LIMIT'):
        assert native[key] == services['worker']['environment'][key], key
    assert total + 10 + 3 <= 100, 'no maintenance/recovery headroom'
    return {'application': total - 1, 'migration': 1, 'maintenance': 10, 'postgres_reserved': 3,
            'total_budget': total + 13, 'database_limit': 100}


def check_budget(directory):
    services = resolved_services(directory, ('compose.resources.yaml',), all_profiles=True)
    infra = ROOT / 'hengxin-smart-image/infra'
    lines = (infra / 'worker-resources.env.example').read_text(encoding='utf-8').splitlines()
    native = dict(line.split('=', 1) for line in lines if line and not line.startswith('#'))
    dropin = (infra / 'hengxin-worker.resources.conf').read_text(encoding='utf-8')
    assert '\nEnvironmentFile=/etc/hengxin-smart-image/worker-resources.env' in dropin
    assert '\nExecStart' not in dropin, 'budget overlay must not change generation concurrency'
    return validate(services, native), services, native
