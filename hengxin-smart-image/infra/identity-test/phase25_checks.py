"""Final HTTP proof: derived resources follow current assignment and active sessions."""
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from phase19_fixtures import domestic_snapshot
from phase20_checks import storage


def run(h):
    before = domestic_snapshot(h)
    domestic = storage('domestic')
    objects_before = sorted((x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True))
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    with ExitStack() as stack:
        clients = []
        for code in ('p18-operator', 'p18-designer', 'p19-designer2', 'p18-admin',
                     'p18-design_manager', 'p18-operator_manager'):
            client = stack.enter_context(h.login(code))
            h.exchange(client, 'overseas')
            clients.append(client)
        operator, old, new, admin, design_manager, operator_manager = clients

        def get(client, suffix, **params):
            return h.expect(client.get(base + suffix, params=params), 200).json()

        tasks = get(admin, '/tasks', search='Phase23真实图片')
        assert tasks['total'] == 1
        task = tasks['items'][0]
        path = '/tasks/' + task['id']
        task = get(admin, path)
        old_id, new_id = (get(client, '/auth/me')['id'] for client in (old, new))
        assert task['status'] == 'archived' and task['designer']['id'] == old_id
        assert task['productName'] == 'Charger23' and task['brand'] == 'HX23'
        assert {sku['code'] for sku in task['skus']} == {'P23-A', 'P23-B'}
        pictures = get(old, path + '/pictures')['items']
        assert len(pictures) == 2 and sum(len(p['history']) for p in pictures) == 3
        materials = get(old, path + '/materials')
        assert materials and get(old, path + '/plans')['items']
        archive_filter = {'product': 'Charger23', 'brand': 'HX23', 'sku': 'P23-B'}
        archives = get(old, '/archives', **archive_filter)
        assert archives['total'] == 1
        download = '/archives/' + archives['items'][0]['id'] + '/download'
        direct = [path + suffix for suffix in ('', '/pictures', '/materials', '/plans', '/jobs', '/execution-events')]
        binary = [download]
        for material in materials:
            direct.append('/materials/' + material['id'])
            binary.append('/materials/' + material['id'] + '/content')
        for picture in pictures:
            for version in picture['history']:
                binary.append(f"/pictures/{picture['id']}/versions/{version['version']}/content")
        direct += binary
        def digest(url, data):
            # ZIP containers include download-time timestamps; compare frozen entries.
            if url == download:
                with ZipFile(BytesIO(data)) as zipped:
                    assert len(zipped.namelist()) == 2
                    return sorted((name, sha256(zipped.read(name)).hexdigest()) for name in zipped.namelist())
            return sha256(data).hexdigest()

        hashes = {url: digest(url, h.expect(old.get(base + url), 200).content) for url in binary}
        initial_jobs = get(admin, '/management/jobs', taskId=task['id'], pageSize=100)
        job_counts = {j['id']: j['executionCount'] for j in initial_jobs['items']}
        assert initial_jobs['total'] == len(job_counts) == 5
        usage = get(admin, '/management/usage', taskId=task['id'])
        assert usage['jobs'] == 5
        member_path = '/members/' + new_id
        member_before = get(admin, member_path)
        assert member_before['status'] == 'active'

        def assign(designer_id):
            current = get(admin, path)
            return h.expect(admin.patch(base + path + '/assignment',
                headers={'Idempotency-Key': str(uuid4())},
                json={'designerId': designer_id, 'version': current['version']}), 200).json()

        def member_status(status):
            current = get(admin, member_path)
            return h.expect(admin.patch(base + member_path, json={
                'roles': member_before['roles'], 'status': status, 'version': current['version']}), 200).json()

        def visible(client):
            for url in direct:
                response = h.expect(client.get(base + url), 200)
                if url in hashes:
                    assert digest(url, response.content) == hashes[url]
            assert get(client, '/tasks', search=task['id'])['total'] == 1
            assert get(client, '/archives', **archive_filter)['total'] == 1
            rows = get(client, '/management/jobs', taskId=task['id'], pageSize=100)
            assert rows['total'] == len(job_counts)
            assert {j['id']: j['executionCount'] for j in rows['items']} == job_counts
            assert get(client, '/management/usage', taskId=task['id']) == usage

        def revoked(client):
            for url in direct + ['/tasks', '/archives', '/management/jobs', '/management/usage']:
                assert client.get(base + url).status_code in (401, 403), url

        try:
            changed = assign(new_id)
            assert changed['status'] == 'archived' and changed['version'] == task['version'] + 1
            for url in direct:
                h.expect(old.get(base + url), 403)
            for suffix, params in (('/tasks', {'search': task['id']}), ('/archives', archive_filter),
                                   ('/management/jobs', {'taskId': task['id']})):
                hidden = get(old, suffix, **params)
                assert hidden['items'] == [] and hidden['total'] == 0
            assert get(old, '/management/usage', taskId=task['id'])['jobs'] == 0
            for client in (new, operator, admin, design_manager, operator_manager):
                visible(client)
            member_status('disabled')
            revoked(new)
            member_status('active')
            revoked(new)
            with h.login('p19-designer2') as fresh:
                h.exchange(fresh, 'overseas')
                visible(fresh)
        finally:
            if get(admin, member_path)['status'] != member_before['status']:
                member_status(member_before['status'])
            if get(admin, path)['designer']['id'] != old_id:
                assign(old_id)
        visible(old)
        assert domestic_snapshot(h) == before
        assert sorted((x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True)) == objects_before
        print('PASS Phase25 current-assignment HTTP: task/material/plan/picture history/jobs/events/archive '
              'and scoped management; five roles; disable/reactivate revokes old session; no job restart; '
              'original assignment restored; domestic DB/objects unchanged', flush=True)
