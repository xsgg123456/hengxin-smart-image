"""Freeze only explicitly delivered files, using the shared Studio receipt format."""
import os

from fastapi import HTTPException

from app.overseas.studio import context_fs as fs
from app.overseas.studio import delivery, delivery_snapshot as snapshots
from app.overseas.studio.delivery_snapshot_fs import identity_value, read_manifest, root_path, verify_file
from app.overseas.studio.output_files import inspect_stream


def capture(workspace, summary, identity):
    if not summary.turn_completed or summary.error or not summary.session_id or summary.final_text is None:
        raise ValueError('A verified complete model response is required')
    selection_path = workspace.control / 'delivery-selection.json'
    if selection_path.exists():
        selection = fs.load(selection_path)
    else:
        references, proven, warnings = delivery.enumerate_delivery(workspace, summary)
        selection = dict(references=references, proven=proven, issues=warnings)
        fs.save(selection_path, selection)
    root = workspace.control / 'delivery'
    targets = [row[0] for row in selection['references']]
    issues = list(selection.get('issues', []))
    try:
        manifest = snapshots.begin(root, identity, summary.final_text, summary.session_id, targets)
    except (OSError, ValueError):
        # One interrupted/corrupt frozen file must not hide the other files.
        # Still reject any manifest belonging to a different invocation/reply.
        with fs.lock(root_path(root)):
            manifest = read_manifest(root_path(root))
        if (not manifest or manifest['identity'] != identity_value(identity, summary.session_id)
                or manifest['finalText'] != summary.final_text or manifest['targets'] != targets):
            raise
        issues.append('部分文件副本无法读取，请通过“取回文件”选择尚存原件')
    for item in manifest['items']:
        if item['status'] == 'captured':
            continue
        try:
            logical = next(row[1] for row in selection['references'] if row[0] == item['target'])
            canonical, path = delivery.reference_path(workspace, summary, logical)
            with fs.reader(path) as stream:
                size = os.fstat(stream.fileno()).st_size
                info = inspect_stream(stream, size, path.name)
            if canonical in selection['proven'] and info.checksum != selection['proven'][canonical]:
                raise ValueError('Native image checksum mismatch')
            snapshots.capture_file(root, item['target'], path, info)
        except (HTTPException, OSError, ValueError, StopIteration):
            issues.append('部分文件未能保存，请保留会话并联系管理员处理')
    with fs.lock(root_path(root)):
        manifest = read_manifest(root_path(root))
    if manifest is None:
        raise ValueError('Delivery manifest is missing')
    issues = list(dict.fromkeys(issues))
    def files():
        for item in manifest['items']:
            if item['status'] != 'captured':
                continue
            try:
                yield item['target'], verify_file(root_path(root), item), dict(item)
            except (HTTPException, OSError, ValueError):
                issue = '部分文件副本无法读取，请通过“取回文件”选择尚存原件'
                if issue not in issues:
                    issues.append(issue)
    return manifest, files(), issues
