"""Persist only the CLI's public stream, with durable byte cursors and ownership."""
import json
import os
import re
from uuid import UUID
from sqlalchemy import select
from app.overseas.execution import claims
from .models import Conversation, Turn, Transcript

TOOLS = {'command_execution': '命令执行', 'file_change': '文件修改',
         'mcp_tool_call': 'MCP工具调用', 'web_search': '网页搜索',
         'todo_list': '任务清单', 'image_generation': '图片生成'}


def public_item(event, offset):
    event_type = event.get('type')
    if event_type in ('turn.failed', 'error'):
        return f'notice:{offset}', 'notice', '执行发生错误', 'failed'
    if event_type not in ('item.started', 'item.updated', 'item.completed'):
        return None
    item = event.get('item')
    if not isinstance(item, dict):
        return None
    kind = item.get('type')
    identity = item.get('id')
    if not isinstance(identity, str) or not identity:
        identity = f'event:{offset}'
    state = 'completed' if event_type == 'item.completed' else 'running'
    if item.get('status') == 'failed':
        state = 'failed'
    if kind in ('agent_message', 'reasoning'):
        # SDK reasoning.text is a public summary, never session reasoning tokens.
        text = item.get('text')
        if isinstance(text, str):
            return identity, 'message' if kind == 'agent_message' else 'reasoning', text, state
    if kind in TOOLS:
        return identity, 'tool', TOOLS[kind], state
    return None


def append(session, turn, value):
    identity, kind, text, state = value
    last = session.scalar(select(Transcript).where(Transcript.turn_id == turn.id,
        Transcript.item_id == identity).order_by(Transcript.id.desc()).limit(1))
    if last and (last.kind, last.text, last.state) == (kind, text, state):
        return
    session.add(Transcript(task_id=turn.task_id, turn_id=turn.id, item_id=identity,
        kind=kind, text=text, state=state))
    if kind == 'message':
        turn.reply = text
    session.flush()


def consume(session, turn, channel, stream, final):
    stream.seek(0, os.SEEK_END)
    if stream.tell() < turn.event_offset:
        turn.event_invalid = True
        return
    stream.seek(turn.event_offset)
    while not turn.event_invalid:
        offset = stream.tell()
        raw = stream.readline()
        if not raw or (not raw.endswith(b'\n') and not final):
            break
        if not raw.strip():
            turn.event_offset = stream.tell()
            continue
        try:
            event = json.loads(raw)
            if not isinstance(event, dict):
                raise ValueError('Invalid public event')
        except (ValueError, UnicodeError):
            turn.event_invalid = True
            break
        turn.event_offset = stream.tell()
        if event.get('type') == 'thread.started':
            identity = event.get('thread_id')
            if (not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identity)
                    or (channel.session_id and channel.session_id != identity)
                    or (turn.event_session_id and turn.event_session_id != identity)):
                turn.event_invalid = True
                break
            channel.session_id = turn.event_session_id = identity
        elif turn.event_session_id:
            value = public_item(event, offset)
            if value:
                append(session, turn, value)


def poll(factory, job, token, workspace, final=False):
    path = workspace.control / 'events.jsonl'
    if not path.exists():
        return
    if path.is_symlink():
        raise ValueError('Invalid public event file')
    with factory.begin() as session:
        current = claims.locked_job(session, job.id)
        if (not current or current.claim_token != token
                or current.status not in ('running', 'collecting', 'cancelling')
                or not claims.lease_active(current)):
            return
        turn = session.get(Turn, UUID(job.payload['turnId']))
        channel = session.get(Conversation, turn.conversation_id)
        if (turn.job_id != current.id or turn.task_id != current.task_id
                or channel.task_id != turn.task_id or str(channel.id) != job.payload['conversationId']):
            raise ValueError('Transcript ownership mismatch')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            consume(session, turn, channel, stream, final)
