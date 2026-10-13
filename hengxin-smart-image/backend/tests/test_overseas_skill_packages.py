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


def test_old_queued_snapshot_still_reads_complete_files_and_assets(materials, monkeypatch, tmp_path):
    from hashlib import sha256
    _, _, _, _, store = materials
    binary = bytes(range(256))
    record = SimpleNamespace(bucket='test', object_key='legacy-resource', content_type='image/png')
    store.put(record, binary)
    frozen = dict(skill=dict(name='whole-pack', files={'SKILL.md': 'Old queued instructions'},
        assets={'assets/ref.png': dict(bucket='test', objectKey='legacy-resource',
            checksum=sha256(binary).hexdigest(), sizeBytes=len(binary))}))
    monkeypatch.setattr(execution_materials, 'get_store', lambda: store)
    work, control = tmp_path / 'work', tmp_path / 'control'
    work.mkdir()
    control.mkdir()
    workspace = SimpleNamespace(work=work, control=control)
    execution_materials.prepare(SimpleNamespace(payload=frozen), workspace)
    assert (workspace.local_skill / 'assets/ref.png').read_bytes() == binary
    assert (workspace.local_skill / 'SKILL.md').read_text() == 'Old queued instructions'
    store.data['legacy-resource'] = b'corrupt'
    with pytest.raises(ValueError, match='integrity'):
        execution_materials.prepare(SimpleNamespace(payload=frozen), workspace)
