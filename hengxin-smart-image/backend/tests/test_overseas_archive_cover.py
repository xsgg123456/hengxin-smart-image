"""Archive summary covers use immutable first assets without reading object bytes."""
from uuid import UUID
from sqlalchemy import delete, select
from app.overseas.archives.models import ArchiveAsset
from app.overseas.tasks.cleanup import cleanup_once
from test_overseas_task_deletion import deletion, generated, archived, request
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_overseas_assignment import change_roles


def test_summary_cover_matches_first_picture_and_never_reads_bytes(deletion, monkeypatch):
    client, _, _, _, _, store = deletion
    archive = archived(deletion, generated(deletion, 3))
    detail = client.get(ROOT + '/archives/' + archive['id']).json()
    assert archive['cover'] == detail['pictures'][0] == detail['cover']
    assert archive['pictureCount'] == 3 and 'pictures' not in archive
    monkeypatch.setattr(store, 'open', lambda _: (_ for _ in ()).throw(AssertionError('list read image bytes')))
    listed = client.get(ROOT + '/archives?pageSize=1').json()
    assert listed['items'][0]['cover'] == detail['pictures'][0]
    assert client.get(ROOT + '/archives?search=no-match').json()['items'] == []


def test_cover_survives_source_deletion_and_enforces_archive_permissions(deletion):
    client, factory, actor, task, _, store = deletion
    archive = archived(deletion, generated(deletion))
    original = client.get(archive['cover']['url']).content
    assert request(client, task).status_code == 200
    assert cleanup_once(factory, store) == 1
    item = client.get(ROOT + '/archives').json()['items'][0]
    assert item['sourceDeleted'] and item['cover'] == archive['cover']
    assert client.get(item['cover']['url']).content == original
    change_roles(factory, actor, ('designer',))
    assert client.get(ROOT + '/archives').json()['items'] == []
    assert client.get(item['cover']['url']).status_code == 403


def test_legacy_archive_without_asset_has_nullable_cover_and_upgrades_on_view(deletion):
    client, factory, _, _, _, _ = deletion
    archive = archived(deletion, generated(deletion))
    with factory.begin() as session:
        session.execute(delete(ArchiveAsset).where(ArchiveAsset.archive_id == UUID(archive['id'])))
    assert client.get(ROOT + '/archives').json()['items'][0]['cover'] is None
    detail = client.get(ROOT + '/archives/' + archive['id']).json()
    assert detail['cover'] == detail['pictures'][0] == archive['cover']
    with factory() as session:
        assert len(session.scalars(select(ArchiveAsset)).all()) == 2


def test_cover_content_cannot_be_read_under_another_archive(deletion):
    client, _, _, _, _, _ = deletion
    archive = archived(deletion, generated(deletion))
    url = archive['cover']['url'].replace(archive['id'], '00000000-0000-0000-0000-000000000000')
    assert client.get(url).status_code == 404
