import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('outon_skill', Path(__file__).with_name('outon-skill.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def test_new_package_preserves_all_existing_metadata_and_source_bytes():
    previous = {'schema': 1, 'items': [{'name': 'existing', 'entries': {'font.ttf': {'sha256': 'abc'}},
                                      'sourceEntries': {}, 'adaptedFiles': ['SKILL.md']}]}
    original = copy.deepcopy(previous)
    package = SimpleNamespace(name=s.NAME, checksum='source-checksum', description='source description')
    entries = {'SKILL.md': {'sha256': 'md', 'size': 13}, 'font.ttf': {'sha256': 'font', 'size': 45}}
    result = s.merged_manifest(previous, package, entries)
    assert previous == original
    assert result['items'][:-1] == original['items']
    added = result['items'][-1]
    assert added['entries'] == added['sourceEntries'] == entries
    assert added['checksum'] == added['sourceChecksum'] == package.checksum
    assert added['adaptedFiles'] == []
    assert 'platforms' not in added and 'enabled' not in added


@pytest.mark.parametrize('names,identity', [([s.NAME], s.NAME), ([], 'another-skill')])
def test_duplicate_or_unexpected_identity_is_rejected(names, identity):
    with pytest.raises(ValueError):
        s.merged_manifest({'items': [{'name': n} for n in names]}, SimpleNamespace(name=identity), {})


@pytest.mark.parametrize('corrupt', [False, True])
def test_portable_source_preserves_assets_and_requires_recorded_hashes(corrupt):
    spec = importlib.util.spec_from_file_location('outon_source', Path(__file__).with_name('outon-source.py'))
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    font, logo = 'assets/brand/fonts/font.ttf', 'assets/brand/logos/logo.png'
    digest = hashlib.sha256(b'original').hexdigest()
    files = {font: b'wrong' if corrupt else b'original', logo: b'original', 'SKILL.md': b'unchanged',
        'assets/brand/manifest.json': json.dumps({'fonts': {'font': {'path': font,
            'sha256': digest, 'sources': ['Z:/local/font.ttf']}}, 'logos': {'logo': {
            'path': logo, 'sha256': digest, 'source': 'Z:/local/logo.png'}}}).encode(),
        'assets/brand/font-reference.json': json.dumps({'sources': [{
            'source': 'Z:/local/font.ttf', 'sha256': digest}]}).encode()}
    original = copy.deepcopy(files)
    if corrupt:
        with pytest.raises(AssertionError, match='Font checksum'):
            source.portable(files)
    else:
        result = source.portable(files)
        assert files == original
        assert all(result[n] == files[n] for n in (font, logo, 'SKILL.md'))
        assert b'Z:' not in result['assets/brand/manifest.json']
        assert json.loads(result['assets/brand/font-reference.json'])['sources'][0]['source'] == font
