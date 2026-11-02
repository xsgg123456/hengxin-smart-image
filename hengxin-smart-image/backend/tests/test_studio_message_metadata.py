"""Real HTTP contracts using isolated databases; no paid execution."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import event, select
from app.overseas.auth.models import BusinessSession, Member
from app.overseas.execution.models import Job
from app.overseas.studio.message_metadata import as_utc, reply_time
from app.overseas.studio.models import Transcript, Turn
from test_overseas_tasks import overseas, ROOT, add_member
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish, output
from test_overseas_plans import post

SENT = datetime(2026, 11, 1, 23, 30, 15)
REPLIED = datetime(2026, 11, 2, 0, 1, 2)
COMPLETED = datetime(2026, 11, 2, 0, 2, 3)


def view(client, task):
    response = client.get(f"{ROOT}/tasks/{task['id']}/studio")
    assert response.status_code == 200, response.text
    return response.json()['turns']


def switch_viewer(factory, actor):
    with factory.begin() as session:
        for row in session.scalars(select(BusinessSession)):
            row.user_id = actor


def record(session, turn, text, timestamp=REPLIED, kind='message'):
    row = Transcript(task_id=turn.task_id, turn_id=turn.id,
        item_id=uuid4().hex, kind=kind, text=text, state='completed', created_at=timestamp)
    session.add(row)
    session.flush()
    return row


def prepare(studio, reply, status='succeeded', completed=COMPLETED):
    client, factory, _, task, _, _ = studio
    data = send(client, task).json()['turns'][0]
    with factory.begin() as session:
        turn = session.get(Turn, UUID(data['id']))
        turn.created_at, turn.reply = SENT, reply
        job = session.get(Job, turn.job_id)
        job.status, job.completed_at = status, completed
    return data


def test_http_two_real_senders_current_names_independent_of_viewer(studio):
    client, factory, first_actor, task, _, _ = studio
    first = send(client, task).json()['turns'][0]
    finish(factory, first)
    second_actor = add_member(factory, ('super_admin',), name='第二位发送人')
    switch_viewer(factory, second_actor)
    second = send(client, task, key='second-sender', text='第二人消息').json()['turns'][-1]
    assert second['actor'] == {'id': str(second_actor), 'name': '第二位发送人'}
    viewer = add_member(factory, ('super_admin',), name='仅查看的人')
    switch_viewer(factory, viewer)
    with factory.begin() as session:
        session.get(Member, first_actor).name = '发送人当前姓名'
    rows = view(client, task)
    assert [row['actor'] for row in rows] == [
        {'id': str(first_actor), 'name': '发送人当前姓名'},
        {'id': str(second_actor), 'name': '第二位发送人'}]
    assert [row['text'] for row in rows] == ['设计产品', '第二人消息']
    assert all(datetime.fromisoformat(row['createdAt']).utcoffset() == timedelta(0) for row in rows)


@pytest.mark.parametrize('missing', [False, True])
def test_http_blank_or_missing_historical_sender_has_no_fabricated_name(studio, missing):
    client, factory, actor, task, _, _ = studio
    turn_id = UUID(send(client, task).json()['turns'][0]['id'])
    with factory.begin() as session:
        if missing:
            # SQLite fixture allows a damaged legacy FK; never delete a live member.
            actor = uuid4()
            session.get(Turn, turn_id).actor_id = actor
        else:
            session.get(Member, actor).name = ' \t '
    assert view(client, task)[0]['actor'] == {'id': str(actor), 'name': None}


def test_http_reply_time_is_latest_matching_public_message_not_latest_update(studio):
    client, factory, _, task, _, _ = studio
    data = prepare(studio, '实际答复')
    with factory.begin() as session:
        turn = session.get(Turn, UUID(data['id']))
        record(session, turn, '实际答复', REPLIED - timedelta(seconds=3))
        record(session, turn, '实际答复')
        record(session, turn, '另一个公开消息', REPLIED + timedelta(seconds=1))
        record(session, turn, '实际答复', REPLIED + timedelta(seconds=2), kind='reasoning')
        turn.updated_at = COMPLETED + timedelta(days=7)
        session.get(Job, turn.job_id).updated_at = COMPLETED + timedelta(days=10)
    row = view(client, task)[0]
    assert row['createdAt'] == SENT.isoformat() + '+00:00'
    assert row['replyAt'] == REPLIED.isoformat() + '+00:00'
    assert row['replyTimeSource'] == 'message'


@pytest.mark.parametrize('reply,status,completed,expected', [
    ('历史回复', 'succeeded', COMPLETED, 'completed'),
    ('历史失败消息', 'failed', COMPLETED, 'completed'),
    ('运行中的消息', 'running', None, None),
    ('没有完成时间', 'failed', None, None),
    (None, 'queued', None, None),
    (None, 'succeeded', COMPLETED, None),
    ('', 'failed', COMPLETED, None),
    (' \n ', 'succeeded', COMPLETED, None),
])
def test_http_history_uses_only_real_completion_with_reply(studio, reply, status, completed, expected):
    client, _, _, task, _, _ = studio
    prepare(studio, reply, status, completed)
    row = view(client, task)[0]
    assert row['replyTimeSource'] == expected
    assert row['replyAt'] == (COMPLETED.isoformat() + '+00:00' if expected else None)


@pytest.mark.parametrize('status', ['running', 'failed', 'succeeded'])
@pytest.mark.parametrize('reply', ['公开回复', None, ''])
def test_http_visible_transcript_fallback_and_nonterminal_public_reply(studio, status, reply):
    client, factory, _, task, _, _ = studio
    data = prepare(studio, reply, status, None)
    with factory.begin() as session:
        turn = session.get(Turn, UUID(data['id']))
        record(session, turn, '较早公开回复', REPLIED - timedelta(seconds=1))
        record(session, turn, '公开回复')
    row = view(client, task)[0]
    assert row['reply'] == reply  # Reading metadata never rewrites historical text.
    assert row['replyAt'] == REPLIED.isoformat() + '+00:00'
    assert row['replyTimeSource'] == 'message'


def test_http_archive_and_later_collection_updates_preserve_message_times(studio):
    client, factory, _, task, _, store = studio
    data = send(client, task).json()['turns'][0]
    picture = output(store)
    finish(factory, data, [picture])
    with factory.begin() as session:
        turn = session.get(Turn, UUID(data['id']))
        turn.created_at = SENT
        record(session, turn, turn.reply)
    before = view(client, task)[0]
    result = post(client, task, '/studio/archive', {'pictureIds': [picture['id']], 'sku': 'A'}, 'archive')
    assert result.status_code == 200, result.text
    with factory.begin() as session:
        turn = session.get(Turn, UUID(data['id']))
        turn.updated_at = COMPLETED + timedelta(days=3)
        turn.delivery_error = '后续收取状态'
        session.get(Job, turn.job_id).updated_at = COMPLETED + timedelta(days=5)
    after = view(client, task)[0]
    assert after['pictures'][0]['archived'] is True
    assert (after['createdAt'], after['replyAt'], after['replyTimeSource']) == (
        before['createdAt'], before['replyAt'], before['replyTimeSource'])


def test_timezone_conversion_preserves_aware_instant_and_naive_utc():
    aware = datetime(2026, 11, 2, 8, 1, 2, tzinfo=timezone(timedelta(hours=8)))
    expected = REPLIED.replace(tzinfo=timezone.utc)
    assert as_utc(aware) == as_utc(REPLIED) == expected
    assert as_utc(None) is None
    turn = SimpleNamespace(reply='回复')
    assert reply_time(turn, SimpleNamespace(completed_at=aware), None) == (expected, 'completed')
    assert reply_time(turn, None, SimpleNamespace(created_at=aware)) == (expected, 'message')
    assert reply_time(turn, None, SimpleNamespace(created_at=None)) == (None, None)


def test_http_metadata_reads_are_batched_as_turn_count_grows(studio):
    client, factory, _, task, _, _ = studio
    for index in range(3):
        data = send(client, task, key=f'batch-{index}').json()['turns'][-1]
        finish(factory, data)
    statements = []
    engine = factory.kw['bind']
    def collect(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', collect)
    try:
        assert len(view(client, task)) == 3
    finally:
        event.remove(engine, 'before_cursor_execute', collect)
    assert sum('overseas_studio_transcript' in sql for sql in statements) == 1
    assert sum('SELECT overseas_members.id, overseas_members.name' in sql for sql in statements) == 1
