"""Exact owned-object inventory and link-safe, bounded workspace erasure."""
import shutil
import os
import re
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from uuid import UUID
from minio.error import S3Error
from sqlalchemy import select
from app.core.config import get_settings
from app.overseas.archives.models import ArchiveAsset
from app.overseas.materials.models import Material
from app.overseas.pictures.models import Picture, PictureVersion
from app.overseas.studio.models import Upload, Picture as StudioPicture, Conversation
from app.overseas.execution.models import Job
from .models import ExecutionObject


def references(session, task_id):
    rows = []
    for model in (Material, Upload, StudioPicture, ExecutionObject):
        rows.extend(session.scalars(select(model).where(model.task_id == task_id)))
    rows.extend(session.scalars(select(PictureVersion).join(Picture,
        Picture.id == PictureVersion.picture_id).where(Picture.task_id == task_id)))
    return rows


def inventory(session, task_id, store):
    rows = references(session, task_id)
    objects = {(row.bucket, row.object_key) for row in rows}
    # Exact task/job namespaces also include successful storage writes whose SQL
    # transaction failed. Shared directories and unproven historical keys are never scanned.
    protected = set(session.execute(select(ArchiveAsset.bucket, ArchiveAsset.object_key).where(
        ArchiveAsset.object_key.startswith(f'archives/{task_id}/'))))
    prefixes = [f'studio/uploads/{task_id}/', f'studio/pictures/{task_id}/', f'archives/{task_id}/']
    prefixes += [f'pictures/{identity}/' for identity in session.scalars(select(Job.id).where(Job.task_id == task_id))]
    buckets = {get_settings().minio_bucket, *(bucket for bucket, _ in objects), *(bucket for bucket, _ in protected)}
    for bucket in buckets:
        for prefix in prefixes:
            for key in store.keys(bucket, prefix):
                if not key.startswith(prefix):
                    raise ValueError('Storage listing escaped requested namespace')
                if (bucket, key) not in protected:
                    objects.add((bucket, key))
    for bucket, key in objects:
        path = PurePosixPath(key)
        if (not path.parts or path.is_absolute() or '..' in path.parts or '\\' in key
                or ':' in key or path.parts[0] not in ('materials', 'pictures', 'studio', 'archives')):
            raise ValueError('Unsafe storage ownership')
        for model in (Material, Upload, StudioPicture, ExecutionObject):
            if session.scalar(select(model.id).where(model.bucket == bucket, model.object_key == key,
                    model.task_id != task_id).limit(1)):
                raise ValueError('Shared storage ownership')
        if session.scalar(select(PictureVersion.id).join(Picture, Picture.id == PictureVersion.picture_id)
                .where(PictureVersion.bucket == bucket, PictureVersion.object_key == key,
                       Picture.task_id != task_id).limit(1)):
            raise ValueError('Shared picture ownership')
        if session.scalar(select(ArchiveAsset.id).where(ArchiveAsset.bucket == bucket,
                ArchiveAsset.object_key == key).limit(1)):
            raise ValueError('Archive storage must remain independent')
    directories = [str(identity) for identity in session.scalars(select(Job.id).where(
        Job.task_id == task_id, Job.kind != 'studio'))]
    directories += ['studio/' + str(identity) for identity in session.scalars(
        select(Conversation.id).where(Conversation.task_id == task_id))]
    manifest = dict(objects=[dict(bucket=bucket, object_key=key) for bucket, key in sorted(objects)],
        directories=directories, root=str(Path(get_settings().codex_execution_root).absolute()))
    validate_directories(manifest)
    return manifest


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def cli_tool_link(path, workspace):
    # The isolated CLI creates these arg0 shims pointing at its sandbox binary.
    # They may be dangling on the host. rmtree removes the link, never its target.
    parts = path.relative_to(workspace).parts
    return (shutil.rmtree.avoids_symlink_attacks and path.is_symlink()
        and len(parts) == 6 and parts[:4] == ('home', '.codex', 'tmp', 'arg0')
        and re.fullmatch(r'codex-arg0[A-Za-z0-9]+', parts[4]) is not None
        and parts[5] in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox')
        and os.readlink(path) == '/opt/codex' and not path.is_dir())


def validate_directories(manifest):
    root = Path(manifest['root'])
    if root != Path(get_settings().codex_execution_root).absolute():
        raise ValueError('Execution root changed; cleanup requires original worker')
    for parent in [root, *root.parents]:
        if linked(parent):
            raise ValueError('Execution root cannot traverse links')
    targets = []
    for relative in manifest['directories']:
        parts = PurePosixPath(relative).parts
        if len(parts) not in (1, 2) or (len(parts) == 2 and parts[0] != 'studio'):
            raise ValueError('Invalid owned workspace')
        if str(UUID(parts[-1])) != parts[-1]:
            raise ValueError('Invalid owned workspace identity')
        target = root.joinpath(*parts)
        if not target.resolve().is_relative_to(root.resolve()) or target.resolve() == root.resolve():
            raise ValueError('Workspace outside execution root')
        for path in (target.parent, target):
            if linked(path) or (path.is_file() and path.stat().st_nlink != 1):
                raise ValueError('Linked workspace cannot be erased')
        for directory, folders, files in os.walk(target, followlinks=False):
            for name in folders + files:
                path = Path(directory) / name
                if cli_tool_link(path, target):
                    continue
                if linked(path) or (path.is_file() and path.stat().st_nlink != 1):
                    raise ValueError('Linked workspace cannot be erased')
        targets.append(target)
    return targets


def remove_object(store, data):
    row = SimpleNamespace(**data)
    store.remove(row)
    try:
        store.stat(row)
    except S3Error as exc:
        if exc.code not in ('NoSuchKey', 'NoSuchObject'):
            raise
    except (KeyError, FileNotFoundError):
        return  # Isolated local stores have the same absence contract.
    else:
        raise OSError('Object still exists after erasure')


def erase(store, manifest):
    targets = validate_directories(manifest)
    for row in manifest['objects']:
        remove_object(store, row)
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        if target.exists() or linked(target):
            raise OSError('Workspace erasure incomplete')
