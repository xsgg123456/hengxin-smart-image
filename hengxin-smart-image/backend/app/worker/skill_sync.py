"""Scan fixed administrator directories and publish lease-fenced object snapshots."""
import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_factory
from app.execution.local_skill_probe import probe_tree
from app.models import Job, utcnow
from app.modules.skills.local_tree import inspect_tree, protected
from app.modules.skills.models import SkillRecord, SkillVersionRecord
from app.modules.skills.package_validator import MAX_FILES, MAX_ZIP, validate_package
from app.storage.minio_store import get_store
from app.worker.leases import claim, finish_job, heartbeat, lease_active


def scan_names(root):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('Skill 发布根目录必须为绝对路径')
    for path in reversed((root, *root.parents)):
        info = path.lstat()
        if path.is_symlink() or not stat.S_ISDIR(info.st_mode):
            raise ValueError('Skill 发布目录不允许链接或非目录路径')
        protected(path, info)
    children = sorted(root.iterdir())
    if len(children) > MAX_FILES:
        raise ValueError('Skill 根目录条目超过限制')
    return [p.name for p in children if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', p.name)]


def snapshot(tree, skill_id, mode):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(tree.files):
            entry = zipfile.ZipInfo(name)
            kind = stat.S_IFDIR if name.endswith('/') else stat.S_IFREG
            entry.external_attr = (kind | tree.permissions.get(name.rstrip('/'), 0o600)) << 16
            archive.writestr(entry, b'' if name.endswith('/') else tree.content[name])
    data = output.getvalue()
    if len(data) > MAX_ZIP:
        raise ValueError('Skill 快照大小超过 20 MiB')
    validate_package(data, mode, None)
    row = SkillVersionRecord(id=uuid4(), skill_id=skill_id, version='0.0.0-' + uuid4().hex,
        source_type='zip', catalog_snapshot=True, status='available', description=tree.description,
        checksum=hashlib.sha256(data).hexdigest(), bucket=get_settings().minio_bucket,
        object_key='skills/snapshots/' + uuid4().hex + '.zip', content_type='application/zip',
        installed_at=utcnow(), installed_path='object-snapshot', node=get_settings().worker_node_name)
    return row, data


def fenced(session, job_id, token):
    job = session.scalar(select(Job).where(Job.id == UUID(str(job_id))).with_for_update())
    return job if job and job.claim_token == token and job.status == 'running' and lease_active(job) else None


def inspect_one(root, name, mode):
    tree = inspect_tree(root, name, mode, None, flat=True)
    if not tree.mode:
        return tree, None
    probe_tree(tree)
    inspect_tree(root, name, mode, None, tree.checksum, flat=True)
    return tree, snapshot(tree, None, tree.mode)


def discard(store, prepared, written):
    if prepared and written:
        try:
            store.remove(prepared[0])
        except Exception:
            pass  # An unreachable object is never published as an executable snapshot.


def sync_one(factory, store, job_id, token, root, name):
    with factory.begin() as session:
        if not fenced(session, job_id, token):
            return False
        records = session.scalars(select(SkillRecord).where(SkillRecord.name == name).with_for_update()).all()
        if len(records) > 1:
            for row in records:
                row.catalog_status, row.catalog_error = 'invalid', '多个历史 Skill 使用同一标识，请先消除冲突'
            return True
        row = records[0] if records else None
        if row is None:
            row = SkillRecord(name=name, mode='', description='', catalog_path=name, catalog_status='syncing')
            session.add(row)
            session.flush()
        else:
            # A historical name/version publication remains compatible until a flat directory appears.
            if not row.catalog_path and not (Path(root) / name).is_symlink() and not (Path(root) / name / 'SKILL.md').exists():
                return True
            if row.catalog_status is None:
                from app.modules.skills.catalog_service import state
                row.manually_disabled = state(session, row) == 'disabled'
            row.catalog_path, row.removed = name, False
            row.catalog_status = 'syncing'
        skill_id, mode = row.id, row.mode or None
        previous = session.get(SkillVersionRecord, row.current_version_id) if row.current_version_id else None
        previous_hash = previous.checksum if previous and previous.catalog_snapshot else None
    tree, prepared, error, written = None, None, None, False
    try:
        tree, prepared = inspect_one(root, name, mode)
        if prepared:
            version, data = prepared
            version.skill_id = skill_id
            if version.checksum != previous_hash:
                written = True
                store.put(version, data)
            else:
                from app.execution.materials import read_object
                read_object(store, previous, MAX_ZIP)
    except ValueError as problem:
        error = str(problem)
    except Exception:
        error = '同步失败，请检查 Skill 文件、快照存储与 Worker 隔离环境'
    if error:
        discard(store, prepared, written)
    with factory.begin() as session:
        if not fenced(session, job_id, token):
            discard(store, prepared, written)
            return False
        row = session.scalar(select(SkillRecord).where(SkillRecord.id == skill_id).with_for_update())
        # A concurrently selected mode must be checked by a subsequent sync, never overwritten.
        if row.mode != (mode or ''):
            discard(store, prepared, written)
            row.catalog_status, row.catalog_error = 'invalid', '处理类型在同步中变化，请重新同步'
            return True
        if tree:
            row.description = tree.description
        row.catalog_error = error
        if error:
            row.catalog_status = 'invalid'
        elif not tree.mode:
            row.catalog_status, row.catalog_error = 'needs_type', '请选择处理类型后同步'
        else:
            row.mode = tree.mode
            previous = session.get(SkillVersionRecord, row.current_version_id) if row.current_version_id else None
            if previous and previous.catalog_snapshot and previous.checksum == version.checksum:
                # ZIP timestamps are fixed by snapshot(), so identical files reuse their snapshot.
                version = previous
            else:
                session.add(version)
                session.flush()
            row.current_version_id = version.id
            row.catalog_status = 'disabled' if row.manually_disabled else 'available'
            version.status = row.catalog_status
        return True


def run_sync(job_id, factory=None, store=None):
    factory, store = factory or session_factory(), store or get_store()
    token = claim(factory, job_id)
    if token is None:
        return
    error = None
    root = get_settings().local_skill_root
    with heartbeat(factory, job_id, token):
        try:
            names = scan_names(root)
            for name in names:
                if not sync_one(factory, store, job_id, token, root, name):
                    return
            with factory.begin() as session:
                if not fenced(session, job_id, token):
                    return
                for row in session.scalars(select(SkillRecord).where(SkillRecord.catalog_path.is_not(None),
                        SkillRecord.removed.is_(False)).with_for_update()).all():
                    if row.catalog_path not in names:
                        row.catalog_status, row.catalog_error = 'invalid', 'Skill 目录缺失'
        except Exception:
            error = '无法扫描 Skill 发布根目录，请检查目录、权限与 Worker 配置'
        with factory.begin() as session:
            job = fenced(session, job_id, token)
            if job:
                if error:
                    for row in session.scalars(select(SkillRecord).where(SkillRecord.catalog_path.is_not(None),
                            SkillRecord.removed.is_(False)).with_for_update()).all():
                        row.catalog_status, row.catalog_error = 'invalid', error
                finish_job(session, job, 'failed' if error else 'succeeded', error)
