"""HTTP helpers shared by independent session regression cases."""
from test_overseas_tasks import ROOT, HEADERS
from test_overseas_plans import post


def base(task):
    return ROOT + '/tasks/' + task['id'] + '/studio'


def channel(client, task, key='new', name='设计会话'):
    response = post(client, task, '/studio/conversations', {'name': name}, key)
    assert response.status_code == 200, response.text
    return response.json()['conversationId']


def selected(client, task, identity):
    return client.get(base(task), params={'conversationId': identity}).json()


def upload_private(client, task, identity, content=b'private'):
    response = client.post(base(task) + '/files', params={'conversationId': identity},
        files={'file': ('private.txt', content)}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def mutate(client, task, identity, method, body, key='mutation'):
    return client.request(method, base(task) + '/conversations/' + identity,
        json=body, headers={**HEADERS, 'Idempotency-Key': key})


