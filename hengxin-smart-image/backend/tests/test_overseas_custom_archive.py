"""同一个 SKU 和名称可以有多个独立创作任务，成品按任务持久化。"""
from uuid import UUID, uuid5

from test_overseas_materials import materials
from test_overseas_auth import overseas
from test_overseas_plans import post
from test_overseas_studio import finish, output, send
from test_overseas_tasks import HEADERS, ROOT


def test_custom_archives_for_same_sku_keep_task_identity(materials):
    client, factory, _, _, store = materials
    tasks = []
    for key in ('first', 'second'):
        created = client.post(ROOT + '/tasks/custom', json={'productNameSku': '灯 + GN-0008'},
                              headers={**HEADERS, 'Idempotency-Key': key})
        assert created.status_code == 201, created.text
        task = created.json()
        turn = send(client, task, key='send-' + key).json()['turns'][0]
        picture = output(store)
        finish(factory, turn, [picture])
        archived = post(client, task, '/studio/archive',
                        {'pictureIds': [picture['id']], 'sku': 'GN-0008'}, 'archive-' + key)
        assert archived.status_code == 200, archived.text
        tasks.append((task['id'], picture['id']))

    listing = client.get(ROOT + '/archives', params={'sku': 'GN-0008'}).json()
    assert listing['total'] == 2
    records = {row['taskId']: row for row in listing['items']}
    assert len({row['id'] for row in records.values()}) == 2
    for task_id, picture_id in tasks:
        record = records[task_id]
        assert record['designType'] == 'custom' and record['productName'] == '灯'
        assert record['pictureCount'] == 1 and record['skus'] == [{'code': 'GN-0008'}]
        detail = client.get(ROOT + '/archives/' + record['id']).json()
        assert detail['designType'] == 'custom' and detail['taskId'] == task_id
        assert len(detail['pictures']) == 1 and detail['pictures'][0]['sku'] == 'GN-0008'
        assert detail['pictures'][0]['id'] == str(uuid5(UUID(record['id']), 'studio:' + picture_id))
