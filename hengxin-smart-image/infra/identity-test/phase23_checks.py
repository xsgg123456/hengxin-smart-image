"""Real private image storage, offline process generation and versioned archive HTTP."""
from contextlib import ExitStack
from io import BytesIO
import os
from uuid import UUID, uuid4
from zipfile import ZipFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.overseas.execution import runner
from app.overseas.execution.models import Job
from app.storage.minio_store import get_store
from local_cli_fixture import configured_runner
from phase19_fixtures import domestic_snapshot
from phase20_checks import storage


def png(color):
    stream = BytesIO()
    Image.new('RGB', (32, 32), color).save(stream, format='PNG')
    return stream.getvalue()


def run(h):
    from app.overseas.generation.delivery import install
    install()
    previous = os.environ.copy()
    os.environ.update(h.environment('overseas'))
    get_settings.cache_clear()
    get_store.cache_clear()
    settings = get_settings()
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    before = domestic_snapshot(h)
    domestic = storage('domestic')
    objects_before = [(x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True)]
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    plan = {'skus': [{'code': code, 'pictures': [{'title': '产品图片', 'description': '清晰展示产品',
        'prompt': 'A clean product photograph.', 'width': 32, 'height': 32}]} for code in ('P23-A', 'P23-B')]}
    try:
        with ExitStack() as stack:
            clients = []
            for code in ('p18-operator', 'p18-designer', 'p19-designer2', 'p18-admin'):
                client = stack.enter_context(h.login(code))
                h.exchange(client, 'overseas')
                clients.append(client)
            operator, designer, stranger, admin = clients
            uid = h.expect(designer.get(base + '/auth/me'), 200).json()['id']
            material = h.expect(operator.post(base + '/materials', params={'kind': 'competitor'},
                files={'file': ('source.csv', b'item,value\nproduct,charger\n', 'text/csv')}), 201).json()
            task = h.expect(operator.post(base + '/tasks', headers={'Idempotency-Key': str(uuid4())},
                json=dict(name='Phase23真实图片', productName='Charger23', brand='HX23', platform='Amazon',
                    market='US', remarks='', skus=[{'code': c} for c in ('P23-A', 'P23-B')],
                    designerId=uid, materialIds=[material['id']])), 201).json()
            path = base + '/tasks/' + task['id']

            def detail():
                return h.expect(designer.get(path), 200).json()

            def pictures():
                return h.expect(designer.get(path + '/pictures'), 200).json()['items']

            def mutate(url, data, client=designer, status=200, key=None):
                return h.expect(client.post(url, json=data,
                    headers={'Idempotency-Key': key or str(uuid4())}), status)

            def jobs(kind):
                with factory() as session:
                    return session.scalars(select(Job).where(Job.task_id == UUID(task['id']),
                        Job.kind == kind).order_by(Job.created_at, Job.id)).all()

            with configured_runner(settings, plan):
                runner.run(factory, jobs('analysis')[0].id)
            current = h.expect(designer.get(path + '/plans'), 200).json()['items'][0]
            mutate(path + '/plans/' + current['id'] + '/confirm', {'version': detail()['version']})
            assert len(pictures()) == 2 and all(p['version'] == 0 for p in pictures())
            h.expect(stranger.get(path + '/pictures'), 403)
            output = {'images': [{'position': 0, 'path': 'product.png'}]}
            first, second = sorted(jobs('generation'), key=lambda j: j.payload['sku']['code'])
            with configured_runner(settings, output, output_name='outputs.json', files={'product.png': png('red')}):
                runner.run(factory, first.id)
            with configured_runner(settings, {'images': []}, output_name='outputs.json'):
                runner.run(factory, second.id)
            rows = sorted(pictures(), key=lambda p: p['sku'])
            a, b = rows
            assert a['version'] == 1 and b['version'] == 0 and b['status'] == 'failed'
            mutate(path + '/archive', {'version': detail()['version']}, status=409)
            key, retry = str(uuid4()), {'version': detail()['version'], 'sku': 'P23-B'}
            mutate(path + '/generation/retry', retry, key=key)
            mutate(path + '/generation/retry', retry, key=key)
            assert len(jobs('generation')) == 3
            pending = next(j for j in jobs('generation') if j.status == 'queued')
            with configured_runner(settings, output, output_name='outputs.json', files={'product.png': png('blue')}):
                runner.run(factory, pending.id)
            a, b = sorted(pictures(), key=lambda p: p['sku'])
            assert a['version'] == b['version'] == 1
            content = base + f"/pictures/{a['id']}/versions/1/content"
            response = h.expect(operator.get(content), 200)
            assert response.content == png('red') and 'no-store' in response.headers['cache-control']
            h.expect(stranger.get(content), 403)
            mutate(base + f"/pictures/{a['id']}/approve", {'version': 1, 'taskVersion': detail()['version']}, client=admin, status=403)
            mutate(base + f"/pictures/{a['id']}/approve", {'version': 1, 'taskVersion': detail()['version']})
            key = str(uuid4())
            revision = {'version': 1, 'taskVersion': detail()['version'], 'note': '改为绿色，保持布局',
                'marks': [{'id': 'mark-1', 'kind': 'rect', 'x': 2, 'y': 3, 'width': 10, 'height': 12,
                           'points': [], 'note': '调整此处颜色'}]}
            url = base + f"/pictures/{b['id']}/revisions"
            mutate(url, {**revision, 'marks': [{**revision['marks'][0], 'x': -1}]}, status=422)
            mutate(url, revision, key=key)
            mutate(url, revision, key=key)
            assert len(jobs('revision')) == 1
            with configured_runner(settings, output, output_name='outputs.json', files={'product.png': png('green')}):
                runner.run(factory, jobs('revision')[0].id)
            a, b = sorted(pictures(), key=lambda p: p['sku'])
            assert a['version'] == 1 and a['approved'] and b['version'] == 2 and not b['approved']
            assert len(b['history']) == 2
            assert h.expect(designer.get(base + f"/pictures/{b['id']}/versions/1/content"), 200).content == png('blue')
            mutate(url, {**revision, 'taskVersion': detail()['version']}, status=409)
            mutate(base + f"/pictures/{b['id']}/approve", {'version': 2, 'taskVersion': detail()['version']})
            key, archive = str(uuid4()), {'version': detail()['version']}
            mutate(path + '/archive', archive, key=key)
            mutate(path + '/archive', archive, key=key)
            assert detail()['status'] == 'archived'
            archives = h.expect(operator.get(base + '/archives', params={'product': 'Charger23', 'brand': 'HX23', 'sku': 'P23-B'}), 200).json()
            assert archives['total'] == 1
            archive_id = archives['items'][0]['id']
            download = base + '/archives/' + archive_id + '/download'
            zipped = h.expect(operator.get(download), 200)
            with ZipFile(BytesIO(zipped.content)) as bundle:
                image_files = [name for name in bundle.namelist() if name.endswith(('.png', '.jpg', '.webp'))]
                assert len(image_files) == 2
                assert sorted(bundle.read(name) for name in image_files) == sorted([png('red'), png('green')])
            h.expect(stranger.get(download), 403)
            mutate(url, {**revision, 'version': 2, 'taskVersion': detail()['version']}, status=409)
            assert domestic_snapshot(h) == before
            assert [(x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True)] == objects_before
            print('PASS images real HTTP/private MinIO/process: SKU partial retry, original bytes, revision history, approval isolation, immutable archive ZIP and permissions', flush=True)
    finally:
        os.environ.clear()
        os.environ.update(previous)
        get_settings.cache_clear()
        get_store.cache_clear()
