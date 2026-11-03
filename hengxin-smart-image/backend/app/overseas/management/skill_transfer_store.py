"""Publisher-owned durable uploads. No caller-provided filesystem destinations."""
import hashlib
import json
import os
import shutil
import tempfile
import posixpath
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import HTTPException
from .installed_catalog import package_title, read_catalog
from .installed_tree import safe_directory, tree, reference_targets


def validate_references(files, entries):
    """Validate actual Markdown links for new uploads, without changing historical readers."""
    known = {path.rstrip('/') for path in entries}
    for filename, relative in reference_targets(files):
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(filename), relative))
        if relative.startswith('/') or '\\' in relative or resolved == '..' or resolved.startswith('../'):
            raise ValueError('Skill reference escapes package: ' + relative)
        if resolved != '.' and resolved not in known:
            raise ValueError('Skill reference is missing: ' + relative)


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_directory(path):
    if os.name == 'posix':
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class TransferStore:
    def __init__(self, path, installed_root, protected=False):
        self.path, self.installed_root, self.protected = Path(path), Path(installed_root), protected
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        safe_directory(self.path, protected=protected)
        if protected:
            self.path.chmod(0o700)

    def directory(self, transfer_id):
        try:
            identity = str(UUID(str(transfer_id)))
        except ValueError:
            raise HTTPException(404, '上传记录不存在') from None
        path = self.path / identity
        if not path.is_dir():
            raise HTTPException(404, '上传记录不存在')
        return safe_directory(path)

    def load(self, transfer_id, actor=None):
        state = json.loads((self.directory(transfer_id) / 'state.json').read_text(encoding='utf-8'))
        if actor is not None and state['actor'] != str(actor):
            raise HTTPException(404, '上传记录不存在')
        return state

    def save(self, state):
        state['updatedAt'] = datetime.now(timezone.utc).isoformat()
        atomic_json(self.directory(state['id']) / 'state.json', state)
        return state

    def create(self, body, actor, key=None):
        value = body.model_dump()
        if key:
            if len(key) > 128:
                raise HTTPException(422, '幂等标识过长')
            for previous in self.list(actor)['items']:
                if previous.get('requestKey') == key:
                    if any(previous[k] != value[k] for k in ('rootName', 'entries')):
                        raise HTTPException(409, '同一幂等标识不能使用不同清单')
                    return previous
        identifier = str(uuid4())
        folder = self.path / identifier
        folder.mkdir(mode=0o700)
        package = folder / 'package'
        package.mkdir()
        for relative, info in value['entries'].items():
            if info.get('directory'):
                (package / relative).mkdir(parents=True, exist_ok=True)
        return self.save(dict(value, id=identifier, actor=str(actor), requestKey=key,
                              status='uploading', received=[]))

    def list(self, actor):
        rows = [self.load(path.name, actor) for path in self.path.iterdir()
                if path.is_dir() and (path / 'state.json').exists()
                and json.loads((path / 'state.json').read_text(encoding='utf-8'))['actor'] == str(actor)]
        return {'items': sorted(rows, key=lambda row: row['updatedAt'], reverse=True)}

    async def upload(self, transfer_id, relative, stream, actor):
        state = self.load(transfer_id, actor)
        if state['status'] in ('installed', 'cancelled'):
            raise HTTPException(409, '上传已完成或取消')
        expected = state['entries'].get(relative)
        if not expected or expected.get('directory'):
            raise HTTPException(422, '文件不在已确认清单中')
        path = self.directory(transfer_id)
        descriptor, temporary = tempfile.mkstemp(prefix='.upload-', dir=path)
        total, checksum = 0, hashlib.sha256()
        try:
            with os.fdopen(descriptor, 'wb') as output:
                async for chunk in stream:
                    total += len(chunk)
                    if total > expected['size']:
                        raise HTTPException(413, '文件超过声明大小')
                    checksum.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if total != expected['size'] or checksum.hexdigest() != expected['sha256']:
                raise HTTPException(422, '文件大小或 SHA-256 与清单不符，请重试')
            os.replace(temporary, path / 'package' / relative)
            sync_directory((path / 'package' / relative).parent)
            if relative not in state['received']:
                state['received'].append(relative)
            state.update(status='uploading', error=None)
            return self.save(state)
        except BaseException:
            state.update(status='failed', error='文件传输未完成或校验失败，可重新上传')
            self.save(state)
            raise
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def validate(self, transfer_id, actor):
        state = self.load(transfer_id, actor)
        if state['status'] == 'cancelled':
            raise HTTPException(409, '上传已取消')
        if state['status'] == 'installed':
            return state
        try:
            package, entries = tree(self.directory(transfer_id) / 'package')
            if entries != state['entries']:
                raise ValueError('上传目录与完整清单不一致，请补传失败的文件')
            validate_references(package.files, entries)
            release, items = read_catalog(self.installed_root, self.protected)
            before = next((item for item in items if item['name'] == package.name), None)
            old = before['entries'] if before else {}
            state.update(status='validated', error=None, baseRelease=release,
                package=dict(name=package.name, displayName=package_title(package, package.name),
                             description=package.description, checksum=package.checksum),
                change='identical' if before and before['checksum'] == package.checksum else
                       'update' if before else 'create',
                diff=dict(added=sorted(entries.keys() - old.keys()), removed=sorted(old.keys() - entries.keys()),
                          modified=sorted(key for key in entries.keys() & old.keys() if entries[key] != old[key])))
            return self.save(state)
        except (ValueError, OSError, UnicodeError) as error:
            state.update(status='failed', error=str(error))
            # A corrupt/missing staged file must be retransmitted, even after a restart.
            state['received'] = []
            self.save(state)
            raise HTTPException(422, 'Skill 校验失败：' + str(error)) from None

    def cancel(self, transfer_id, actor):
        state = self.load(transfer_id, actor)
        if state['status'] == 'installed':
            raise HTTPException(409, '已安装的记录不能取消')
        state['status'] = 'cancelled'
        self.save(state)
        package = self.directory(transfer_id) / 'package'
        if package.exists():
            shutil.rmtree(package)
        return state
