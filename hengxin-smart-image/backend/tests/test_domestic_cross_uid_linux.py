"""Real Linux UID separation plus PostgreSQL disconnect and source cleanup."""
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time

import pytest
from sqlalchemy import text

from app.modules.domestic_studio import conversation_deletion
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Transcript
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux') or os.geteuid() != 0,
                               reason='requires isolated root Linux to create two test UIDs')


def line(process, timeout=15):
    ready, _, _ = select.select([process.stdout], [], [], timeout)
    assert ready, 'test process did not report readiness'
    return process.stdout.readline().strip()


def test_api_and_worker_different_uids_fence_late_write_after_pg_disconnect(context, database, monkeypatch):
    factory, _, _, actor, _, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    schema = database.get_execution_options()['schema_translate_map'][None]
    url = os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL']
    helper = str(Path(__file__).with_name('domestic_cross_uid_helper.py'))
    group = 4242
    with tempfile.TemporaryDirectory(prefix='hx-crossuid-', dir='/tmp') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        for name in ('locks', 'objects', 'execution'):
            directory = root / name
            directory.mkdir()
            os.chown(directory, 0, group)
            directory.chmod(0o2770)
        env = dict(os.environ, DOMESTIC_STUDIO_LOCK_ROOT=str(root / 'locks'))
        def identity(uid):
            def drop():
                os.setgroups([group])
                os.setgid(group)
                os.setuid(uid)
            return drop
        def start(mode, uid):
            return subprocess.Popen([sys.executable, helper, mode, url, schema, str(actor), str(channel), str(root)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                preexec_fn=identity(uid))
        uploader = start('upload', 10001)
        cleaner = None
        try:
            message = line(uploader)
            assert message.startswith('PUT_WAIT '), (message, uploader.stderr.read() if uploader.poll() is not None else '')
            pid = int(message.split()[1])
            with factory.begin() as session:
                assert session.scalar(text('select pg_terminate_backend(:pid)'), {'pid': pid})
            with factory.begin() as session:
                version = session.get(Conversation, channel).version
                conversation_deletion.request(session, actor, 'camera', channel, version)
            cleaner = start('cleanup', 1001)
            assert line(cleaner) == 'CLEANUP_WAIT'
            time.sleep(.4)
            assert cleaner.poll() is None, 'native cleanup must wait for the API file operation'
            uploader.stdin.write('\n'); uploader.stdin.flush()
            stdout, stderr = uploader.communicate(timeout=20)
            assert uploader.returncode == 0 and 'UPLOAD_FAILED' in stdout, (stdout, stderr)
            stdout, stderr = cleaner.communicate(timeout=20)
            assert cleaner.returncode == 0 and 'CLEANUP_RESULT True' in stdout, (stdout, stderr)
            with factory() as session:
                assert session.get(ConversationDeletion, channel).status == 'deleted'
                assert session.get(Conversation, channel) is None
            assert not [path for path in (root / 'objects').rglob('*') if path.is_file()]
        finally:
            for process in (uploader, cleaner):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
