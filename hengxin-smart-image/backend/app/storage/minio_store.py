from functools import lru_cache
from datetime import timedelta
from io import BytesIO
import logging
from threading import Lock
from time import monotonic

from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager, Timeout

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MinioStore:
    PRIVATE_CHECK_SECONDS = 30
    FAILED_CHECK_SECONDS = 2
    _initialization_lock = Lock()

    def __init__(self):
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint, access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key, secure=settings.minio_secure,
            http_client=PoolManager(timeout=Timeout(connect=3, read=30), retries=False),
        )

    def ensure_private(self, bucket, *, force=True):
        # Explicit checks remain forceful. Object operations merge concurrent checks
        # per bucket, and never reuse an expired success while verification runs.
        with self._initialization_lock:
            if not hasattr(self, '_policy_checks'):
                self._policy_checks = {}
            state = self._policy_checks.setdefault(bucket, [Lock(), 0.0, False])
        with state[0]:
            if not force and monotonic() < state[1]:
                if not state[2]:
                    raise RuntimeError('File bucket privacy verification unavailable')
                return
            state[2] = False
            try:
                self._check_private(bucket)
            except Exception:
                state[1] = monotonic() + self.FAILED_CHECK_SECONDS
                logger.warning('File bucket privacy verification failed: %s', bucket)
                raise
            state[1], state[2] = monotonic() + self.PRIVATE_CHECK_SECONDS, True

    def _check_private(self, bucket):
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
        self.ensure_private(record.bucket, force=False)
        self.client.put_object(record.bucket, record.object_key, BytesIO(data), len(data),
                               content_type=record.content_type)

    def remove(self, record):
        self.client.remove_object(record.bucket, record.object_key)

    def open(self, record):
        self.ensure_private(record.bucket, force=False)
        return self.client.get_object(record.bucket, record.object_key)

    def stat(self, record):
        self.ensure_private(record.bucket, force=False)
        return self.client.stat_object(record.bucket, record.object_key).size

    def signed_delivery(self, record, method, headers):
        self.ensure_private(record.bucket, force=False)
        return self.client.get_presigned_url(method, record.bucket, record.object_key,
                                             expires=timedelta(seconds=60), response_headers=headers)


@lru_cache
def get_store():
    return MinioStore()
