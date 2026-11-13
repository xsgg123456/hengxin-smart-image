"""Subprocess helper for the isolated Linux cross-UID deletion regression."""
import os
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.modules.domestic_studio import conversation_cleanup, file_service, maintenance_lock
from app.overseas.tasks import cleanup_files


mode, url, schema, actor, channel, root = sys.argv[1:]
root = Path(root)
os.umask(0o002)
engine = create_engine(url).execution_options(schema_translate_map={None: schema})
factory = sessionmaker(engine, expire_on_commit=False)
settings = SimpleNamespace(app_env='production', minio_bucket='private',
                           codex_execution_root=str(root / 'execution'), worker_node_name='test')
maintenance_lock.PRODUCTION_ROOT = Path(os.environ['DOMESTIC_STUDIO_LOCK_ROOT'])
file_service.get_settings = conversation_cleanup.get_settings = cleanup_files.get_settings = lambda: settings


class Store:
    def path(self, row):
        return root / 'objects' / row.bucket / row.object_key

    def put(self, row, data):
        print('PUT_WAIT ' + str(pid[0]), flush=True)
        sys.stdin.readline()
        path = self.path(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_stream(self, row, stream, size):
        data = stream.read()
        assert len(data) == size
        self.put(row, data)

    def keys(self, bucket, prefix):
        base = root / 'objects' / bucket
        return [p.relative_to(base).as_posix() for p in base.rglob('*')
                if p.is_file() and p.relative_to(base).as_posix().startswith(prefix)] if base.exists() else []

    def remove(self, row):
        self.path(row).unlink(missing_ok=True)

    def stat(self, row):
        return self.path(row).stat().st_size

    def open(self, row):
        class Stream(BytesIO):
            def release_conn(self):
                pass
        return Stream(self.path(row).read_bytes())


pid = []
if mode == 'upload':
    original = file_service.owned
    def owned(session, *args, **kwargs):
        result = original(session, *args, **kwargs)
        if kwargs.get('lock'):
            pid.append(session.scalar(text('select pg_backend_pid()')))
        return result
    file_service.owned = owned
    try:
        file_service.upload(factory, Store(), UUID(actor), 'camera', UUID(channel), b'late-private-bytes', 'late.txt')
    except Exception as error:
        print('UPLOAD_FAILED ' + type(error).__name__, flush=True)
    else:
        raise SystemExit('Disconnected upload unexpectedly committed')
elif mode == 'cleanup':
    print('CLEANUP_WAIT', flush=True)
    print('CLEANUP_RESULT ' + str(conversation_cleanup.process(factory, Store(), UUID(channel))), flush=True)
else:
    raise SystemExit('Unknown isolated helper mode')
