"""Offline publication with real DB owners and real private execution history."""
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.execution.workspace import prepare_workspace
from app.overseas.execution import materials, skill_history
from app.overseas.execution.models import Job
from app.overseas.management import installed_catalog
from app.overseas.studio import context_workspace
from app.overseas.studio.models import Conversation, Transcript, Turn
from test_overseas_skill_transfers import (
    DOCUMENT, URL, deletion, install, overseas, transfers, upload,
)
from test_overseas_tasks import add_member, create, payload


@pytest.fixture
def history(transfers, tmp_path, monkeypatch):
    client, factory, actor, store = transfers
    root = tmp_path / 'execution'
    root.mkdir()
    monkeypatch.setattr(get_settings(), 'codex_execution_root', str(root))
    monkeypatch.setattr(materials, 'get_store', lambda: pytest.fail('Offline history must not download'))
    transfer, files = upload(client)
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    frozen = installed_catalog.freeze(item['id'])
    task = create(client, payload(add_member(factory)))
    assert task.status_code == 201, task.text
    return SimpleNamespace(client=client, factory=factory, actor=actor, store=store, root=root,
                           item=item, package=package, frozen=frozen, files=files,
                           task=UUID(task.json()['id']))


def owned_job(h, *, kind='studio', status='succeeded', process_id=None, exited=True):
    conversation, job_id, turn_id = uuid4(), uuid4(), uuid4()
    body = dict(skill=deepcopy(h.frozen), prompt='原始完整上下文', attachments=['kept-attachment'])
    if kind == 'studio':
        body['conversationId'] = str(conversation)
    with h.factory.begin() as session:
        job = Job(id=job_id, task_id=h.task, kind=kind, dedupe_key=str(job_id), payload=body,
                  status=status, process_id=process_id, process_exited=exited)
        session.add(job)
        session.flush()
        if kind == 'studio':
            session.add(Conversation(id=conversation, task_id=h.task, session_id='original-session'))
            session.flush()
            session.add(Turn(id=turn_id, task_id=h.task, conversation_id=conversation,
                             job_id=job_id, actor_id=h.actor, text='原始消息', reply='原始答复',
                             attachment_ids=['kept-attachment'], reference_ids=['kept-picture'],
                             skill_name=h.frozen['name'], event_session_id='original-session'))
            session.flush()
            session.add(Transcript(task_id=h.task, turn_id=turn_id, item_id='original-item',
                                   kind='message', text='完整历史记录', state='completed'))
    owner_id = conversation if kind == 'studio' else job_id
    base = h.root / 'studio' if kind == 'studio' else h.root
    workspace = prepare_workspace(base, owner_id, turn_id, None, copy_auth=False)
    if kind == 'studio':
        context_workspace.prepare(workspace, [], [], lambda _: pytest.fail('No remote calls'))
    return SimpleNamespace(id=job_id, payload=body, conversation=conversation, turn=turn_id,
                           workspace=workspace, owner=workspace.home.parent)


def fingerprint(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('existing_copy', [False, True])
@pytest.mark.parametrize('kind', ['studio', 'analysis'])
def test_delete_preserves_owned_history_and_prepares_original_bytes(history, existing_copy, kind):
    h = history
    job = owned_job(h, kind=kind)
    workspace = job.workspace
    if existing_copy:
        materials.prepare(job, workspace)
    sentinels = [workspace.home / '.codex' / 'session.jsonl', workspace.work / 'user-work.bin',
                 workspace.work / 'reference.png', workspace.work / 'attachment.bin']
    for index, file in enumerate(sentinels):
        file.write_bytes(b'untouched\x00\xff' + bytes([index]))
    before = fingerprint(job.owner)
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 200, result.text
    assert all(fingerprint(job.owner)[name] == value for name, value in before.items())
    assert not (h.store.installed_root / 'packages' / 'folder-test' / h.package['checksum']).exists()
    assert not (h.store.installed_root / 'releases' / h.package['release'] / 'folder-test').exists()
    with pytest.raises((ValueError, OSError)):
        installed_catalog.frozen_package(h.frozen)
    with h.factory() as session:
        assert session.get(Job, job.id).payload == job.payload
        if kind == 'studio':
            assert session.get(Conversation, job.conversation).session_id == 'original-session'
            turn = session.get(Turn, job.turn)
            assert (turn.text, turn.reply, turn.attachment_ids, turn.reference_ids) == (
                '原始消息', '原始答复', ['kept-attachment'], ['kept-picture'])
            assert session.scalar(select(Transcript)).text == '完整历史记录'
    _, item, _ = installed_catalog.frozen_item(h.frozen)
    assert skill_history.find(job.owner, item)[1] == h.files
    # Exercise the real preparation path in another round after central bytes are gone.
    next_round = prepare_workspace(job.owner.parent, job.owner.name, uuid4(), None, copy_auth=False)
    if kind == 'studio':
        context_workspace.prepare(next_round, [], [], lambda _: pytest.fail('No remote calls'))
    materials.prepare(job, next_round)
    assert {p.relative_to(next_round.local_skill).as_posix(): p.read_bytes()
            for p in next_round.local_skill.rglob('*') if p.is_file()} == h.files
    # A separate owner cannot borrow the original conversation's private copy.
    stranger = prepare_workspace(job.owner.parent, uuid4(), uuid4(), None, copy_auth=False)
    if kind == 'studio':
        context_workspace.prepare(stranger, [], [], lambda _: pytest.fail('No remote calls'))
    with pytest.raises((ValueError, OSError)):
        materials.prepare(job, stranger)


@pytest.mark.parametrize('status,pid,exited', [
    ('queued', None, False), ('running', 99, False), ('collecting', 99, False),
    ('uncertain', 99, False), ('cancelling', 99, False), ('succeeded', 99, False),
    ('failed', 99, False), ('cancelled', 99, False),
])
def test_inflight_or_unconfirmed_exit_blocks_delete_without_pointer_change(history, status, pid, exited):
    h = history
    owned_job(h, status=status, process_id=pid, exited=exited)
    before = fingerprint(h.store.installed_root)
    response = deletion(h.client, h.item, h.package)
    assert response.status_code == 409, response.text
    assert fingerprint(h.store.installed_root) == before
    assert installed_catalog.frozen_package(h.frozen).files == h.files
    assert not (h.store.installed_root / '.pending.json').exists()


def test_update_pins_active_original_content_until_terminal_delete(history):
    h = history
    job = owned_job(h, status='running', process_id=99, exited=False)
    second, new_files = upload(h.client, {'SKILL.md': DOCUMENT + b'updated', 'assets/new.bin': b'new'})
    response = install(h.client, second)
    assert response.status_code == 200, response.text
    assert installed_catalog.frozen_package(h.frozen).files == h.files
    current = h.client.get(URL + '/skills').json()['items'][0]
    current_package = h.client.get(URL + '/skills/' + current['id'] + '/package').json()
    assert installed_catalog.frozen_package(installed_catalog.freeze(current['id'])).files == new_files
    assert deletion(h.client, current, current_package).status_code == 409
    with h.factory.begin() as session:
        row = session.get(Job, job.id)
        row.status, row.process_exited = 'succeeded', True
    response = deletion(h.client, current, current_package)
    assert response.status_code == 200, response.text
    materials.prepare(job, job.workspace)
    assert (job.workspace.local_skill / 'SKILL.md').read_bytes() == DOCUMENT


def test_mismatched_conversation_ownership_aborts_before_publication(history):
    h = history
    job = owned_job(h)
    with h.factory.begin() as session:
        row = session.get(Job, job.id)
        row.payload = dict(row.payload, conversationId=str(uuid4()))
    before = fingerprint(h.store.installed_root)
    assert deletion(h.client, h.item, h.package).status_code == 409
    assert fingerprint(h.store.installed_root) == before


def test_corrupt_exact_private_snapshot_blocks_deletion(history):
    h = history
    job = owned_job(h)
    _, item, _ = installed_catalog.frozen_item(h.frozen)
    skill_history.preserve(job.owner, item, h.files.__getitem__)
    target = job.owner / 'skill-history' / item['checksum'] / item['name'] / 'SKILL.md'
    target.write_bytes(b'corrupted history')
    before = fingerprint(h.store.installed_root)
    response = deletion(h.client, h.item, h.package)
    assert response.status_code == 503, response.text
    assert fingerprint(h.store.installed_root) == before
    assert target.read_bytes() == b'corrupted history'


def test_exact_history_hardlink_cannot_preserve_or_delete_central_bytes(history, tmp_path):
    h = history
    job = owned_job(h)
    _, item, _ = installed_catalog.frozen_item(h.frozen)
    skill_history.preserve(job.owner, item, h.files.__getitem__)
    target = job.owner / 'skill-history' / item['checksum'] / item['name'] / 'SKILL.md'
    outside = tmp_path / 'other-owner-skill.md'
    outside.write_bytes(DOCUMENT)
    target.unlink()
    os.link(outside, target)
    before = fingerprint(h.store.installed_root)
    try:
        response = deletion(h.client, h.item, h.package)
        assert response.status_code == 503, response.text
        assert fingerprint(h.store.installed_root) == before
        assert outside.read_bytes() == DOCUMENT
    finally:
        target.unlink()


def test_workspace_cannot_mix_other_owner_round_with_original_home(history):
    h = history
    job = owned_job(h)
    stranger = prepare_workspace(h.root / 'studio', uuid4(), uuid4(), None, copy_auth=False)
    # Syntactically valid UUID paths still require a consistent owning directory.
    forged = SimpleNamespace(home=job.workspace.home, work=stranger.work,
                             control=stranger.control, round_work=stranger.work)
    with pytest.raises(ValueError, match='belong'):
        materials.prepare(job, forged)
