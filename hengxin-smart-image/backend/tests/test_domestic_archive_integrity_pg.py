"""Archive file routes must never use corrupted pointers to private originals."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from types import SimpleNamespace
from uuid import UUID

from app.db.session import get_session
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.domestic_studio import archive_deletion, archive_service, file_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveFile
from app.modules.domestic_studio.turn_models import Picture, Upload
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from test_domestic_archive_pg import setup_archive
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


@pytest.mark.parametrize('reseal', [False, True])
def test_corrupt_archive_cannot_expose_unarchived_source_or_zip(context, database, monkeypatch, tmp_path, reseal):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        archive_id = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='归档隔离'), 'archive').id
    archive_service.complete(factory, store, archive_id, first)
    private = file_service.upload(factory, store, first, 'camera', channel, b'private-data', '私人资料.txt')
    private_id = UUID(private['id'].split(':', 1)[1])
    with factory.begin() as session:
        private_row = session.scalar(select(Upload).where(Upload.id == private_id))
        source_picture = session.scalar(select(Picture))
        rows = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == archive_id)
                                    .order_by(ArchiveFile.position, ArchiveFile.id)))
        uploaded = next(row for row in rows if row.kind == 'upload')
        picture = next(row for row in rows if row.kind == 'picture')
        uploaded.object_key, uploaded.bucket = private_row.object_key, private_row.bucket
        uploaded.size_bytes, uploaded.checksum = private_row.size_bytes, private_row.checksum
        picture.object_key = source_picture.object_key
        if reseal:
            # Simulate even a consistently re-sealed but non-archive object key.
            record = session.get(Archive, archive_id)
            snapshot = dict(record.snapshot)
            snapshot['files'] = [archive_service.manifest_entry(row) for row in rows]
            snapshot['checksum'] = archive_service.seal({'turns': snapshot['turns'], 'files': snapshot['files']})
            record.snapshot = snapshot
        upload_id, picture_id = uploaded.id, picture.id
        forbidden = {(private_row.bucket, private_row.object_key), (source_picture.bucket, source_picture.object_key)}
    opened, real_open = [], store.open
    def track(row):
        opened.append((row.bucket, row.object_key))
        return real_open(row)
    monkeypatch.setattr(store, 'open', track)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: second
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            root = '/api/v1/domestic-studio'
            assert client.get(f'{root}/workspaces/camera/files/{private_id}/content').status_code == 404
            assert client.get(f'{root}/archives/{archive_id}').status_code == 503
            for method, suffix in [('GET', f'/files/{upload_id}/content'),
                                   ('HEAD', f'/files/{upload_id}/content'),
                                   ('GET', f'/files/{picture_id}/content?preview=true'),
                                   ('HEAD', f'/files/{picture_id}/content?thumbnail=true'),
                                   ('GET', '/download')]:
                assert client.request(method, f'{root}/archives/{archive_id}{suffix}').status_code == 503
            assert client.get(f'{root}/archives/{archive_id}/files/{picture_id}/content',
                              headers={'If-None-Match': '*'}).status_code == 503
            assert not forbidden.intersection(opened)
    finally:
        for dependency in (get_session, get_identity_id, get_store):
            app.dependency_overrides.pop(dependency, None)
    monkeypatch.setattr(archive_deletion, 'get_settings', lambda: SimpleNamespace(codex_execution_root=str(tmp_path)))
    with factory.begin() as session:
        session.get(UserRecord, first).role = 'super_admin'
    with factory.begin() as session:
        assert archive_deletion.request(session, first, archive_id)['status'] == 'deleting'
    assert not archive_deletion.process(factory, store, archive_id)
    assert forbidden.issubset(store.objects)
    with factory() as session:
        assert session.get(Archive, archive_id) is not None


def test_archive_rejects_same_length_corrupted_attachment_before_download(context, database, monkeypatch):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        archive_id = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='附件'), 'archive').id
    archive_service.complete(factory, store, archive_id, first)
    with factory() as session:
        row = session.scalar(select(ArchiveFile).where(ArchiveFile.archive_id == archive_id,
                                                        ArchiveFile.kind == 'upload'))
        asset_id, key = row.id, (row.bucket, row.object_key)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: second
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            url = f'/api/v1/domestic-studio/archives/{archive_id}/files/{asset_id}/content'
            assert client.get(url).content == '原始附件'.encode()
            store.objects[key] = b'x' * len(store.objects[key])
            damaged = client.get(url)
            assert damaged.status_code == 503 and damaged.content != store.objects[key]
    finally:
        for dependency in (get_session, get_identity_id, get_store):
            app.dependency_overrides.pop(dependency, None)
