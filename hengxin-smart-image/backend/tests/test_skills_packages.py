import io
import json
import stat
import zipfile

import pytest

from app.modules.skills.package_validator import validate_package


def archive(entries=None, compression=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=compression) as output:
        for name, content in (entries or {'SKILL.md': '---\nname: demo\ndescription: 描述\n---\n'}).items():
            output.writestr(name, content)
    return stream.getvalue()


def test_valid_nested_package_and_manifest():
    data = archive({'demo/SKILL.md': '---\nname: demo\ndescription: 描述\n---\n',
                    'demo/hengxin-skill.json': json.dumps({'mode': 'text', 'version': '1.0.0'})})
    parsed = validate_package(data, 'text', '1.0.0')
    assert parsed.name == 'demo' and 'SKILL.md' in parsed.files


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', 'a\\b', 'a/../b',
                                 'a//b', 'CON', 'nul.txt', 'a./file'])
def test_unsafe_paths_rejected(name):
    with pytest.raises(ValueError):
        validate_package(archive({name: 'x'}), 'text', '1.0.0')


def test_symlink_case_collision_and_compression_bomb():
    link = zipfile.ZipInfo('link')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    cases = [archive({link: '../target'}), archive({'A': '1', 'a': '2'}),
             archive({'bomb': 'x' * 100000}, zipfile.ZIP_DEFLATED)]
    for data in cases:
        with pytest.raises(ValueError):
            validate_package(data, 'text', '1.0.0')


def test_corrupt_crc_and_metadata_rejected():
    data = archive()
    corrupt = data.replace(b'name: demo', b'name: fail', 1)
    for invalid in [corrupt, archive({'SKILL.md': 'no metadata'}),
                    archive({'SKILL.md': '---\nname: x\ndescription: y\n---\n',
                             'hengxin-skill.json': '{"mode":"product"}'})]:
        with pytest.raises(ValueError):
            validate_package(invalid, 'text', '1.0.0')
