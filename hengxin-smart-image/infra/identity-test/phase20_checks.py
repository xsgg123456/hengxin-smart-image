"""Real document bytes, private object storage, HTTP authorization and persistence."""
from contextlib import ExitStack
from io import BytesIO
import time
from uuid import uuid4
from zipfile import ZipFile

from minio import Minio
from minio.error import S3Error
from sqlalchemy import text

from phase19_fixtures import domestic_snapshot


def storage(kind):
    return Minio(kind + '-minio:9000', access_key=kind + '-test',
                 secret_key=kind + '-phase20-test-only', secure=False)


def run(h):
    for kind in ('domestic', 'overseas'):
        client = storage(kind)
        for attempt in range(30):
            try:
                if not client.bucket_exists(kind + '-test'):
                    client.make_bucket(kind + '-test')
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(.2)
    domestic = storage('domestic')
    domestic.put_object('domestic-test', 'sentinel', BytesIO(b'domestic-unchanged'), 18)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    with ExitStack() as stack:
        domestic_session = stack.enter_context(h.login('both'))
        h.exchange(domestic_session, 'domestic')
        from PIL import Image
        image = BytesIO()
        Image.new('RGB', (4, 4), 'white').save(image, format='PNG')
        domestic_file = h.expect(domestic_session.post(h.BUSINESS['domestic'][0] + '/api/v1/files',
            files={'file': ('domestic.png', image.getvalue(), 'image/png')}), 200).json()['fileId']
        domestic_before = domestic_snapshot(h)
        before_objects = [(x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True)]
        clients = {}
        for code in ('p18-operator', 'p19-operator2', 'p18-designer', 'p19-designer2', 'p18-admin'):
            clients[code] = stack.enter_context(h.login(code))
            h.exchange(clients[code], 'overseas')
        operator, outsider, old, new, admin = clients.values()
        designer = h.expect(old.get(base + '/auth/me'), 200).json()['id']
        next_designer = h.expect(new.get(base + '/auth/me'), 200).json()['id']

        def upload(data=b'item,value\nproduct,charger\n', name='competitor.csv', kind='competitor', status=200):
            result = operator.post(base + '/materials', params={'kind': kind},
                                   files={'file': (name, data, 'application/octet-stream')}, timeout=40)
            assert result.status_code in ({200, 201} if status == 200 else {status}), result.text
            return result.json()

        material = upload()
        assert material['status'] == 'ready' and 'text' not in material
        assert 'version' not in material and material['taskId'] is None
        url = base + '/materials/' + material['id']
        h.expect(outsider.get(url), 403)
        h.expect(old.get(url + '/content'), 403)
        content = h.expect(operator.get(url + '/content'), 200)
        assert content.content == b'item,value\nproduct,charger\n'
        assert 'no-store' in content.headers['cache-control']
        assert content.headers['x-content-type-options'] == 'nosniff'
        assert 'attachment' in content.headers['content-disposition']
        assert 'bucket' not in material and 'objectKey' not in material
        h.expect(operator.head(url + '/content'), 200)
        h.expect(outsider.head(url + '/content'), 403)
        upload(b'', status=422)
        for name in ('wrong.exe', 'old.doc'):
            assert upload(b'opaque original', name, 'requirement')['status'] == 'ready'
        failed = upload(b'%PDF-1.7\nbroken', 'broken.pdf', 'requirement')
        assert failed['status'] == 'ready' and 'error' not in failed
        failed_url = base + '/materials/' + failed['id']
        h.expect(operator.post(failed_url + '/retry'), 404)
        body = dict(name='Phase20 real materials', productName='Charger', brand='HX', platform='Amazon',
                    market='US', remarks='', skus=[{'code': 'MAT-20'}], designerId=designer,
                    materialIds=[material['id']])
        key = {'Idempotency-Key': str(uuid4())}
        h.expect(outsider.post(base + '/tasks', json=body, headers=key), 403)
        compatible = h.expect(operator.post(base + '/tasks', json={**body, 'materialIds': [failed['id']]},
            headers={'Idempotency-Key': str(uuid4())}), 201).json()
        assert compatible['status'] == 'pending_review'
        result = h.expect(operator.post(base + '/tasks', json=body, headers=key), 201).json()
        assert result['status'] == 'pending_review'
        assert h.expect(operator.post(base + '/tasks', json=body, headers=key), 200).json()['id'] == result['id']
        materials = h.expect(old.get(base + '/tasks/' + result['id'] + '/materials'), 200).json()
        assert materials[0]['id'] == material['id']
        h.expect(operator.delete(url), 409)
        h.expect(operator.post(url + '/retry'), 404)
        h.expect(operator.post(base + '/tasks', json=body, headers={'Idempotency-Key': str(uuid4())}), 409)
        h.expect(admin.patch(base + '/tasks/' + result['id'] + '/assignment',
                            json={'designerId': next_designer, 'version': result['version']},
                            headers={'Idempotency-Key': str(uuid4())}), 200)
        for path in (url, url + '/content', url + '/content?download=true', url + '/content?variant=256'):
            h.expect(old.get(path), 403)
            h.expect(new.get(path), 200)
        h.expect(outsider.get(base + '/tasks/' + result['id'] + '/materials'), 403)
        h.expect(operator.get(base + '/materials/' + str(uuid4())), 404)
        h.expect(operator.get(base + '/materials/' + domestic_file + '/content'), 404)
        h.expect(operator.post(base + '/tasks', json={**body, 'materialIds': [domestic_file]},
                               headers={'Idempotency-Key': str(uuid4())}), 404)
        h.expect(operator.delete(failed_url), 409)
        disposable = upload()
        disposable_url = base + '/materials/' + disposable['id']
        h.expect(operator.delete(disposable_url), 204)
        h.expect(operator.head(disposable_url + '/content'), 404)
        spare = upload()
        metadata = {k: v for k, v in body.items() if k != 'materialIds'}
        saved = h.expect(operator.post(base + '/tasks', json=metadata,
                                       headers={'Idempotency-Key': str(uuid4())}), 201).json()
        submit_url = base + '/tasks/' + saved['id'] + '/materials'
        submit_body = {'materialIds': [spare['id']], 'version': saved['version']}
        h.expect(operator.post(submit_url, json={**submit_body, 'version': 99}, headers=key), 409)
        submitted = h.expect(operator.post(submit_url, json=submit_body, headers=key), 200).json()
        assert submitted['status'] == 'pending_review' and submitted['version'] == saved['version'] + 1
        assert h.expect(operator.post(submit_url, json=submit_body, headers=key), 200).json()['id'] == saved['id']
        document = BytesIO()
        with ZipFile(document, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Actual document requirements'
                '</w:t></w:r></w:p></w:body></w:document>')
        requirement = upload(document.getvalue(), 'requirements.docx', 'requirement')
        assert requirement['status'] == 'ready' and 'text' not in requirement
        pair = [requirement['id'], upload()['id']]
        both = h.expect(operator.post(base + '/tasks', json={**body, 'materialIds': pair},
                                      headers={'Idempotency-Key': str(uuid4())}), 201).json()
        assert len(h.expect(old.get(base + '/tasks/' + both['id'] + '/materials'), 200).json()) == 2
        h.expect(domestic_session.get(h.BUSINESS['domestic'][0] + '/api/v1/files/' + material['id'] + '/content'), 404)
    assert domestic_snapshot(h) == domestic_before
    assert [(x.object_name, x.etag) for x in domestic.list_objects('domestic-test', recursive=True)] == before_objects
    own = storage('overseas')
    objects = list(own.list_objects('overseas-test', recursive=True))
    assert len(objects) >= 2
    for client in (Minio('overseas-minio:9000', secure=False),
                   Minio('overseas-minio:9000', access_key='domestic-test',
                         secret_key='domestic-phase20-test-only', secure=False)):
        try:
            client.stat_object('overseas-test', objects[0].object_name)
        except S3Error as error:
            assert error.code in ('AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch')
        else:
            raise AssertionError('Private overseas storage accessible across credentials')
    print('PASS Phase20 real MinIO bytes/private credentials; upload/download/HEAD/removed retry; '
          'ownership/atomic binding/idempotency/reassignment; domestic DB and objects unchanged', flush=True)
