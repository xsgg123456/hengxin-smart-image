from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import pytest
from minio.error import S3Error
from app.storage import minio_store

@pytest.fixture
def policy_env(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(minio_store, 'monotonic', lambda: clock[0])
    state = SimpleNamespace(clock=clock, checks=0, gets=0, makes=0, exists=True,
                            public=False, unavailable=False, puts=0)
    class Client:
        def bucket_exists(self, bucket):
            return state.exists
        def make_bucket(self, bucket):
            state.makes += 1
            state.exists = True
        def get_bucket_policy(self, bucket):
            state.checks += 1
            if state.unavailable:
                raise OSError('policy service unavailable')
            if state.public:
                return '{"Statement": []}'
            raise S3Error(response=None, code='NoSuchBucketPolicy', message='none',
                          resource='', request_id='', host_id='')
        def get_object(self, *args):
            state.gets += 1
            return 'stream'
        def put_object(self, *args, **kwargs):
            state.puts += 1
    store = object.__new__(minio_store.MinioStore)
    store.client = Client()
    state.store = store
    state.record = SimpleNamespace(bucket='private', object_key='image', content_type='image/png')
    return state


def test_concurrent_reads_merge_policy_checks(policy_env):
    env = policy_env
    entered, release = Event(), Event()
    original = env.store.client.get_bucket_policy
    def blocked(bucket):
        entered.set()
        assert release.wait(5)
        return original(bucket)
    env.store.client.get_bucket_policy = blocked
    with ThreadPoolExecutor(max_workers=12) as executor:
        jobs = [executor.submit(env.store.open, env.record) for _ in range(12)]
        assert entered.wait(5)
        assert env.gets == 0
        release.set()
        assert all(j.result() == 'stream' for j in jobs)
    assert env.checks == 1 and env.gets == 12
    env.clock[0] += 30
    env.store.open(env.record)
    assert env.checks == 2


@pytest.mark.parametrize('failure', ['public', 'unavailable'])
def test_expired_success_fails_closed_and_negative_cache_is_bounded(policy_env, failure):
    env = policy_env
    env.store.open(env.record)
    setattr(env, failure, True)
    env.clock[0] += 30
    with ThreadPoolExecutor(max_workers=12) as executor:
        jobs = [executor.submit(env.store.open, env.record) for _ in range(12)]
        for job in jobs:
            with pytest.raises((RuntimeError, OSError)):
                job.result()
    assert env.checks == 2 and env.gets == 1
    setattr(env, failure, False)
    with pytest.raises(RuntimeError):
        env.store.open(env.record)
    env.clock[0] += 2
    env.store.open(env.record)
    assert env.checks == 3 and env.gets == 2


def test_explicit_force_check_revokes_cached_success(policy_env):
    env = policy_env
    env.store.open(env.record)
    env.public = True
    with pytest.raises(RuntimeError):
        env.store.ensure_private('private')
    with pytest.raises(RuntimeError):
        env.store.open(env.record)
    assert env.gets == 1 and env.checks == 2
    env.public = False
    env.store.ensure_private('private')
    env.store.open(env.record)
    assert env.checks == 3 and env.gets == 2


def test_upload_still_creates_missing_bucket_and_shares_validation(policy_env):
    env = policy_env
    env.exists = False
    env.store.put(env.record, b'original')
    env.store.open(env.record)
    assert env.makes == env.puts == env.checks == env.gets == 1


def test_buckets_do_not_share_verification(policy_env):
    env = policy_env
    env.store.open(env.record)
    env.public = True
    env.record.bucket = 'other'
    with pytest.raises(RuntimeError):
        env.store.open(env.record)
    assert env.gets == 1 and env.checks == 2
