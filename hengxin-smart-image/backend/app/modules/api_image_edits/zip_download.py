"""Download an atomic selection of immutable successful result objects."""
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_STORED, ZipFile

from fastapi import HTTPException
from sqlalchemy import select
from app.modules.files.streaming import OwnedStreamResponse

from .files import find_file, read_bytes
from .models import ApiItem
from .service import find_task
from .state import channel


def download(session, store, task_id):
    channel(session)
    task = find_task(session, task_id, lock=True)
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)
                            .order_by(ApiItem.position).with_for_update()).all()
    if not items or any(i.state != 'succeeded' or not i.result_id for i in items):
        raise HTTPException(409, '全部图片成功后才能下载整套 ZIP')
    records = [find_file(session, item.result_id) for item in items]
    # Release all SQL locks before object I/O. Version references protect these files.
    session.expunge_all()
    session.commit()
    buffer = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with ZipFile(buffer, 'w', compression=ZIP_STORED) as archive:
            for position, record in enumerate(records, 1):
                suffix = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}[record.content_type]
                archive.writestr(f'{position:02d}.{suffix}', read_bytes(store, record))
    except Exception:
        buffer.close()
        raise HTTPException(503, '整套图片暂时无法打包，请重试') from None
    size = buffer.tell()
    buffer.seek(0)
    return OwnedStreamResponse(ZipStream(buffer), media_type='application/zip', headers={
        'Content-Length': str(size),
        'Content-Disposition': f'attachment; filename="api-images-{task_id}.zip"',
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


class ZipStream:
    def __init__(self, buffer):
        self.buffer = buffer

    def stream(self, size):
        while data := self.buffer.read(size):
            yield data

    def close(self):
        self.buffer.close()

    def release_conn(self):
        pass
