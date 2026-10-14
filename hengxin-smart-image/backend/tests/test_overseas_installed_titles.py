"""Display metadata comes from verified installed bytes; frozen history stays valid."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.overseas.management import installed_catalog as catalog
from app.overseas.management.settings import freeze_selected
from overseas_installed_helpers import install_sample
from test_overseas_tasks import overseas, setup, ROOT
from test_overseas_materials import materials
from test_overseas_studio import studio


@pytest.mark.parametrize('body,expected', [
    ('# OUTON · Wayfair新品整套图片生成\n\n# 第二个标题', 'OUTON · Wayfair新品整套图片生成'),
    ('```md\n# 示例\n```\n~~~\n# 示例二\n~~~\n\n# 实际标题 ###', '实际标题'),
    ('    # 缩进代码\n\n<!--\n# 注释\n-->\n\n# 正文标题', '正文标题'),
    ('一级标题\n=======\n', '一级标题'),
    ('# **新品** `SKU` [图片](https://example.com) <b>生成</b>', '新品 SKU 图片 生成'),
    ('## 二级标题\n正文', '旧简称'),
    ('#\n\n# 后续标题', '旧简称'),
    ('```\n# 没有真实标题\n```', '旧简称'),
])
def test_first_markdown_heading_skips_metadata_and_code(body, expected):
    document = '\ufeff---\r\nname: sample\r\n# 元数据注释\r\ndescription: 完整说明\r\n---\r\n' + body
    package = SimpleNamespace(files={'SKILL.md': document.encode('utf-8')})
    assert catalog.package_title(package, '旧简称') == expected


def test_real_install_title_shared_by_management_studio_and_freeze(studio, monkeypatch):
    client, factory, _, task, _, _ = studio
    title = 'OUTON · Wayfair新品整套图片生成'
    description = '读取完整参考素材，生成整套新品图片；适用于实际平台要求。'
    document = f'---\nname: sample\n# 非正文标题\ndescription: {description}\n---\n# {title}'
    item = install_sample(files={'SKILL.md': document.encode()}, display_name='OUTON Wayfair 新品主图')
    root = Path(get_settings().local_skill_root)
    release = json.loads((root / 'current.json').read_bytes())['release']
    manifest_path = root / 'releases' / release / 'manifest.json'
    original = manifest_path.read_bytes()
    manifest_item = json.loads(original)['items'][0]
    expected = dict(item, displayName=title, description=description)

    # First read validates actual installed files and caches derived metadata.
    catalog.verified_release.cache_clear()
    called, verify = [], catalog.verify_package
    def counted(*args, **kwargs):
        called.append(args[1]['name'])
        return verify(*args, **kwargs)
    monkeypatch.setattr(catalog, 'verify_package', counted)
    assert client.get(ROOT + '/management/skills').json()['items'] == [expected]
    assert client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()['skills'] == [expected]
    with factory.begin() as session:
        frozen = freeze_selected(session, item['id'])['skill']
    assert called == ['sample']
    assert frozen['displayName'] == title
    assert frozen['checksum'] == manifest_item['checksum']
    assert frozen['installedRelease'] == release
    assert manifest_path.read_bytes() == original

    # Changing heading bytes after caching must still fail integrity validation.
    skill_path = manifest_path.parent / 'sample/SKILL.md'
    skill_path.write_bytes(skill_path.read_bytes().replace(title.encode(), '篡改名称'.encode()))
    with pytest.raises(HTTPException) as caught:
        catalog.listing()
    assert caught.value.status_code == 503


def test_old_display_snapshot_and_new_release_titles_remain_independent(overseas):
    setup(overseas, ('super_admin',))
    item = install_sample(content='# 原版完整标题', display_name='原版旧简称')
    first = catalog.freeze(item['id'])
    legacy = dict(first, displayName='原版旧简称')
    first_bytes = catalog.frozen_package(legacy).files['SKILL.md']
    install_sample(content='# 新版完整标题', display_name='新版旧简称')
    second = catalog.freeze(item['id'])
    assert first['displayName'] == '原版完整标题'
    assert second['displayName'] == catalog.listing()[0]['displayName'] == '新版完整标题'
    assert first['installedRelease'] != second['installedRelease']
    assert first['checksum'] != second['checksum']
    assert catalog.frozen_package(first).files['SKILL.md'] == first_bytes
    assert catalog.frozen_package(legacy).files['SKILL.md'] == first_bytes
    assert legacy['displayName'] == '原版旧简称'
    assert '新版完整标题' in catalog.frozen_package(second).files['SKILL.md'].decode()


def test_real_old_package_without_heading_retains_manifest_display_name(overseas):
    setup(overseas, ('super_admin',))
    item = install_sample(content='## 仅二级标题\n正文', display_name='历史简称')
    assert catalog.listing() == [item]
    assert catalog.freeze(item['id'])['displayName'] == '历史简称'
