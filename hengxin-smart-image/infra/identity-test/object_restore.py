"""Disposable MinIO backup/restore drill; source objects are never mutated."""
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from phase20_checks import storage

SOURCE = 'overseas-test'


def read(client, bucket, name):
    response = client.get_object(bucket, name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def manifest(client, bucket):
    result = {}
    for obj in client.list_objects(bucket, recursive=True):
        info = client.stat_object(bucket, obj.object_name)
        data = read(client, bucket, obj.object_name)
        assert len(data) == info.size
        result[obj.object_name] = (len(data), sha256(data).hexdigest(), info.content_type)
    return result


def copy(client, source, target):
    for obj in client.list_objects(source, recursive=True):
        info = client.stat_object(source, obj.object_name)
        data = read(client, source, obj.object_name)
        client.put_object(target, obj.object_name, BytesIO(data), len(data),
                          content_type=info.content_type)


def run():
    # These aliases and credentials exist only inside run.py's random Docker network.
    client = storage('overseas')
    anonymous = Minio('overseas-minio:9000', secure=False)
    before = manifest(client, SOURCE)
    assert before, 'The Phase20/23 source fixtures must exist before restoration'
    source_etags = sorted((x.object_name, x.etag) for x in client.list_objects(SOURCE, recursive=True))
    created = []
    try:
        backup, restored = ('phase25-' + kind + '-' + uuid4().hex for kind in ('backup', 'restore'))
        for bucket in (backup, restored):
            assert not client.bucket_exists(bucket)
            client.make_bucket(bucket)
            created.append(bucket)
            assert list(client.list_objects(bucket, recursive=True)) == []
        copy(client, SOURCE, backup)
        assert manifest(client, backup) == before
        copy(client, backup, restored)
        assert manifest(client, restored) == before
        for bucket in (backup, restored):
            try:
                anonymous.stat_object(bucket, next(iter(before)))
            except S3Error as error:
                assert error.code == 'AccessDenied', error.code
            else:
                raise AssertionError('Backup/restore bucket exposed anonymously')
        assert manifest(client, SOURCE) == before
        assert sorted((x.object_name, x.etag) for x in client.list_objects(SOURCE, recursive=True)) == source_etags
        print(f'PASS Phase25 object backup/restore: {len(before)} objects, '
              f'{sum(v[0] for v in before.values())} bytes, SHA256/size/content-type equal; '
              'private backup and restore buckets; source unchanged', flush=True)
    finally:
        # Only exact bucket names successfully created by this invocation are owned.
        for bucket in reversed(created):
            assert bucket != SOURCE and bucket.startswith(('phase25-backup-', 'phase25-restore-'))
            for obj in client.list_objects(bucket, recursive=True):
                client.remove_object(bucket, obj.object_name)
            client.remove_bucket(bucket)
