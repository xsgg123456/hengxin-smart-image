from io import BytesIO
from uuid import UUID

from PIL import Image
import pytest

from app.overseas.auth.models import Member
from app.overseas.feedback.models import Feedback
from test_overseas_auth import COOKIE_PATH, HEADERS, login, overseas, seed
from test_overseas_members import add_member

URL = COOKIE_PATH + '/feedback'
ADMIN = COOKIE_PATH + '/management/feedback'


def switch(client, factory, assertion, identifier):
    with factory() as session:
        member = session.get(Member, identifier)
        assertion['member'] = {k: getattr(member, k) for k in (
            'corp_id', 'provider_user_id', 'union_id', 'name', 'department')}
    result = login(client)
    assert result.status_code == 200, result.text
    return result.json()


def send(client, **changes):
    fields = {'question': (None, '  图片未显示 '), 'source': (None, 'AI 工作台'),
              'task_name': (None, '桌灯'), 'sku': (None, 'SKU-10'), **changes}
    return client.post(URL, files=fields, headers=HEADERS)


def test_feedback_permissions_reply_visibility_and_screenshot(overseas):
    client, factory, assertion = overseas
    owner = seed(factory)
    manager = add_member(factory, 'active', ('design_manager',), '设计经理')
    admin = add_member(factory, 'active', ('super_admin',), '主管')
    outsider = add_member(factory, 'active', ('designer',), '其他人')
    png = BytesIO()
    Image.new('RGB', (12, 17), 'green').save(png, format='PNG')
    assert client.get(URL + '/mine').status_code == 401
    assert send(client).status_code == 401
    assert login(client).is_success
    item = send(client, screenshot=('screen.png', png.getvalue(), 'image/png'))
    assert item.status_code == 201, item.text
    item = item.json()
    assert item['submitter_id'] == str(owner) and item['submitter_name'] == '海外成员'
    assert item['question'] == '图片未显示' and item['task_name'] == '桌灯' and item['sku'] == 'SKU-10'
    assert item['source'] == 'AI 工作台' and item['status'] == 'pending'
    assert 'internal_note' not in item and item['version'] == 1
    detail = ADMIN + '/' + item['id']
    pic = item['screenshot_url']
    assert client.get(pic).content == png.getvalue()
    assert client.get(ADMIN).status_code == 403
    assert client.get(detail).status_code == 403
    assert client.patch(detail, json={'version': 1, 'internal_note': 'x'}, headers=HEADERS).status_code == 403
    switch(client, factory, assertion, outsider)
    assert client.get(URL + '/mine').json() == {'items': [], 'total': 0}
    assert client.get(pic).status_code == 404
    second = send(client).json()
    assert second['screenshot_url'] is None
    assert client.get(URL + '/' + second['id'] + '/screenshot').status_code == 404
    switch(client, factory, assertion, admin)
    assert client.get(ADMIN).status_code == 403
    member_url = COOKIE_PATH + '/members/' + str(manager)
    patch = {'version': 1, 'roles': ['design_manager'], 'status': 'active', 'feedbackManage': True}
    assert client.patch(member_url, json=patch, headers=HEADERS).json()['feedbackManage']
    audit = client.get(member_url + '/audit').json()['items'][0]
    assert audit['after']['feedbackManage'] and not audit['before']['feedbackManage']
    assert 'feedback.manage' in switch(client, factory, assertion, manager)['capabilities']
    assert client.get(URL + '/mine').json()['total'] == 0
    assert client.get(COOKIE_PATH + '/members').status_code == 403
    assert client.get(detail).json()['internal_note'] == ''
    screenshot = client.get(pic)
    assert screenshot.headers['content-type'] == 'image/png' and screenshot.content == png.getvalue()
    assert 'no-store' in screenshot.headers['cache-control']
    assert client.get(ADMIN, params={'offset': 1, 'limit': 1}).json()['items'][0]['id'] == item['id']
    assert client.get(ADMIN, params={'status': 'invalid'}).status_code == 422
    assert client.patch(detail, json={'version': 1, 'status': 'resolved'}, headers=HEADERS).status_code == 422
    assert client.patch(detail, json={'version': 1, 'status': 'processing'}).status_code == 403
    response = client.patch(detail, json={'version': 1, 'status': 'processing', 'internal_note': '仅组内'},
                            headers=HEADERS)
    assert response.status_code == 200 and response.json()['internal_note'] == '仅组内'
    assert response.json()['version'] == 2
    stale = client.patch(detail, json={'version': 1, 'public_reply': '过期'}, headers=HEADERS)
    assert stale.status_code == 409
    response = client.patch(detail, json={'version': 2, 'status': 'resolved', 'public_reply': ' 已修复 '},
                            headers=HEADERS)
    assert response.json()['public_reply'] == '已修复' and response.json()['internal_note'] == '仅组内'
    listed = client.get(ADMIN, params={'status': 'resolved'}).json()
    assert listed['total'] == 1 and listed['counts'] == {'pending': 1, 'resolved': 1, 'processing': 0}
    assert listed['items'][0]['id'] == item['id']
    assert client.patch(detail, json={'version': 3, 'public_reply': '  '}, headers=HEADERS).status_code == 422
    switch(client, factory, assertion, owner)
    history = client.get(URL + '/mine')
    assert 'no-store' in history.headers['cache-control']
    own = history.json()
    assert own['total'] == len(own['items']) == 1
    record = own['items'][0]
    assert record['public_reply'] == '已修复' and record['status'] == 'resolved'
    assert 'internal_note' not in record and '仅组内' not in str(own)
    with factory() as session:
        saved = session.get(Feedback, UUID(item['id']))
        assert saved.internal_note == '仅组内' and saved.version == 3
    switch(client, factory, assertion, admin)
    assert client.patch(member_url, headers=HEADERS, json={**patch, 'version': 2, 'roles': ['designer']}).status_code == 422
    assert client.patch(member_url, headers=HEADERS, json={
        'version': 2, 'roles': ['designer'], 'status': 'active'}).json()['feedbackManage'] is False
    assert 'feedback.manage' not in switch(client, factory, assertion, manager)['capabilities']
    assert client.get(detail).status_code == 403 and client.get(pic).status_code == 404


@pytest.mark.parametrize('changes,expected', [
    ({'question': (None, '   ')}, 422), ({'source': (None, ' ')}, 422),
    ({'question': (None, 'x' * 4001)}, 422), ({'submitter_id': (None, 'forged')}, 422),
    ({'screenshot': ('bad.png', b'text only', 'image/png')}, 422),
    ({'screenshot': ('huge.png', b'x' * (5 * 1024 * 1024 + 1), 'image/png')}, 413),
])
def test_feedback_rejects_invalid_submissions(overseas, changes, expected):
    client, factory, _ = overseas
    seed(factory)
    login(client)
    assert send(client, **changes).status_code == expected
    assert client.get(URL + '/mine').json()['total'] == 0


def test_feedback_rejects_duplicate_files_and_mislabeled_image(overseas):
    client, factory, _ = overseas
    seed(factory)
    login(client)
    png = BytesIO()
    Image.new('RGB', (2, 2)).save(png, format='PNG')
    assert send(client, screenshot=('file.jpg', png.getvalue(), 'image/jpeg')).status_code == 422
    files = [('question', (None, 'test')), ('source', (None, 'test'))] + [
        ('screenshot', ('file.png', png.getvalue(), 'image/png'))] * 2
    assert client.post(URL, files=files, headers=HEADERS).status_code == 422
    assert client.post(URL, files=files[:2]).status_code == 403
    assert client.get(URL + '/mine').json()['items'] == []


def test_feedback_preserves_all_skus_from_a_maximum_size_task(overseas):
    client, factory, _ = overseas
    seed(factory)
    login(client)
    skus = '、'.join(f'{n:02}' + '灯' * 78 for n in range(100))
    name = '灯' * 80
    assert len(skus) == 8099
    sent = send(client, task_name=(None, name), sku=(None, skus))
    assert sent.status_code == 201
    saved = client.get(URL + '/mine').json()['items'][0]
    assert saved['sku'] == skus and saved['task_name'] == name
    assert send(client, sku=(None, skus + '灯')).status_code == 422
