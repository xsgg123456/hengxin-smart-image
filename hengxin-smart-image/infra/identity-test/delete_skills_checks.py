"""Real deletion HTTP, database, filesystem and MinIO assertions; disposable topology only."""
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker
from phase19_fixtures import domestic_snapshot


def run(h):
    import studio_fixture
    studio_fixture.h = h
    studio_fixture.run()
    from app.core.config import get_settings
    from app.overseas.studio.models import Conversation
    from app.overseas.tasks.cleanup import cleanup_once
    from app.overseas.tasks.cleanup_files import references
    from app.storage.minio_store import get_store
    from minio.error import S3Error
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    store = get_store()
    before_domestic = domestic_snapshot(h)
    with h.ENGINES['overseas'].connect() as connection:
        tasks = connection.execute(text("SELECT id,name FROM overseas_tasks WHERE status='studio' ORDER BY created_at")).all()
    target, other = tasks[:2]
    task_id = str(target.id)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    path = base + '/tasks/' + task_id
    with ExitStack() as stack:
        clients = []
        for name in ('p18-admin', 'p18-designer', 'p18-operator', 'p19-designer2'):
            client = stack.enter_context(h.login(name))
            h.exchange(client, 'overseas')
            clients.append(client)
        admin, designer, operator, stranger = clients
        from installed_skill_checks import run as check_skills
        check_skills(h, admin, designer, base, str(other.id))
        studio = h.expect(designer.get(path + '/studio'), 200).json()
        pictures = [p for turn in studio['turns'] for p in turn['pictures']]
        assert len(pictures) == 3
        selected = pictures[:2]
        expected = [h.expect(designer.get(h.BUSINESS['overseas'][0] + p['url']), 200).content for p in selected]
        h.expect(designer.post(path + '/studio/archive', json={'pictureIds': [p['id'] for p in selected],
            'sku': 'HX-USB-C'}, headers={'Idempotency-Key': str(uuid4())}), 200)
        archive = h.expect(designer.get(base + '/archives'), 200).json()['items'][0]
        archive_path = base + '/archives/' + archive['id']
        independent = h.expect(designer.get(archive_path), 200).json()
        assert len(independent['pictures']) == 2
        h.expect(stranger.get(archive_path), 403)
        with factory() as session:
            owned = list(references(session, target.id))
            conversation = session.scalar(select(Conversation).where(Conversation.task_id == target.id))
            folder = Path(get_settings().codex_execution_root) / 'studio' / str(conversation.id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'task-memory.txt').write_text('task-private disposable memory')
        (folder / 'sessions').mkdir(exist_ok=True)
        (folder / 'sessions/history.jsonl').write_text('{"temporary":true}')
        preserved = Path(get_settings().codex_execution_root) / str(uuid4())
        preserved.mkdir(parents=True)
        (preserved / 'other-task.txt').write_text('keep unrelated workspace')
        detail = h.expect(admin.get(path), 200).json()
        body = {'version': detail['version'], 'confirmationName': target.name}
        for client in (designer, operator, stranger):
            h.expect(client.request('DELETE', path, json=body), 403)
        h.expect(admin.request('DELETE', path, json={**body, 'confirmationName': 'wrong'}), 422)
        h.expect(admin.request('DELETE', path, json={**body, 'version': body['version'] + 1}), 409)
        deleting = h.expect(admin.request('DELETE', path, json=body), 200).json()
        assert deleting['status'] == 'deleting'
        during = h.expect(admin.get(path), 200).json()
        assert during['deletionStatus'] == 'deleting'
        assert set(during['capabilities']) <= {'task.read', 'task.delete'}
        h.expect(designer.post(path + '/studio/turns', json={'text': 'must not be queued'},
            headers={'Idempotency-Key': str(uuid4())}), 409)
        assert cleanup_once(factory, store) == 1
        receipt = h.expect(admin.get(path + '/deletion'), 200).json()
        assert receipt['status'] == 'deleted' and receipt['error'] is None
        h.expect(admin.get(path), 404)
        assert h.expect(admin.request('DELETE', path, json=body), 200).json() == receipt
        assert not folder.exists() and (preserved / 'other-task.txt').exists()
        for row in owned:
            try:
                store.stat(row)
            except S3Error as exc:
                assert exc.code in ('NoSuchKey', 'NoSuchObject')
            else:
                raise AssertionError('Task-owned object remains after successful deletion')
        for client in (designer, operator, admin):
            records = h.expect(client.get(base + '/archives'), 200).json()['items']
            assert any(a['id'] == archive['id'] and a['sourceDeleted'] and a['taskId'] is None for a in records)
            result = h.expect(client.get(archive_path), 200).json()
            actual = [h.expect(client.get(h.BUSINESS['overseas'][0] + p['url']), 200).content for p in result['pictures']]
            assert sorted(map(sha256_hex, actual)) == sorted(map(sha256_hex, expected))
            zipped = h.expect(client.get(archive_path + '/download'), 200)
            with ZipFile(BytesIO(zipped.content)) as package:
                assert sorted(sha256_hex(package.read(name)) for name in package.namelist()) == sorted(map(sha256_hex, expected))
        h.expect(stranger.get(archive_path), 403)
        h.expect(stranger.get(archive_path + '/download'), 403)
        assert h.expect(admin.get(base + '/management/skills'), 200).json()['items']
        h.expect(designer.get(base + '/tasks/' + str(other.id) + '/studio'), 200)
        print('DELETE_SKILLS_FIXTURES ' + json.dumps(dict(deletedTask=task_id, archiveId=archive['id'],
            remainingStudio=str(other.id), modelCalls=0)), flush=True)
    assert domestic_snapshot(h) == before_domestic
    print('PASS super-admin-only DELETE, stale/name checks, new work fenced, independent archive '
          'view/PNG/ZIP bytes and permissions after deletion, owned objects/memory gone, other task/Skills/domestic retained', flush=True)


def sha256_hex(data):
    return sha256(data).hexdigest()
