import json
from hashlib import sha256
import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.overseas.generation import delivery
from test_overseas_pictures import png
from test_overseas_materials import MemoryStore


@pytest.fixture
def protocol(tmp_path, monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(delivery, 'get_store', lambda: store)
    job = SimpleNamespace(id=uuid4(), kind='generation', payload={'sku': {'pictures': [
        {'width': 1024, 'height': 1024}, {'width': 1024, 'height': 1024}]}})
    workspace = SimpleNamespace(work=tmp_path)
    receipt = SimpleNamespace(error=None, turn_completed=True, session_id='session')
    (tmp_path / 'one.png').write_bytes(png())
    (tmp_path / 'two.png').write_bytes(png(color='blue'))
    return job, workspace, receipt, store


def validate(protocol, entries):
    job, workspace, receipt, _ = protocol
    (workspace.work / 'outputs.json').write_text(json.dumps({'images': entries}))
    return delivery.HANDLER.validate(job, workspace, receipt)


@pytest.mark.parametrize('entries', [[], [{'position': 0, 'path': 'one.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 0, 'path': 'two.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': './one.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': '../two.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': '.'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': '/tmp/two.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': True, 'path': 'two.png'}],
    [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': 'original-image'}]])
def test_bad_manifest_never_stores_partial_sku(protocol, entries):
    with pytest.raises((ValueError, OSError)):
        validate(protocol, entries)
    assert protocol[-1].data == {}


@pytest.mark.parametrize('kind', ['corrupt', 'dimensions', 'symlink', 'hardlink', 'missing'])
def test_invalid_second_image_never_stores_first(protocol, kind):
    job, workspace, _, store = protocol
    path = workspace.work / 'two.png'
    path.unlink()
    if kind == 'corrupt':
        path.write_bytes(b'corrupt')
    elif kind == 'dimensions':
        path.write_bytes(png((8, 8)))
    elif kind == 'symlink':
        path.symlink_to(workspace.work / 'one.png')
    elif kind == 'hardlink':
        os.link(workspace.work / 'one.png', path)
    with pytest.raises(Exception):
        validate(protocol, [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': 'two.png'}])
    assert not store.data


def test_success_is_json_metadata_not_bytes(protocol):
    result = validate(protocol, [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': 'two.png'}])
    assert len(result['images']) == len(protocol[-1].data) == 2
    json.dumps(result)
    assert all(len(i['checksum']) == 64 for i in result['images'])


def test_storage_failure_retains_inaccessible_immutable_objects(protocol, monkeypatch):
    store = protocol[-1]
    put = store.put
    def failing(record, data):
        if store.data:
            raise RuntimeError('storage unavailable')
        put(record, data)
    monkeypatch.setattr(store, 'put', failing)
    with pytest.raises(RuntimeError):
        validate(protocol, [{'position': 0, 'path': 'one.png'}, {'position': 1, 'path': 'two.png'}])
    assert len(store.data) == 1


def test_revision_copy_of_original_cannot_become_new_version(protocol):
    job, workspace, _, store = protocol
    job.kind = 'revision'
    job.payload = {'position': 0, 'original': {'width': 1024, 'height': 1024,
        'checksum': sha256((workspace.work / 'one.png').read_bytes()).hexdigest()}}
    with pytest.raises(ValueError, match='Unchanged revision'):
        validate(protocol, [{'position': 0, 'path': 'one.png'}])
    assert not store.data
