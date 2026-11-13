from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.modules.domestic_studio import queries, turn_service
from app.modules.domestic_studio.turn_models import OutputFile, Transcript, Turn
from app.overseas.studio.schemas import Send
from app.resource_models import UserRecord
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def test_workspace_reads_only_owners_messages_with_real_name_and_time(context, database):
    factory, catalog, skill, first, second, channel, other_channel = context
    for model in (Transcript, OutputFile):
        model.__table__.create(database)
    with factory() as session:
        empty = queries.view(session, first, 'camera', catalog=catalog)
        assert empty['fixedSkillReady'] is False and empty['turns'] == []
        assert [row['id'] for row in empty['conversations']] == [str(channel)]
        with pytest.raises(HTTPException) as error:
            queries.view(session, first, 'camera', other_channel, catalog=catalog)
        assert error.value.status_code == 404
    with factory.begin() as session:
        session.get(UserRecord, first).name = '张三'
        bind(session, skill['id'])
        turn_service.send(session, first, 'camera', channel, Send(skillId=skill['id'], text='原始要求'), 'send', catalog)
        turn = session.scalar(select(Turn))
        turn.reply = '真实回复'
        session.get(Job, turn.job_id).status = 'succeeded'
        session.add(Transcript(turn_id=turn.id, item_id='reply', kind='message', text='真实回复', state='completed',
                               created_at=datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)))
    with factory() as session:
        result = queries.view(session, first, 'camera', channel, catalog=catalog)
        assert result['fixedSkillReady'] is True
        assert result['turns'][0]['actor'] == {'id': str(first), 'name': '张三'}
        assert result['turns'][0]['text'] == '原始要求' and result['turns'][0]['reply'] == '真实回复'
        assert result['turns'][0]['replyAt'] == '2026-11-12T09:00:00+00:00'
        assert result['turns'][0]['replyTimeSource'] == 'message'
        assert queries.view(session, second, 'camera', other_channel, catalog=catalog)['turns'] == []
        with pytest.raises(HTTPException) as error:
            queries.transcript(session, second, 'camera', channel, 0)
        assert error.value.status_code == 404
