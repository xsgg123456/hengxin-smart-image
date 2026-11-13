import json
from types import SimpleNamespace

from sqlalchemy import select

from app.capacity.models import CapacityGate, CapacityReservation
from app.modules.domestic_studio import runtime, turn_service
from app.modules.domestic_studio.transcript import Monitor
from app.modules.domestic_studio.turn_models import Transcript, Turn
from app.overseas.studio.schemas import Send
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def test_real_public_stream_is_conversation_scoped_and_fenced(context, database, tmp_path, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    for model in (CapacityGate, CapacityReservation, Transcript):
        model.__table__.create(database)
    monkeypatch.setattr(runtime, 'get_settings', lambda: SimpleNamespace(generation_concurrency=1, job_lease_seconds=30))
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='用户要求'), 'send', catalog)
        job_id = session.scalar(select(Turn.job_id))
    token = runtime.claim(factory, job_id)
    assert token is not None
    events = [dict(type='thread.started', thread_id='real-session-id'),
              dict(type='item.completed', item=dict(id='reply-1', type='agent_message', text='真实回复')),
              dict(type='item.completed', item=dict(id='tool-1', type='command_execution', text='private command'))]
    path = tmp_path / 'events.jsonl'
    path.write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in events) + '\n', encoding='utf-8')
    monitor = Monitor(factory, job_id, token, tmp_path)
    assert not monitor.poll(final=True)
    with factory() as session:
        turn = session.scalar(select(Turn))
        entries = list(session.scalars(select(Transcript).order_by(Transcript.id)))
        assert turn.reply == '真实回复' and turn.event_session_id == 'real-session-id'
        assert [(row.kind, row.text) for row in entries] == [('message', '真实回复'), ('tool', '命令执行')]
    path.write_text('', encoding='utf-8')
    assert monitor.poll(final=True)
    with factory() as session:
        assert session.scalar(select(Turn)).event_invalid is True
