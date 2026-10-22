"""Real files in temporary overseas installs; no shared user/production directories."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.core.config import get_settings
from app.overseas.management import installed_catalog as catalog, skill_install
from app.overseas.management.installed_tree import tree
from app.overseas.management.models import Skill, SkillVersion
from app.overseas.management.settings import freeze_selected, freeze
from app.overseas.execution.materials import prepare
from overseas_installed_helpers import install_sample, enable_sample
from test_overseas_tasks import overseas, setup, ROOT
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish


def test_catalog_and_studio_share_real_install_and_complete_frozen_round(studio, tmp_path):
    client, factory, _, task, _, _ = studio
    contents = {'assets/ref.png': bytes(range(256)), 'scripts/check.py': b'print("ok")',
                'references/rules.md': b'Rules', 'agents/openai.yaml': b'interface: {}'}
    item = install_sample(files=contents, display_name='沃尔玛新品主图 · 新版（9.27）')
    enable_sample(factory)
    listing = client.get(ROOT + '/management/skills').json()['items']
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert listing == [{**item, 'enabled': True, 'version': 1}]
    assert view['skills'] == [item]
    assert set(item) == {'id', 'name', 'displayName', 'description'}
    response = send(client, task, skillId=item['id'])
    assert response.status_code == 200, response.text
    from sqlalchemy import select
    from app.overseas.execution.models import Job
    with factory() as session:
        frozen = session.scalar(select(Job)).payload
    work, control = tmp_path / 'work', tmp_path / 'control'
    work.mkdir()
    control.mkdir()
    workspace = SimpleNamespace(work=work, control=control)
    prepare(SimpleNamespace(payload=frozen), workspace)
    for relative, data in contents.items():
        assert (workspace.local_skill / relative).read_bytes() == data
    assert len(list(workspace.local_skill.rglob('*'))) >= 9
    finish(factory, response.json()['turns'][0])
    install_sample(content='new release', files={'assets/updated.png': b'new'})
    prepare(SimpleNamespace(payload=frozen), workspace)
    assert (workspace.local_skill / 'assets/ref.png').read_bytes() == contents['assets/ref.png']
    assert not (workspace.local_skill / 'assets/updated.png').exists()
    second = send(client, task, key='second', skillId=item['id'])
    assert second.status_code == 200, second.text
    with factory() as session:
        jobs = session.scalars(select(Job).order_by(Job.created_at)).all()
        assert jobs[-1].payload['skill']['installedRelease'] != frozen['skill']['installedRelease']


def test_uninstalled_rows_hidden_and_old_defaults_only_map_installed_names(overseas):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    old_id = uuid4()
    with factory.begin() as session:
        session.add(Skill(id=old_id, name='sample', stage='analysis'))
        session.flush()
        session.add(SkillVersion(skill_id=old_id, version=1, files={'SKILL.md': 'uninstalled'}))
    assert client.get(ROOT + '/management/skills').json() == {'items': [], 'canToggle': False}
    with factory.begin() as session, pytest.raises(HTTPException) as caught:
        freeze_selected(session, old_id)
    assert caught.value.status_code == 422
    install_sample()
    enable_sample(factory)
    with factory.begin() as session:
        frozen = freeze_selected(session, old_id)
        assert frozen['skill']['id'] == catalog.identity('sample')
        assert 'files' not in frozen['skill']


def test_corruption_missing_root_and_permission_errors_do_not_look_empty(overseas, monkeypatch):
    client, _, _, _ = setup(overseas, ('super_admin',))
    install_sample(files={'assets/ref.png': b'original'})
    release, _ = catalog.catalog()
    root = Path(get_settings().local_skill_root)
    asset = root / 'releases' / release / 'sample/assets/ref.png'
    asset.write_bytes(b'corrupt')
    response = client.get(ROOT + '/management/skills')
    assert response.status_code == 503
    assert str(root) not in response.text
    asset.unlink()
    assert client.get(ROOT + '/management/skills').status_code == 503
    monkeypatch.setattr(catalog, 'root_config', lambda: (root / 'missing', False))
    assert client.get(ROOT + '/management/skills').status_code == 503
    monkeypatch.setattr(catalog, 'root_config', lambda: (_ for _ in ()).throw(PermissionError('private')))
    assert client.get(ROOT + '/management/skills').status_code == 503


def source_package(root, relative, content):
    path = root / relative
    path.mkdir(parents=True)
    (path / 'SKILL.md').write_text('---\nname: original\ndescription: 完整说明\n---\n' + content, encoding='utf-8')
    (path / 'agents').mkdir()
    (path / 'agents/openai.yaml').write_text('default_prompt: 使用 $original', encoding='utf-8')


def test_two_same_names_coexist_idempotently_without_changing_sources(overseas, tmp_path):
    source = tmp_path / 'source'
    source_package(source, 'one/original', '2000×2000')
    source_package(source, 'two/original', '1250×1600')
    mapping = tmp_path / 'map.json'
    rows = [dict(source=f'{folder}/original', name=f'original-{folder}', displayName=folder) for folder in ('one', 'two')]
    mapping.write_text(json.dumps(rows), encoding='utf-8')
    before = [tree(source / row['source'])[0].checksum for row in rows]
    result = skill_install.bundle(source, mapping, tmp_path / 'bundles')
    first = skill_install.install(result['path'])
    second = skill_install.install(result['path'])
    assert first == second
    assert {item['name'] for item in catalog.listing()} == {'original-one', 'original-two'}
    assert [tree(source / row['source'])[0].checksum for row in rows] == before
    frozen = catalog.freeze(catalog.identity('original-one'))
    files = catalog.frozen_package(frozen).files
    assert '2000×2000' in files['SKILL.md'].decode()
    assert files['agents/openai.yaml'].decode().endswith('$original-one')


def test_large_package_and_publish_failure_keep_previous_release(overseas, tmp_path, monkeypatch):
    first = install_sample()
    frozen = catalog.freeze(first['id'])
    original_replace = os.replace
    def fail(source, target):
        if Path(target).name == 'current.json':
            raise OSError('injected pointer failure')
        return original_replace(source, target)
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError, match='pointer'):
        install_sample(content='second', files={'assets/large.bin': b'x' * (21 * 1024 * 1024)})
    assert catalog.freeze(first['id']) == frozen
    assert catalog.frozen_package(frozen).files['SKILL.md'].endswith(b'first')
    monkeypatch.setattr(os, 'replace', original_replace)
    install_sample(content='second', files={'assets/large.bin': b'x' * (21 * 1024 * 1024)})
    assert len(catalog.frozen_package(catalog.freeze(first['id'])).files['assets/large.bin']) > 20 * 1024 * 1024


def test_missing_reference_and_unsafe_links_rejected(tmp_path):
    source_package(tmp_path, 'bad', '[missing](assets/missing.png)')
    with pytest.raises(ValueError, match='missing'):
        tree(tmp_path / 'bad')
    source_package(tmp_path, 'linked', 'all good')
    # Hard links work on both Windows and POSIX and must never be copied.
    os.link(tmp_path / 'linked/SKILL.md', tmp_path / 'linked/extra.md')
    with pytest.raises(ValueError, match='unsafe'):
        tree(tmp_path / 'linked')


def test_domestic_context_cannot_install(overseas, monkeypatch):
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', 'domestic')
    with pytest.raises(ValueError, match='overseas'):
        skill_install.install('/does/not/matter')


def test_directory_cache_skips_byte_reads_and_detects_in_place_changes(overseas, monkeypatch):
    item = install_sample()
    first = catalog.listing()
    called, original = [], catalog.verify_package
    def counted(*args, **kwargs):
        called.append(args[1]['name'])
        return original(*args, **kwargs)
    monkeypatch.setattr(catalog, 'verify_package', counted)
    assert catalog.listing() == first
    assert called == []
    # Executions always re-read full content even when directory listing is cached.
    catalog.frozen_package(catalog.freeze(item['id']))
    assert called == ['sample']
    release, _ = catalog.catalog()
    path = Path(get_settings().local_skill_root) / 'releases' / release / 'sample/SKILL.md'
    path.write_bytes(path.read_bytes().replace(b'first', b'other'))
    with pytest.raises(HTTPException) as caught:
        catalog.listing()
    assert caught.value.status_code == 503


def test_production_install_root_is_explicit_overseas_allowlist(overseas):
    get_settings().app_env = 'production'
    get_settings().local_skill_root = '/var/lib/hengxin/skills'
    with pytest.raises(ValueError, match='approved overseas'):
        skill_install.install('/not-read')


@pytest.mark.skipif(os.name != 'posix', reason='Production ownership checks require Linux')
def test_production_tree_rejects_worker_writable_packages(tmp_path):
    from app.overseas.management.installed_tree import protect
    source_package(tmp_path, 'package', 'complete')
    path = tmp_path / 'package/SKILL.md'
    path.chmod(0o666)
    with pytest.raises(ValueError, match='root-owned'):
        protect(path, path.stat())
