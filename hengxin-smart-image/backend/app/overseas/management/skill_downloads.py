"""Download one verified immutable release, never files from a mutable pointer."""
import hashlib
from fastapi import HTTPException
from fastapi.responses import Response
from . import installed_catalog as catalog
from .installed_tree import read_file, safe_directory


def package(skill_id):
    release, items = catalog.catalog()
    item = next((row for row in items if catalog.identity(row['name']) == str(skill_id)), None)
    if item is None:
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    return dict(name=item['name'], displayName=item['displayName'], description=item['description'],
                rootName=item.get('rootName', item['name']), release=release,
                checksum=item['checksum'], entries=item['entries'])


def file(skill_id, release, path):
    try:
        root, protected = catalog.root_config()
        directory, manifest = catalog.release_manifest(root, release, protected)
        item = next((row for row in manifest['items'] if catalog.identity(row['name']) == str(skill_id)), None)
        if not item or path not in item['entries'] or item['entries'][path].get('directory'):
            raise HTTPException(404, '文件不在固定发布版本中')
        # The pinned manifest is content-addressed; verify this file without rereading
        # the whole 256 MiB package once per downloaded resource.
        try:
            package_root = catalog.package_directory(directory, item, protected)
        except FileNotFoundError:
            raise HTTPException(410, '此 Skill 固定版本已回收，无法下载') from None
        source = package_root / path
        safe_directory(source.parent, protected=protected)
        data = read_file(source, protected=protected)
        expected = item['entries'][path]
        if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Downloaded Skill bytes differ from the pinned manifest')
        return Response(data, media_type='application/octet-stream',
                        headers={'ETag': '"' + item['entries'][path]['sha256'] + '"',
                                 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})
    except (ValueError, OSError, KeyError, TypeError):
        raise HTTPException(503, 'Skill 固定版本读取或完整性校验失败') from None
