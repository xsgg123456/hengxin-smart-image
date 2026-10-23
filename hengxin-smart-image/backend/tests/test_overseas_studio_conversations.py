from uuid import UUID
from pathlib import Path
from sqlalchemy import select, func
from app.core.config import get_settings
from app.overseas.execution import runner
from app.overseas.studio.models import Conversation, Transcript
from app.overseas.tasks.cleanup import cleanup_once
from test_overseas_studio import studio, send, finish
from test_overseas_studio_execution import fake_runtime
from test_overseas_task_deletion import deletion, request, generated, archived
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_overseas_plans import post


def test_new_conversation_preserves_history_and_uses_fresh_cli_home(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    first = send(client, task).json()
    runner.run(factory, first['turns'][0]['jobId'])
    second = post(client, task, '/studio/conversations', {}, 'new')
    assert second.status_code == 200
    data = second.json()
    assert data['conversationId'] != first['conversationId']
    assert data['turns'] == []
    previous = client.get(ROOT + '/tasks/' + task['id'] + '/studio', params={'conversationId': first['conversationId']}).json()
    assert previous['turns'][0]['conversationId'] == first['conversationId']
    assert data['materials'] == first['materials']
    assert post(client, task, '/studio/conversations', {}, 'new').json() == data
    turn = send(client, task, key='second').json()['turns'][-1]
    assert turn['conversationId'] == data['conversationId']
    runner.run(factory, turn['jobId'])
    assert 'resume' not in commands[-1][1]
    assert commands[0][0].home != commands[-1][0].home
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 2


def test_only_first_prompt_has_persona_and_selected_references(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path)
    from app.overseas.studio.execution import HANDLER
    original, prompts = HANDLER.prepare, []
    def prepare(*args):
        prompt = original(*args)
        prompts.append(prompt)
        return prompt
    monkeypatch.setattr(HANDLER, 'prepare', prepare)
    for index in range(2):
        turn = send(client, task, key=str(index), text='  设计产品\n原样文本  ').json()['turns'][-1]
        runner.run(factory, turn['jobId'])
    assert prompts == ['你是设计师的协作助手，按设计师的要求提供帮助。\n\n  设计产品\n原样文本  ',
                       '  设计产品\n原样文本  ']


def test_delete_removes_every_conversation_and_transcript_but_keeps_archive(deletion):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows)
    assert post(client, task, '/studio/conversations', {}, 'new').status_code == 200
    turn = send(client, task, key='next').json()['turns'][-1]
    finish(factory, turn)
    with factory.begin() as session:
        session.add(Transcript(task_id=UUID(task['id']), turn_id=UUID(turn['id']),
            item_id='one', kind='message', text='历史文字', state='completed'))
        identities = list(session.scalars(select(Conversation.id)))
    assert len(identities) == 2
    roots = [Path(get_settings().codex_execution_root) / 'studio' / str(i) for i in identities]
    for path in roots:
        path.mkdir(parents=True)
        (path / 'session.jsonl').write_text('history')
    assert request(client, task).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert all(not path.exists() for path in roots)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Transcript)) == 0
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
    assert client.get(ROOT + '/archives/' + archive['id']).json()['pictureCount'] == 2
