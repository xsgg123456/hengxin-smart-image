"""Inspect a recoverable local file in bounded memory before storing it."""
from dataclasses import asdict
from types import SimpleNamespace

from app.overseas.studio import context_fs as fs, recovery_listing as listing
from app.overseas.studio.output_files import inspect_stream


def inspect(item, version):
    if item.version != version:
        raise listing.RecoveryError('文件已变化，请刷新列表后重新选择')
    before, size = listing.stamp(item.path)
    if item.snapshot is None and before != version:
        raise listing.RecoveryError('文件已变化，请刷新列表后重新选择')
    if size > listing.MAX_BYTES:
        raise listing.RecoveryError('单个文件不能超过 500 MB')
    with fs.reader(item.path) as stream:
        metadata = inspect_stream(stream, size, item.name)
    after, final_size = listing.stamp(item.path)
    if before != after or final_size != size:
        raise listing.RecoveryError('文件在读取时发生变化，请刷新后重试')
    if item.snapshot is not None:
        snapshot = item.snapshot
        if (metadata.checksum != snapshot['checksum'] or metadata.size_bytes != snapshot['sizeBytes']
                or metadata.name != snapshot['name'] or metadata.content_type != snapshot['contentType']
                or metadata.width != snapshot['width'] or metadata.height != snapshot['height']):
            raise listing.RecoveryError('已冻结文件校验失败，请联系管理员')
    return SimpleNamespace(path=item.path, **asdict(metadata))
