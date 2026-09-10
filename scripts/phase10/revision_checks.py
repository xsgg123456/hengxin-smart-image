"""Phase 10 fixture API/PG/MinIO verification in the Phase 8 disposable stack."""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
from uuid import UUID, uuid4
import time


def verify_revisions(api, wait, compose, sql, env):
    source = api('/tasks?search=phase8-duplicate-limit2')[1]['items'][0]
    body = dict(mode='text', name='phase10-api', sources=source['sources'] * 2,
                note='首次双图', skillVersionId=source['skillVersionId'])

    def post(path, payload, key=None):
        return api(path, payload, 'POST', headers={'Content-Type': 'application/json',
                                                  'Idempotency-Key': key or str(uuid4())})

    code, initial = post('/tasks', body)
    assert code == 202, (code, initial)
    task_id = str(UUID(initial['taskId']))
    path = '/tasks/' + task_id

    def detail():
        code, data = api(path)
        assert code == 200, data
        return data

    def done():
        data = detail()
        assert data['task']['state'] not in ('失败', '部分失败'), data
        return data['task']['state'] == '待查看'

    def fingerprints():
        # Version, file ID, private object key and checksum are independent assertions.
        rows = sql("SELECT s.slot,v.id,f.id,f.object_key,f.checksum FROM result_slots s "
                   "JOIN image_versions v ON v.id=s.current_version_id "
                   "JOIN files f ON f.id=v.file_id "
                   f"WHERE s.task_id='{task_id}' ORDER BY s.slot")
        return rows.splitlines()

    wait(done, 'Phase10 initial two-slot fixture completed')
    before, original = detail(), fingerprints()
    note = '仅修改第二张，第一张保持不变'
    revision = dict(taskId=task_id, target=1, note=note)
    key = str(uuid4())
    compose('stop', 'worker')
    try:
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(lambda _: post(path + '/rounds', revision, key), range(6)))
        assert time.monotonic() - started < 8, 'Revision waited for executor'
        assert all(code == 202 and receipt == responses[0][1] for code, receipt in responses)
        accepted = responses[0][1]
        assert detail()['task']['state'] == '排队中'
        assert detail()['slots'] == before['slots']
        assert not detail()['executionControl']['canRevise']
        assert post(path + '/rounds', dict(revision, note='different'), key)[0] == 409
        assert post(path + '/rounds', revision)[0] == 409
        assert sql(f"SELECT count(*) FROM execution_rounds WHERE task_id='{task_id}'") == '2'
    finally:
        compose('start', 'worker')
    wait(lambda: detail()['task']['state'] == '执行中', 'Phase10 revision really running')
    assert post(path + '/rounds', revision)[0] == 409
    wait(done, 'Phase10 single-slot revision completed')
    after = detail()
    changed = fingerprints()
    assert changed[0] == original[0] and changed[1] != original[1]
    assert after['slots'][0] == before['slots'][0]
    assert len(after['slots'][1]['versions']) == 2
    assert after['rounds'][-1]['note'] == note and after['rounds'][-1]['target'] == 1
    assert after['rounds'][-1]['operatorId'] == env['DEV_USER_ID']
    assert post(path + '/rounds', revision, key) == (202, accepted)
    for slot in after['slots']:
        for version in slot['versions']:
            with urlopen('http://127.0.0.1:' + env['API_PORT'] + version['url'], timeout=10) as response:
                assert response.status == 200 and response.read().startswith(b'\x89PNG')

    whole = dict(taskId=task_id, target=None, note='整套统一调整；保留历次反馈')
    # Distinct keys compete against the same task; PostgreSQL must select one winner.
    compose('stop', 'worker')
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            raced = list(pool.map(lambda _: post(path + '/rounds', whole), range(6)))
        assert sorted(code for code, _ in raced) == [202, 409, 409, 409, 409, 409], raced
    finally:
        compose('start', 'worker')
    wait(done, 'Phase10 whole-set revision completed')
    final = detail()
    assert [len(s['versions']) for s in final['slots']] == [2, 3]
    assert [r['note'] for r in final['rounds']] == ['首次双图', note, whole['note']]
    assert final['rounds'][-1]['target'] is None
    assert final['task']['executionSource'] == 'fixture' and final['task']['sessionId'] is None
    assert sql(f"SELECT count(*) FROM task_requests WHERE task_id='{task_id}'") == '3'
    assert sql("SELECT count(*) FROM job_outbox o JOIN execution_rounds r ON r.job_id=o.id "
               f"WHERE r.task_id='{task_id}'") == '3'
    print('PHASE10 API PASS: asynchronous revision, queued/running barriers, stable replay, '
          'competing new requests, unchanged other slot IDs/object/hash, historical bytes and feedback', flush=True)
