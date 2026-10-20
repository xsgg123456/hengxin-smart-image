"""Read-only durable-work handoff; no task edits, lease clearing or force stops."""
import json
import time


EVIDENCE = """SELECT json_build_object(
 'paused', (SELECT paused FROM api_image_channel WHERE id=1),
 'reserved', (SELECT count(*) FROM api_image_channel WHERE item_id IS NOT NULL
             OR token IS NOT NULL OR lease_until IS NOT NULL),
 'attempts', (SELECT count(*) FROM api_image_attempts WHERE completed_at IS NULL OR state IS NULL
             OR state NOT IN ('succeeded','failed','retryable','permanent','channel','uncertain')),
 'cli', (SELECT count(*) FROM api_edit_turns
         WHERE status IS NULL OR status NOT IN ('candidate','waiting_user','adopted','failed','cancelled')),
 'unknown_tasks', (SELECT count(*) FROM api_image_tasks
             WHERE state IS NULL OR state NOT IN ('queued','running','uncertain','succeeded','failed','partial_failed')),
 'items', (SELECT coalesce(json_agg(json_build_object(
     'id', id, 'state', state, 'token', lease_token IS NOT NULL,
     'lease', lease_until IS NOT NULL, 'expired', coalesce(lease_until <= now(),false),
     'receipt', coalesce(length(result_url)>0,false) OR coalesce(octet_length(result_bytes)>0,false)
 )), '[]'::json) FROM api_image_items))"""


def safe(data):
    assert isinstance(data, dict) and set(data) == {
        'paused', 'reserved', 'attempts', 'cli', 'unknown_tasks', 'items'}, 'Malformed handoff evidence'
    assert data['paused'] is True, 'Generation channel is not paused'
    assert all(type(data[key]) is int and data[key] >= 0
               for key in ('reserved', 'attempts', 'cli', 'unknown_tasks')), 'Malformed work counters'
    assert isinstance(data['items'], list), 'Malformed item evidence'
    seen = set()
    for item in data['items']:
        assert isinstance(item, dict) and set(item) == {
            'id', 'state', 'token', 'lease', 'expired', 'receipt'}, 'Malformed item evidence'
        assert isinstance(item['id'], str) and item['id'] and item['id'] not in seen, 'Invalid item identity'
        seen.add(item['id'])
        assert isinstance(item['state'], str) and all(type(item[key]) is bool
            for key in ('token', 'lease', 'expired', 'receipt')), 'Malformed item fields'
    if any(data[key] != 0 for key in ('reserved', 'attempts', 'cli', 'unknown_tasks')):
        return False
    for item in data['items']:
        state = item['state']
        if state == 'uncertain':
            # Only the known expired-owner representation is admitted.
            if not (item['token'] and item['lease'] and item['expired']):
                return False
        elif state in ('queued', 'retry_wait', 'collecting', 'succeeded', 'failed'):
            if item['token'] or item['lease']:
                return False
            if state == 'collecting' and not item['receipt']:
                return False
        else:
            return False
    return True


def database(runtime, timeout=30):
    db = runtime.DATABASE
    return json.loads(runtime.m.run('docker', 'exec', db[0], 'psql', '-v', 'ON_ERROR_STOP=1',
        '-U', db[1], '-d', db[2], '-Atc', EVIDENCE, capture=True, timeout=timeout))


def broker(runtime, timeout=30):
    return json.loads(runtime.m.run('docker', 'exec',
        runtime.m.container('domestic', 'api-image-worker'), 'python', '-c',
        runtime.probe.PROBE.format(module='app.modules.api_image_edits.celery_app', queues=['api_image_edits']),
        capture=True, timeout=timeout))


def wait_idle(work, runtime, timeout=1200):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'API work busy/unknown; no force stop'
        worker = broker(runtime, remaining)
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'Handoff deadline exceeded'
        data = database(runtime, remaining)
        assert time.monotonic() <= deadline, 'Handoff deadline exceeded'
        ready = safe(data) and runtime.probe.idle({'api': worker})
        stable = stable + 1 if ready else 0
        runtime.m.private(work / 'api-handoff.json', dict(worker=worker, database=data, stable=stable))
        if stable == 2:
            return
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def drain(work, runtime):
    assert runtime.r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 't'
    runtime.graceful_stop('api-image-outbox')
    wait_idle(work, runtime)
    runtime.graceful_stop('api-image-worker')
    data = database(runtime)
    assert safe(data), 'Durable work changed after worker exit'
    runtime.m.private(work / 'api-handoff-stopped.json', data)
    runtime.m.private(work / 'EXECUTORS_STOPPED',
        'Broker idle twice; only durable unleased/expired-owner work retained, no row edits')


PROTECTED = {
    'api_image_items': "state IN ('succeeded','failed')",
    'api_image_attempts': "item_id IN (SELECT id FROM api_image_items WHERE state IN ('succeeded','failed'))",
    'api_image_versions': 'true',
    'api_image_files': 'id IN (SELECT file_id FROM api_image_versions)',
}


def protected(runtime):
    # Freeze row hashes, allowing newly completed rows without losing old evidence.
    return {table: json.loads(runtime.b.query(runtime.DATABASE,
        "SELECT coalesce(json_object_agg(id, fingerprint),'{}'::json) FROM "
        f'(SELECT id,md5(to_jsonb(t)::text) AS fingerprint FROM "{table}" t WHERE {where}) rows'))
        for table, where in PROTECTED.items()}


def verify_protected(runtime, before):
    after = protected(runtime)
    for table, rows in before.items():
        assert all(after[table].get(key) == value for key, value in rows.items()), \
            'Previously completed API evidence changed: ' + table
