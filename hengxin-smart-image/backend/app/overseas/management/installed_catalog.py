"""Read the actual overseas immutable installation, never a registration-only row."""
import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from app.core.config import get_business_context, get_settings
from .installed_tree import NAME, digest, read_file, safe_directory, tree, tree_stamp

HASH = re.compile(r'[a-f0-9]{64}')
PRODUCTION_ROOTS = {
    '/var/lib/hengxin-overseas/local-skills',
    '/var/lib/docker/volumes/hengxin-overseas_overseas_local_skills/_data',
}


def identity(name):
    return str(uuid5(NAMESPACE_URL, 'hengxin:overseas:installed-skill:' + name))


def root_config():
    if get_business_context() != 'overseas':
        raise ValueError('Installed Skills require overseas context')
    settings = get_settings()
    root, protected = Path(settings.local_skill_root), settings.app_env == 'production'
    if protected and str(root) not in PRODUCTION_ROOTS:
        raise ValueError('Production Skill root is not an approved overseas volume')
    return root, protected


def release_manifest(root, release, protected=False):
    if not isinstance(release, str) or not HASH.fullmatch(release):
        raise ValueError('Invalid Skill release')
    safe_directory(root / 'releases', protected=protected)
    directory = safe_directory(root / 'releases' / release, protected=protected)
    manifest = json.loads(read_file(directory / 'manifest.json', protected=protected))
    if not isinstance(manifest, dict) or manifest.get('schema') != 1 or digest(manifest) != release:
        raise ValueError('Skill release manifest integrity mismatch')
    items = manifest.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('Skill release manifest is empty')
    names = set()
    for item in items:
        name = item.get('name')
        if (not isinstance(name, str) or not NAME.fullmatch(name) or name in names
                or not isinstance(item.get('displayName'), str) or not item['displayName'].strip()):
            raise ValueError('Invalid or duplicate installed Skill')
        names.add(name)
    if {p.name for p in directory.iterdir()} != names | {'manifest.json'}:
        raise ValueError('Skill release contains unexpected or missing packages')
    return directory, manifest


def verify_package(directory, item, protected=False):
    package, entries = tree(directory / item['name'], protected=protected)
    if (package.name != item['name'] or package.description != item['description']
            or package.checksum != item['checksum'] or entries != item['entries']):
        raise ValueError('Installed Skill integrity mismatch')
    return package


@lru_cache(maxsize=8)
def verified_release(root_value, release, stamp, protected):
    directory, manifest = release_manifest(Path(root_value), release, protected)
    for item in manifest['items']:
        verify_package(directory, item, protected)
    if tree_stamp(directory, protected=protected) != stamp:
        raise ValueError('Skill release changed during verification')
    return manifest['items']


def read_catalog(root, protected=False):
    root = safe_directory(root, protected=protected)
    pointer = root / 'current.json'
    if not pointer.exists():
        # An empty installation is valid; an unindexed directory is not success.
        if any(root.iterdir()):
            raise ValueError('Skill installation has no published catalog')
        return None, []
    current = json.loads(read_file(pointer, protected=protected))
    directory, _ = release_manifest(root, current['release'], protected)
    stamp = tree_stamp(directory, protected=protected)
    return current['release'], verified_release(str(root), current['release'], stamp, protected)


def catalog():
    try:
        root, protected = root_config()
        return read_catalog(root, protected)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(503, '海外 Skill 安装目录读取或完整性校验失败，请联系管理员') from None


def listing():
    _, items = catalog()
    return [dict(id=identity(item['name']), name=item['name'], displayName=item['displayName'],
                 description=item['description']) for item in items]


def freeze(identity_value, legacy_name=None):
    release, items = catalog()
    item = next((row for row in items if identity(row['name']) == str(identity_value)
                 or row['name'] == legacy_name), None)
    if item is None:
        raise HTTPException(422, '所选 Skill 未完整安装或已移出目录，请刷新后重新选择')
    return dict(id=identity(item['name']), name=item['name'], displayName=item['displayName'],
                installedRelease=release, checksum=item['checksum'])


def frozen_package(skill):
    root, protected = root_config()
    safe_directory(root, protected=protected)
    directory, manifest = release_manifest(root, skill['installedRelease'], protected)
    item = next((row for row in manifest['items'] if row['name'] == skill['name']), None)
    if item is None or item['checksum'] != skill['checksum']:
        raise ValueError('Frozen installed Skill does not match release')
    return verify_package(directory, item, protected)
