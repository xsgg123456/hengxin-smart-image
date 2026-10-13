from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile
import pytest
from app.overseas.management.packages import unpack
from app.overseas.management.settings import freeze_selected
from app.overseas.execution import materials as execution_materials
from test_overseas_tasks import overseas, HEADERS
from test_overseas_materials import materials
from test_overseas_assignment import change_roles


def package(files):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


@pytest.mark.parametrize('path', ['../secret', '/secret', 'CON.txt', 'assets/../x', 'SKILL.md/child'])
def test_unsafe_package(path):
    with pytest.raises(ValueError):
        unpack(package({'SKILL.md': 'instructions', path: b'x'}))


def test_complete_package_roundtrip_and_text_update(materials, monkeypatch, tmp_path):
    client, factory, actor, _, store = materials
    change_roles(factory, actor, ('super_admin',))
    binary = bytes(range(256))
    response = client.post('/api/overseas/v1/management/skill-packages?name=whole-pack&stage=generation',
        headers=HEADERS, files={'file': ('pack.zip', package({'pack/SKILL.md':'Use references', 'pack/assets/ref.png':binary}), 'application/zip')})
    assert response.status_code == 201, response.text
    item = response.json()
    assert item['versions'][0]['assetNames'] == ['assets/ref.png']
    assert 'objectKey' not in response.text
    updated = client.post('/api/overseas/v1/management/skills/' + item['id'] + '/versions', headers=HEADERS,
        json={'version':1,'files':{'SKILL.md':'Updated'}})
    assert updated.status_code == 200, updated.text
    assert updated.json()['versions'][0]['assetNames'] == ['assets/ref.png']
    with factory.begin() as session:
        frozen = freeze_selected(session, item['id'])
    monkeypatch.setattr(execution_materials, 'get_store', lambda: store)
    work, control = tmp_path / 'work', tmp_path / 'control'
    work.mkdir(); control.mkdir()
    workspace = SimpleNamespace(work=work, control=control)
    execution_materials.prepare(SimpleNamespace(payload=frozen), workspace)
    assert (workspace.local_skill / 'assets/ref.png').read_bytes() == binary
    assert (workspace.local_skill / 'SKILL.md').read_text() == 'Updated'
    key = frozen['skill']['assets']['assets/ref.png']['objectKey']
    store.data[key] = b'corrupt'
    with pytest.raises(ValueError, match='integrity'):
        execution_materials.prepare(SimpleNamespace(payload=frozen), workspace)
    conflict = client.post('/api/overseas/v1/management/skills/' + item['id'] + '/versions', headers=HEADERS,
        json={'version':2,'files':{'SKILL.md':'Updated','assets/ref.png':'collision'}})
    assert conflict.status_code == 422
