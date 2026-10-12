"""Runs inside the disposable verification container, never against user services."""
import io
import json
import sys

import psycopg
from minio import Minio
from minio.error import S3Error
from redis import Redis
from redis.exceptions import AuthenticationError


def denied(call, errors, codes=None):
    try:
        call()
    except errors as error:
        if codes is not None:
            assert getattr(error, 'code', None) in codes or getattr(error, 'sqlstate', None) in codes
        return
    raise AssertionError('Expected permission rejection')


def database(side, password=None, user='overseas_app'):
    return psycopg.connect(host=side['postgres'], port=5432, user=user,
                           password=password or side['app_password'],
                           dbname=side['database'], connect_timeout=3, autocommit=True)


def storage(side, credentials=None):
    credentials = credentials or side
    return Minio(side['minio'] + ':9000', access_key=credentials['access_key'],
                 secret_key=credentials['secret_key'], secure=False)


def database_auth_denied(side, password):
    try:
        database(side, password)
    except psycopg.OperationalError as error:
        # libpq connect failures can omit SQLSTATE; require the server auth message.
        assert error.sqlstate == '28P01' or 'password authentication failed for user "overseas_app"' in str(error)
        return
    raise AssertionError('Cross-business database credentials were accepted')


def main():
    overseas, domestic = json.load(sys.stdin)
    for own, peer in ((overseas, domestic), (domestic, overseas)):
        assert own['database'].endswith('_test')
        with database(own) as connection:
            assert connection.execute('SELECT current_user').fetchone()[0] == 'overseas_app'
            denied(lambda: connection.execute('CREATE TABLE forbidden(id int)'), psycopg.errors.InsufficientPrivilege)
            denied(lambda: connection.execute('CREATE TEMP TABLE forbidden(id int)'), psycopg.errors.InsufficientPrivilege)
            denied(lambda: connection.execute('CREATE SCHEMA forbidden'), psycopg.errors.InsufficientPrivilege)
            denied(lambda: connection.execute("UPDATE overseas_alembic_version SET version_num='forbidden'"),
                   psycopg.errors.InsufficientPrivilege)
        with database(own, own['owner_password'], 'overseas_owner') as owner:
            owner.execute('CREATE TABLE isolation_probe(id int PRIMARY KEY)')
        with database(own) as app:
            app.execute('INSERT INTO isolation_probe VALUES (1)')
            assert app.execute('SELECT id FROM isolation_probe').fetchone() == (1,)
            app.execute('UPDATE isolation_probe SET id=2')
            app.execute('DELETE FROM isolation_probe')
            denied(lambda: app.execute('DROP TABLE isolation_probe'), psycopg.errors.InsufficientPrivilege)
        with database(own, own['owner_password'], 'overseas_owner') as owner:
            owner.execute('DROP TABLE isolation_probe')
        database_auth_denied(peer, own['app_password'])
        client = storage(own)
        admin = Minio(own['minio'] + ':9000', access_key=own['root_user'],
                      secret_key=own['root_password'], secure=False)
        hidden_bucket = own['bucket'] + '-hidden'
        admin.make_bucket(hidden_bucket)
        # MinIO filters ListBuckets by per-bucket permissions without ListAllMyBuckets.
        assert {bucket.name for bucket in client.list_buckets()} == {own['bucket']}
        client.put_object(own['bucket'], 'probe', io.BytesIO(b'isolated'), 8)
        response = client.get_object(own['bucket'], 'probe')
        try:
            assert response.read() == b'isolated'
        finally:
            response.close()
            response.release_conn()
        try:
            client.get_bucket_policy(own['bucket'])
        except S3Error as error:
            assert error.code == 'NoSuchBucketPolicy'
        else:
            raise AssertionError('Bucket must have no anonymous policy')
        for label, forbidden in (('create-bucket', lambda: client.make_bucket('forbidden-bucket')),
                          ('hidden-bucket', lambda: client.list_objects(hidden_bucket).__next__()),
                          ('cross-get', lambda: storage(peer, own).get_object(peer['bucket'], 'probe')),
                          ('cross-put', lambda: storage(peer, own).put_object(peer['bucket'], 'forbidden', io.BytesIO(b'x'), 1)),
                          ('anonymous', lambda: Minio(own['minio'] + ':9000', secure=False).stat_object(own['bucket'], 'probe'))):
            print('Checking ' + label, flush=True)
            denied(forbidden, S3Error, {'AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch'})
        client.remove_object(own['bucket'], 'probe')
        admin.remove_bucket(hidden_bucket)
        redis = Redis(host=own['redis'], password=own['redis_password'], socket_timeout=3)
        assert redis.ping()
        denied(lambda: Redis(host=own['redis'], socket_timeout=3).ping(), AuthenticationError)
        denied(lambda: Redis(host=peer['redis'], password=own['redis_password'], socket_timeout=3).ping(), AuthenticationError)
    print('PASS: bidirectional PostgreSQL/MinIO/Redis credential isolation; DML allowed, DDL denied; private buckets')


if __name__ == '__main__':
    main()
