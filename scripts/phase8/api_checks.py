"""Phase 8 assertions; called only by the disposable Compose harness."""
from concurrent.futures import ThreadPoolExecutor
import time
import struct
import zlib
from urllib.request import urlopen
from uuid import UUID, uuid4


def readable_png(data):
    assert data.startswith(b'\x89PNG\r\n\x1a\n'), 'Result is not a PNG'
    offset, compressed = 8, b''
    while offset < len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        checksum = struct.unpack('>I', data[offset + 8 + size:offset + 12 + size])[0]
        assert zlib.crc32(kind + body) == checksum, 'Invalid PNG checksum'
        if kind == b'IHDR':
            assert struct.unpack('>II', body[:8]) == (2, 2)
        if kind == b'IDAT':
            compressed += body
        offset += size + 12
    assert len(zlib.decompress(compressed)) >= 12, 'Result PNG has no readable pixel data'


def verify(api, upload, package, wait, compose, sql, env, pixel):
    defaults, inputs = {}, {}
    code, source = upload('/files', pixel, 'phase8-input.png', 'image/png')
    assert code == 200, (code, source)
    for mode in ('wallpaper', 'product', 'text'):
        code, skill = upload('/management/skills', package('8.0.0', mode=mode),
                             mode + '.zip', 'application/zip', {'mode': mode, 'version': '8.0.0'})
        assert code == 201, (code, skill)
        sid = str(UUID(skill['id']))
        assert api('/management/skills/' + sid + '/install', {})[0] == 200
        wait(lambda: next(s for s in api('/management/skills')[1] if s['id'] == sid)['status'] == 'available',
             'real Worker Skill installation ' + mode)
        defaults[mode] = sid
        body = dict(mode=mode, name='phase8-' + mode, sources=[source], note='受控集成输入', skillVersionId=sid)
        if mode != 'text':
            code, template = api('/templates', dict(name='phase8-' + mode, mode=mode,
                images=[source, source], skillVersionId=sid, active=True, notes='isolated fixture'), 'POST')
            assert code == 200, (code, template)
            body.update(templateId=template['id'], templateVersion=template['version'])
        inputs[mode] = body
    assert api('/management/skills/defaults', defaults, 'PUT')[0] == 200

    def create(body, key=None):
        code, receipt = api('/tasks', body, 'POST', headers={'Content-Type': 'application/json',
            'Idempotency-Key': key or str(uuid4())})
        assert code == 202, (code, receipt)
        return receipt

    def detail(receipt):
        code, data = api('/tasks/' + receipt['taskId'])
        assert code == 200, (code, data)
        return data

    def done(receipt):
        data = detail(receipt)
        assert data['task']['state'] != '失败', data
        return data['task']['state'] == '待查看'

    key = str(uuid4())
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as executor:
        receipts = list(executor.map(lambda _: create(inputs['wallpaper'], key), range(6)))
    assert time.monotonic() - started < 8, 'HTTP waited for fixture completion'
    first = receipts[0]
    assert all(r == first for r in receipts)
    assert sql('SELECT count(*) FROM task_records') == '1'
    assert api('/tasks', dict(inputs['wallpaper'], name='changed'), 'POST', headers={
        'Content-Type': 'application/json', 'Idempotency-Key': key})[0] == 409
    wait(lambda: detail(first)['task']['state'] == '执行中', 'first asynchronous task running')
    second = create(inputs['product'])
    assert detail(second)['task']['state'] == '排队中'
    assert not detail(first)['executionControl']['canRevise']
    job = str(UUID(sql(f"SELECT job_id FROM execution_rounds WHERE id='{first['roundId']}'")))
    publish = ("from app.worker.celery_app import celery_app; "
               f"[celery_app.send_task('hengxin.job', args=['{job}']) for _ in range(6)]")
    compose('exec', '-T', 'api', 'python', '-c', publish)
    wait(lambda: done(first), 'duplicate messages first task completes')
    wait(lambda: done(second), 'global limit releases queued task')
    compose('exec', '-T', 'api', 'python', '-c', publish)
    assert sql(f"SELECT execution_count FROM job_records WHERE id='{job}'") == '1'
    assert sql(f"SELECT count(*) FROM image_versions WHERE round_id='{first['roundId']}'") == '2'
    print('PASS concurrent same-key 202, different-content 409, limit=1, repeated messages single start/results', flush=True)

    compose('stop', 'redis')
    third = create(inputs['text'])
    assert detail(third)['task']['state'] == '排队中'
    compose('start', 'redis')
    wait(lambda: done(third), 'Redis outage accepted task recovered')
    for receipt, count in ((first, 2), (second, 2), (third, 1)):
        data = detail(receipt)
        assert data['task']['executionSource'] == 'fixture' and data['task']['sessionId'] is None
        assert len(data['slots']) == count and len(data['task']['images']) == count
        assert data['task']['skillVersionId'] == defaults[data['task']['mode']]
        assert data['rounds'][0]['note'] == '受控集成输入'
        for picture in data['task']['images']:
            assert picture['fileId'] != source['fileId'], 'Result must have an independent stored file'
            url = picture['url']
            if url.startswith('/'):
                url = 'http://127.0.0.1:' + env['API_PORT'] + url
            with urlopen(url, timeout=10) as response:
                result_bytes = response.read()
                readable_png(result_bytes)
                assert result_bytes == pixel, 'Fixture must preserve the frozen input bytes'
        assert not data['executionControl']['canRevise'] and not data['executionControl']['canRetry']
    print('PASS three entry API snapshots, real MinIO bytes, fixture provenance and no fake CLI session', flush=True)

    env['GENERATION_CONCURRENCY'] = '2'
    compose('up', '-d', '--no-build', '--scale', 'worker=2', 'api', 'worker', 'outbox')
    wait(lambda: api('/auth/me')[0] == 200, 'independent duplicate claim check with global limit 2')
    parallel = create(dict(inputs['text'], name='phase8-duplicate-limit2'))
    peer = create(dict(inputs['text'], name='phase8-peer-limit2'))
    parallel_job = str(UUID(sql(f"SELECT job_id FROM execution_rounds WHERE id='{parallel['roundId']}'")))
    republish = ("from app.worker.celery_app import celery_app; "
                 f"[celery_app.send_task('hengxin.job', args=['{parallel_job}']) for _ in range(8)]")
    compose('exec', '-T', 'api', 'python', '-c', republish)
    wait(lambda: detail(parallel)['task']['state'] == '执行中' and detail(peer)['task']['state'] == '执行中',
         'two distinct tasks running concurrently across two workers')
    wait(lambda: done(parallel) and done(peer), 'limit2 duplicated job and peer finish')
    compose('exec', '-T', 'api', 'python', '-c', republish)
    assert sql(f"SELECT execution_count FROM job_records WHERE id='{parallel_job}'") == '1'
    assert sql(f"SELECT count(*) FROM image_versions WHERE round_id='{parallel['roundId']}'") == '1'
    print('PASS duplicate execution claim under global limit2, distinct peer concurrently running', flush=True)
    env['GENERATION_CONCURRENCY'] = '1'
    compose('up', '-d', '--no-build', '--scale', 'worker=2', 'api', 'worker', 'outbox')
    wait(lambda: api('/auth/me')[0] == 200, 'restore limit1 cancellation scenario')

    running = create(dict(inputs['text'], name='phase8-cancel-running'))
    wait(lambda: detail(running)['task']['state'] == '执行中', 'cancellable task running')
    queued = create(dict(inputs['text'], name='phase8-cancel-queued'))
    assert detail(queued)['task']['state'] == '排队中'
    for receipt in (queued, running):
        code, deletion = api('/tasks/' + receipt['taskId'], method='DELETE')
        assert code == 200 and deletion['operatorId'] == env['DEV_USER_ID'], (code, deletion)
        assert api('/tasks/' + receipt['taskId'])[0] == 404
    wait(lambda: sql(f"SELECT count(*) FROM execution_rounds WHERE id IN ('{queued['roundId']}','{running['roundId']}') AND finished_at IS NULL") == '0',
         'queued and running cancellation acknowledged')
    assert sql(f"SELECT count(*) FROM image_versions WHERE round_id IN ('{queued['roundId']}','{running['roundId']}')") == '0'
    compose('restart', 'worker')
    assert api('/tasks/' + queued['taskId'])[0] == 404 and api('/tasks/' + running['taskId'])[0] == 404
    print('PASS durable queued/running deletion, no late versions, restart no resurrection', flush=True)

    original_user = env['DEV_USER_ID']
    env['DEV_USER_ID'], env['DEV_USER_ROLE'] = str(uuid4()), 'designer'
    compose('up', '-d', '--no-build', 'api')
    wait(lambda: api('/auth/me')[0] == 200, 'second trusted development identity in isolated database')
    assert api('/auth/me')[1]['id'] == env['DEV_USER_ID']
    assert detail(first)['task']['ownerId'] == original_user
    assert api('/tasks?search=phase8-wallpaper')[1]['total'] >= 1
    code, receipt = api('/tasks/' + first['taskId'], method='DELETE')
    assert code == 200 and receipt['operatorId'] == env['DEV_USER_ID']
    assert sql(f"SELECT operator_id FROM deletion_records WHERE resource_id='{first['taskId']}'") == env['DEV_USER_ID']
    assert api('/tasks/' + first['taskId'])[0] == 404
    print('PASS cross-owner read/delete with second trusted identity and actual operator audit', flush=True)

    def verify_uncertain():
        # Last scenario intentionally retains an uncertain execution right until volume cleanup.
        wait(lambda: sql("SELECT count(*) FROM execution_rounds WHERE status IN ('queued','running','collecting','cancelling','uncertain')") == '0',
             'all previous browser and API tasks terminal before worker fault scenario')
        env['FIXTURE_DELAY_SECONDS'] = '60'
        compose('up', '-d', '--no-build', '--scale', 'worker=2', 'api', 'worker', 'outbox')
        wait(lambda: api('/auth/me')[0] == 200, 'long fixture configured for hard worker loss')
        lost = create(dict(inputs['text'], name='phase8-hard-kill-uncertain'))
        wait(lambda: detail(lost)['task']['state'] == '执行中', 'worker entered execution before hard kill')
        lost_job = str(UUID(sql(f"SELECT job_id FROM execution_rounds WHERE id='{lost['roundId']}'")))
        compose('kill', '-s', 'SIGKILL', 'worker')
        sql(f"UPDATE job_records SET lease_until=now()-interval '1 second' WHERE id='{lost_job}'")
        wait(lambda: sql(f"SELECT status FROM job_records WHERE id='{lost_job}'") == 'uncertain',
             'hard killed worker lease transitions to uncertain')
        compose('start', 'worker')
        replay = ("from app.worker.celery_app import celery_app; "
                  f"[celery_app.send_task('hengxin.job', args=['{lost_job}']) for _ in range(6)]")
        compose('exec', '-T', 'api', 'python', '-c', replay)
        blocked = create(dict(inputs['text'], name='phase8-uncertain-holds-global-slot'))
        time.sleep(3)
        data = detail(lost)
        assert '待核实' in data['executionControl']['blockedReason']
        assert not data['executionControl']['canRevise'] and not data['executionControl']['canRetry']
        assert detail(blocked)['task']['state'] == '排队中'
        assert sql(f"SELECT execution_count FROM job_records WHERE id='{lost_job}'") == '1'
        assert sql(f"SELECT count(*) FROM image_versions WHERE round_id='{lost['roundId']}'") == '0'
        assert sql(f"SELECT status FROM job_records WHERE id='{lost_job}'") == 'uncertain'
        print('PASS hard SIGKILL plus expired lease remains uncertain, duplicate messages do not restart, slot retained', flush=True)

    return verify_uncertain
