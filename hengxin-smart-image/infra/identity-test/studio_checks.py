"""Real PostgreSQL/HTTP studio admission, intentionally never starts a worker."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4


def check_queued_studio(h, designer, stranger, base, task, material):
    path = base + '/tasks/' + task['id'] + '/studio'
    state = h.expect(designer.get(path), 200).json()
    assert not state['completed'] and state['turns'] == []
    h.expect(stranger.get(path), 403)
    original = 'task:' + material['id']
    assert original in {item['id'] for item in state['materials']}
    uploaded = h.expect(designer.post(path + '/files',
        files={'file': ('notes.txt', '工作台原始附件'.encode(), 'text/plain')}), 200).json()
    assert h.expect(designer.get(base.split('/api/')[0] + uploaded['url']), 200).content == '工作台原始附件'.encode()
    h.expect(stranger.get(base.split('/api/')[0] + uploaded['url']), 403)
    body = dict(text='只创建排队凭据；隔离测试不启动执行器',
                attachmentIds=[original, uploaded['id']], referencePictureIds=[])
    key = str(uuid4())
    def submit(_):
        return h.expect(designer.post(path + '/turns', json=body,
            headers={'Idempotency-Key': key}), 200).json()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, (1, 2)))
    assert results[0] == results[1] and len(results[0]['turns']) == 1
    turn = results[0]['turns'][0]
    assert turn['status'] == 'queued'
    h.expect(designer.post(path + '/turns', json=body,
        headers={'Idempotency-Key': str(uuid4())}), 409)
    h.expect(designer.post(path + '/complete', json={},
        headers={'Idempotency-Key': str(uuid4())}), 409)
    cancelled = h.expect(designer.post(path + '/turns/' + turn['id'] + '/cancel',
        json={'version': turn['jobVersion']}), 200).json()
    assert cancelled['turns'][0]['status'] == 'cancelled'
    events = h.expect(designer.get(path + '/events'), 200).json()
    assert len(events['items']) == 2
    assert h.expect(designer.get(path + '/events', params={'after': events['cursor']}), 200).json()['items'] == []
    print('PASS studio real PG concurrent idempotency, originals, foreign permission, queued cancel and cursor; no CLI', flush=True)
