"""Read domestic Skill packages using the overseas integrity implementation.

The root is supplied by the domestic deployment, never the overseas root. The
publisher and execution integration are separate tasks; this module only reads.
"""
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_business_context, get_settings
from app.overseas.management.installed_catalog import (
    identity, package_directory, read_catalog, release_manifest, safe_directory, verify_package,
)
from . import protected as protection


DOMESTIC_ROOT = Path('/var/lib/hengxin-domestic/local-skills')
OVERSEAS_ROOT = Path('/var/lib/hengxin-overseas/local-skills')


class DomesticInstalledSkills:
    identity = staticmethod(identity)
    package_directory = staticmethod(package_directory)
    release_manifest = staticmethod(release_manifest)

    def __init__(self, root: Path, *, protected: bool):
        self.root = Path(root)
        self.protected = protected
        if get_business_context() != 'domestic':
            raise ValueError('Domestic Skills require domestic context')
        if self.root == OVERSEAS_ROOT or self.root.is_relative_to(OVERSEAS_ROOT):
            raise ValueError('Domestic Skills cannot use the overseas root')
        if protection.enabled(get_settings()) and not protected:
            raise ValueError('Production Skill directory must be protected')
        # The two businesses must never publish to or read each other's root.
        if protected and self.root != DOMESTIC_ROOT:
            raise ValueError('Domestic production Skill root is not approved')

    def _catalog(self):
        try:
            return read_catalog(self.root, protected=self.protected)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(503, '国内 Skill 安装目录读取或完整性校验失败，请联系管理员') from None

    def catalog(self):
        return self._catalog()

    def root_config(self):
        return self.root, self.protected

    def list(self):
        _, items = self._catalog()
        return [dict(id=identity(item['name']), name=item['name'],
                     displayName=item['displayName'], description=item['description'])
                for item in items]

    def freeze(self, skill_id: str):
        release, items = self._catalog()
        item = next((row for row in items if identity(row['name']) == skill_id), None)
        if item is None or release is None:
            raise HTTPException(422, '所选 Skill 未完整安装，请刷新后重新选择')
        return dict(id=identity(item['name']), name=item['name'],
                    displayName=item['displayName'], installedRelease=release,
                    checksum=item['checksum'])

    def frozen_package(self, skill: dict):
        try:
            root = safe_directory(self.root, protected=self.protected)
            directory, manifest = release_manifest(root, skill['installedRelease'], self.protected)
            item = next((row for row in manifest['items'] if row['name'] == skill['name']), None)
            if item is None or item['checksum'] != skill['checksum'] or identity(item['name']) != skill['id']:
                raise ValueError('Frozen Skill does not match the installation')
            return verify_package(directory, item, self.protected)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(503, '国内 Skill 文件不可用或完整性校验失败，请联系管理员') from None
