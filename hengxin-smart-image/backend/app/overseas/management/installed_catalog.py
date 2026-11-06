"""Read the actual overseas immutable installation, never a registration-only row."""
import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from markdown_it import MarkdownIt
from app.core.config import get_business_context, get_settings
from .installed_tree import NAME, digest, read_file, safe_directory, tree, tree_stamp
from .skill_transfer_schema import TransferCreate

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
    if not isinstance(manifest, dict) or manifest.get('schema') not in (1, 2) or digest(manifest) != release:
        raise ValueError('Skill release manifest integrity mismatch')
    items = manifest.get('items')
    if not isinstance(items, list):
        raise ValueError('Invalid Skill release items')
    names = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Invalid installed Skill metadata')
        name = item.get('name')
        if (not isinstance(name, str) or not NAME.fullmatch(name) or name in names
                or not isinstance(item.get('displayName'), str) or not item['displayName'].strip()):
            raise ValueError('Invalid or duplicate installed Skill')
        validate_item(item)
        names.add(name)
    children = {p.name for p in directory.iterdir()}
    allowed = {'manifest.json'} | (names if manifest['schema'] == 1 else set())
    if not children <= allowed:
        raise ValueError('Skill release contains unexpected packages')
    return directory, manifest


def validate_item(item):
    if (not isinstance(item.get('name'), str) or not NAME.fullmatch(item['name'])
            or not isinstance(item.get('checksum'), str) or not HASH.fullmatch(item['checksum'])
            or not isinstance(item.get('description'), str)):
        raise ValueError('Invalid installed Skill metadata')
    TransferCreate(rootName=item['name'], entries=item['entries'])
    if digest(item['entries']) != item['checksum']:
        raise ValueError('Installed Skill manifest checksum mismatch')


def package_directory(directory, item, protected=False):
    """Old releases may retain local trees; schema 2 always uses shared objects."""
    directory = safe_directory(directory, protected=protected)
    validate_item(item)
    manifest_path = directory / 'manifest.json'
    schema = json.loads(read_file(manifest_path, protected=protected))['schema'] if manifest_path.exists() else 1
    legacy = directory / item['name']
    if schema == 1 and (legacy.exists() or legacy.is_symlink()):
        return safe_directory(legacy, protected=protected)
    if schema not in (1, 2) or directory.parent.name != 'releases':
        raise ValueError('Skill package is unavailable in this release')
    root = directory.parent.parent
    for path in (root / 'packages', root / 'packages' / item['name']):
        safe_directory(path, protected=protected)
    return safe_directory(root / 'packages' / item['name'] / item['checksum'], protected=protected)


def verify_package(directory, item, protected=False):
    package, entries = tree(package_directory(directory, item, protected), protected=protected)
    if (package.name != item['name'] or package.description != item['description']
            or package.checksum != item['checksum'] or entries != item['entries']):
        raise ValueError('Installed Skill integrity mismatch')
    return package


def release_stamp(directory, manifest, protected=False):
    def stamp(path):
        info = path.stat()
        identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                    info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        return identity, tree_stamp(path, protected=protected)
    return (stamp(directory), tuple((item['name'], stamp(package_directory(directory, item, protected)))
                                   for item in manifest['items']))


def package_title(package, fallback):
    """Derive presentation from verified bytes, without rewriting release identity."""
    document = package.files['SKILL.md'].decode('utf-8-sig')
    # Use the same frontmatter boundary as package_validator; YAML comments and
    # multiline descriptions must not become headings.
    body = re.sub(r'\A---\s*\r?\n(.*?)\r?\n---(?:\s*\r?\n|$)', '', document, count=1, flags=re.S)
    tokens = MarkdownIt('commonmark').parse(body)
    for index, token in enumerate(tokens):
        if token.type == 'heading_open' and token.tag == 'h1':
            children = tokens[index + 1].children or []
            title = ''.join(' ' if child.type in ('softbreak', 'hardbreak') else child.content
                            for child in children
                            if child.type in ('text', 'code_inline', 'image', 'softbreak', 'hardbreak'))
            return title.strip() or fallback
    return fallback


@lru_cache(maxsize=8)
def verified_release(root_value, release, stamp, protected):
    directory, manifest = release_manifest(Path(root_value), release, protected)
    items = []
    for item in manifest['items']:
        package = verify_package(directory, item, protected)
        items.append(dict(item, displayName=package_title(package, item['displayName']),
                          description=package.description))
    if release_stamp(directory, manifest, protected) != stamp:
        raise ValueError('Skill release changed during verification')
    return items


def read_catalog(root, protected=False, *, allow_pending=False):
    root = safe_directory(root, protected=protected)
    if not allow_pending and (root / '.pending.json').exists():
        raise ValueError('Skill publication is awaiting transaction recovery')
    pointer = root / 'current.json'
    if not pointer.exists():
        # An empty installation is valid; an unindexed directory is not success.
        contents = {path.name for path in root.iterdir()}
        if contents == {'.preparing.json'}:
            from .skill_preparation import load
            load(root, protected)
            return None, []
        if contents:
            raise ValueError('Skill installation has no published catalog')
        return None, []
    current = json.loads(read_file(pointer, protected=protected))
    directory, manifest = release_manifest(root, current['release'], protected)
    stamp = release_stamp(directory, manifest, protected)
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


def frozen_item(skill):
    """Read frozen metadata even after the corresponding central tree was reclaimed."""
    root, protected = root_config()
    safe_directory(root, protected=protected)
    directory, manifest = release_manifest(root, skill['installedRelease'], protected)
    item = next((row for row in manifest['items'] if row['name'] == skill['name']), None)
    if item is None or item['checksum'] != skill['checksum']:
        raise ValueError('Frozen installed Skill does not match release')
    return directory, item, protected


def frozen_package(skill):
    directory, item, protected = frozen_item(skill)
    return verify_package(directory, item, protected)
