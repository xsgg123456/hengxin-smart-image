"""Existing conversation recovery must preserve source files and business facts."""
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.execution.workspace import prepare_workspace
from app.overseas.execution.models import Job
from app.overseas.studio.models import Turn
from app.overseas.studio.restore_context import recover
from test_overseas_studio import studio, send, finish
from test_overseas_materials import materials
from test_overseas_tasks import overseas


def legacy(studio, monkeypatch, tmp_path):
    client, factory, actor, task, material, store = studio
    turn = send(client, task, attachmentIds=['task:' + material['id']]).json()['turns'][0]
    finish(factory, turn)
    with factory.begin() as session:
        row = session.get(Turn, UUID(turn['id']))
        row.dispatched = True
        channel = row.conversation_id
    settings = get_settings()
    settings.codex_execution_root = str(tmp_path / 'execution')
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    ws = prepare_workspace(Path(settings.codex_execution_root) / 'studio', channel, turn['id'], auth)
    sessions = ws.home / '.codex/sessions'
    sessions.mkdir()
    (sessions / 'rollout-thread-1.jsonl').write_text('{}')
    (ws.work / 'inputs').mkdir()
    (ws.work / 'inputs/1.csv').write_bytes(b'name,value\nitem,42\n')
    (ws.work / 'research.txt').write_text('old research')
    monkeypatch.setattr('app.overseas.studio.restore_context.get_store', lambda: store)
    return factory, channel, ws, turn, task


def test_inspect_is_readonly_apply_is_pinned_and_repeatable(studio, monkeypatch, tmp_path):
    factory, channel, ws, turn, task = legacy(studio, monkeypatch, tmp_path)
    before = (ws.work / 'research.txt').read_bytes()
    inspected = recover(factory, channel)
    assert inspected['status'] == 'inspected'
    assert not (ws.home.parent / 'persistent').exists()
    with pytest.raises(ValueError, match='digest'):
        recover(factory, channel, apply=True, expected_digest='wrong')
    restored = recover(factory, channel, apply=True, expected_digest=inspected['plan']['digest'])
    assert restored['sessionId'] == 'thread-1'
    persistent = ws.home.parent / 'persistent'
    assert (persistent / 'work/research.txt').read_bytes() == before
    assert (persistent / 'inputs/1.csv').read_bytes() == b'name,value\nitem,42\n'
    assert (ws.work / 'research.txt').read_bytes() == before
    again = recover(factory, channel, apply=True, expected_digest=inspected['plan']['digest'])
    assert again['sessionId'] == restored['sessionId']
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        assert job.status == 'succeeded' and job.execution_count == 1
        assert session.scalar(select(Turn)).reply == '请确认设计方向'


def test_source_change_after_inspection_requires_new_plan(studio, monkeypatch, tmp_path):
    factory, channel, ws, _, _ = legacy(studio, monkeypatch, tmp_path)
    inspected = recover(factory, channel)
    (ws.work / 'research.txt').write_text('changed after inspect')
    with pytest.raises(ValueError, match='digest'):
        recover(factory, channel, apply=True, expected_digest=inspected['plan']['digest'])
    assert not (ws.home.parent / 'persistent').exists()


def test_active_or_uncertain_process_blocks_recovery(studio, monkeypatch, tmp_path):
    factory, channel, ws, turn, _ = legacy(studio, monkeypatch, tmp_path)
    with factory.begin() as session:
        job = session.get(Job, UUID(turn['jobId']))
        job.process_id = 123
        job.process_exited = False
    with pytest.raises(ValueError, match='idle'):
        recover(factory, channel)
    assert not (ws.home.parent / 'persistent').exists()
