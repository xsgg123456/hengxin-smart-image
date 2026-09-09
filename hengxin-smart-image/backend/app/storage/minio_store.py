from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager, Timeout

from app.core.config import get_settings


class MinioStore:
    def __init__(self):
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint, access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key, secure=settings.minio_secure,
            http_client=PoolManager(timeout=Timeout(connect=3, read=30), retries=False),
        )

    def ensure_private(self, bucket):
        if not self.client.bucket_exists(bucket):
            try:
                self.client.make_bucket(bucket)
            except S3Error as error:
                if error.code not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                    raise
        try:
            policy = self.client.get_bucket_policy(bucket)
        except S3Error as error:
            if error.code != 'NoSuchBucketPolicy':
                raise
        else:
            if policy:
                raise RuntimeError('File bucket must have no anonymous access policy')

    def put(self, record, data):
        self.ensure_private(record.bucket)
        self.client.put_object(record.bucket, record.object_key, BytesIO(data), len(data),
                               content_type=record.content_type)

    def remove(self, record):
        self.client.remove_object(record.bucket, record.object_key)

    def open(self, record):
        self.ensure_private(record.bucket)
        return self.client.get_object(record.bucket, record.object_key)


@lru_cache
def get_store():
    return MinioStore()
