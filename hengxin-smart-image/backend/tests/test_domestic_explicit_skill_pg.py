"""Explicit per-turn choices, retries and fail-closed legacy reference protection."""
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.modules.domestic_studio import execution_workspace, queries, skill_references, turn_service
from app.modules.domestic_studio.conversation_models import Conversation
from app.modules.domestic_studio.models import SkillExecutionReference
from app.modules.domestic_studio.skill_state import DomesticSkillState
from app.modules.domestic_studio.turn_models import Turn
from app.overseas.studio.schemas import Send
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_studio_http_pg import client_env
from test_domestic_turns_pg import bind, context, count


@pytest.mark.parametrize('bound', [False, True])
def test_unselected_never_reads_catalog_or_pins_and_retry_keeps_none(context, bound):
    factory, catalog, skill, actor, _, channel, _ = context
    unavailable = SimpleNamespace(freeze=lambda _: pytest.fail('unselected must not read Skill files'))
    body = Send(text='继续修改原图')
    with factory.begin() as session:
        if bound:
            bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, body, 'none', unavailable)
        bind(session, None if bound else skill['id'])
        turn_service.send(session, actor, 'camera', channel, body, 'none', unavailable)
    with factory() as session:
        turn = session.scalar(select(Turn))
        assert turn.snapshot['skillSelection'] == 'none' and turn.snapshot['skill'] is None
        assert count(session, Turn) == 1 and count(session, SkillExecutionReference) == 0
        assert skill_references.pinned(session, None, {skill['name']}) == (set(), False)


def test_binding_change_and_disable_reject_new_selection_but_original_retry_is_frozen(context):
    factory, catalog, skill, actor, _, channel, _ = context
    body = Send(text='选中调用', skillId=skill['id'])
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, body, 'selected', catalog)
        turn = session.scalar(select(Turn))
        original = turn.snapshot
        session.get(Job, turn.job_id).status = 'succeeded'
        bind(session, str(uuid4()))
    with factory.begin() as session:
        turn_service.send(session, actor, 'camera', channel, body, 'selected', catalog)
        assert session.scalar(select(Turn)).snapshot == original
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, actor, 'camera', channel, body, 'changed', catalog)
    assert error.value.status_code == 409
    with factory.begin() as session:
        bind(session, skill['id'])
        session.get(DomesticSkillState, skill['name']).enabled = False
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, actor, 'camera', channel, body, 'disabled', catalog)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            turn_service.send(session, actor, 'camera', channel, Send(text=body.text), 'selected', catalog)
    assert error.value.status_code == 409
    with factory.begin() as session:
        turn_service.send(session, actor, 'camera', channel, Send(text='取消选择后继续'), 'none', catalog)
    with factory() as session:
        assert count(session, Turn) == 2 and count(session, SkillExecutionReference) == 1


@pytest.mark.parametrize('damage', ['marker', 'skill', 'turn', 'conversation', 'actor', 'job'])
def test_no_pin_requires_trusted_explicit_none_before_execution_or_skill_cleanup(context, tmp_path, damage):
    factory, catalog, skill, actor, other, channel, _ = context
    with factory.begin() as session:
        turn_service.send(session, actor, 'camera', channel, Send(text='普通对话'), 'none', catalog)
        turn = session.scalar(select(Turn))
        payload = dict(turn.snapshot)
        if damage == 'marker':
            payload.pop('skillSelection')
        elif damage == 'skill':
            payload['skill'] = catalog.freeze(skill['id'])
        elif damage == 'turn':
            payload['turnId'] = str(uuid4())
        elif damage == 'conversation':
            payload['conversationId'] = str(uuid4())
        elif damage == 'actor':
            turn.actor_id = other
        else:
            session.get(Job, turn.job_id).value = str(uuid4())
        turn.snapshot, job_id = payload, turn.job_id
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    with pytest.raises(ValueError):
        execution_workspace.prepare(factory, job_id, settings, catalog, Store())
    assert not (tmp_path / 'execution').exists()
    with factory() as session, pytest.raises(HTTPException) as error:
        skill_references.pinned(session, None, {skill['name']})
    assert error.value.status_code == 503


def test_legacy_selected_turn_prepares_but_missing_pin_is_never_treated_as_none(context, tmp_path):
    factory, catalog, skill, actor, _, channel, _ = context
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='旧请求', skillId=skill['id']), 'old', catalog)
        turn = session.scalar(select(Turn))
        turn.snapshot = {key: value for key, value in turn.snapshot.items() if key != 'skillSelection'}
        job_id = turn.job_id
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    workspace, _ = execution_workspace.prepare(factory, job_id, settings, catalog, Store())
    assert workspace.use_skill
    with factory.begin() as session:
        session.delete(session.get(SkillExecutionReference, job_id))
    with pytest.raises(ValueError):
        execution_workspace.prepare(factory, job_id, settings, catalog, Store())
    with factory() as session, pytest.raises(HTTPException) as error:
        skill_references.pinned(session, None, {skill['name']})
    assert error.value.status_code == 503


def test_skill_to_none_resumes_same_session_preserves_work_and_skips_materialization(context, tmp_path, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), codex_auth_file=None)
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='生成', skillId=skill['id']), 'first', catalog)
        first = session.scalar(select(Turn))
        job_id = first.job_id
    workspace, _ = execution_workspace.prepare(factory, job_id, settings, catalog, Store())
    (workspace.work / 'original.png').write_bytes(b'original image')
    sessions = workspace.home / '.codex' / 'sessions'
    sessions.mkdir()
    (sessions / 'rollout-session-original.jsonl').write_text(
        '{"type":"session_meta","payload":{"id":"session-original"}}\n', encoding='utf-8')
    with factory.begin() as session:
        session.get(Job, job_id).status = 'succeeded'
        session.scalar(select(Turn)).dispatched = True
        session.get(Conversation, channel).session_id = 'session-original'
        turn_service.send(session, actor, 'camera', channel, Send(text='只把背景改白'), 'second', catalog)
        second = session.scalar(select(Turn).where(Turn.job_id != job_id))
        second_job = second.job_id
    monkeypatch.setattr(execution_workspace, 'prepare_skill', lambda *args: pytest.fail('must not prepare Skill'))
    resumed, payload = execution_workspace.prepare(factory, second_job, settings, catalog, Store())
    assert resumed.home == workspace.home and resumed.work == workspace.work
    assert resumed.previous_session == 'session-original' and not resumed.use_skill and resumed.local_skill is None
    assert (resumed.work / 'original.png').read_bytes() == b'original image'
    prompt = execution_workspace.prompt(resumed, payload)
    assert '$' + skill['name'] not in prompt and '只把背景改白' in prompt
    assert '不主动重启历史 Skill 流程' in prompt


def test_http_explicit_choice_history_and_catalog_failure_do_not_block_plain_send(client_env, monkeypatch):
    client, factory, skill, _, actor, _, channel, _ = client_env
    root = '/api/v1/domestic-studio/workspaces/camera'
    headers = {'X-HX-Request': '1', 'Idempotency-Key': 'selected'}
    with factory.begin() as session:
        bind(session, skill['id'])
    result = client.post(root + '/turns', headers=headers,
        json={'conversationId': str(channel), 'text': '调用一次', 'skillId': skill['id']})
    assert result.status_code == 200, result.text
    assert result.json()['skills'] == [{**skill, 'enabled': True, 'platforms': []}]
    assert result.json()['turns'][0]['skillName'] == skill['displayName']
    with factory.begin() as session:
        turn = session.get(Turn, UUID(result.json()['turns'][0]['id']))
        session.get(Job, turn.job_id).status = 'succeeded'
    def unavailable(*args):
        raise HTTPException(503, 'Skill 目录损坏')
    monkeypatch.setattr(queries, 'freeze_enabled', unavailable)
    result = client.post(root + '/turns', headers={**headers, 'Idempotency-Key': 'plain'},
        json={'conversationId': str(channel), 'text': '继续调整', 'skillId': None})
    assert result.status_code == 200, result.text
    view = result.json()
    assert view['skills'] == [] and view['fixedSkillReady'] is False
    assert [turn['skillName'] for turn in view['turns']] == [skill['displayName'], None]
    assert view['conversationId'] == str(channel)
