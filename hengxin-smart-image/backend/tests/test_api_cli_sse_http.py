"""Exercise real HTTP streaming without a model, production DB or external services."""
import socket
import threading
import time
from types import SimpleNamespace
from uuid import UUID

import httpx
import uvicorn

from app.core.config import get_settings
from app.main import app
from app.modules.api_image_edits import conversation, conversation_router
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_image_versions import setup_result, post


def test_live_sse_replay_and_access_revocation(files_env, monkeypatch):
    client, factory, _, identity = files_env
    settings = SimpleNamespace(**get_settings().model_dump())
    settings.enable_codex_executor = True
    monkeypatch.setattr(conversation, 'get_settings', lambda: settings)
    monkeypatch.setattr(conversation_router, 'session_factory', lambda: factory)
    _, _, path = setup_result(client, factory)
    response = post(client, path + '/conversation/turns', {'text': '仅调整目标位置', 'baseVersion': 1})
    assert response.status_code == 202, response.text
    turn_id = UUID(response.json()['turns'][0]['id'])
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        url = f'http://127.0.0.1:{port}' + path + '/conversation/events'
        with httpx.Client(timeout=5, trust_env=False) as http:
            with http.stream('GET', url) as stream:
                assert stream.status_code == 200
                assert stream.headers['x-accel-buffering'] == 'no'
                assert stream.headers['content-type'].startswith('text/event-stream')
                lines = stream.iter_lines()
                assert next(lines) == 'id: 1'
                assert next(lines) == 'event: message'
                assert 'queued' in next(lines)
                assert next(lines) == ''
                assert next(lines) == ': heartbeat'
                assert next(lines) == ''
                # Add a public message after the response has already begun.
                started = time.monotonic()
                with factory.begin() as session:
                    turn = session.get(ConversationTurn, turn_id)
                    channel = session.get(Conversation, turn.conversation_id)
                    conversation.emit(session, channel, turn, 'message', '正在检查目标位置')
                assert next(lines) == 'id: 2'
                assert next(lines) == 'event: message'
                assert '正在检查目标位置' in next(lines)
                assert time.monotonic() - started < 4
            # Disconnect leaves the actual queued turn alone. Header cursor replays only newer IDs.
            with factory() as session:
                assert session.get(ConversationTurn, turn_id).status == 'queued'
            with http.stream('GET', url, headers={'Last-Event-ID': '1'}) as stream:
                lines = stream.iter_lines()
                assert next(lines) == 'id: 2'
                assert next(lines) == 'event: message'
                assert '正在检查目标位置' in next(lines)
                assert next(lines) == ''
                assert next(lines) == ': heartbeat'
                assert next(lines) == ''
                with factory.begin() as session:
                    session.get(UserRecord, identity[0]).status = 'disabled'
                assert next(lines) == 'event: closed'
                assert 'access_changed' in next(lines)
            assert http.get(url).status_code == 403
    finally:
        server.should_exit = True
        thread.join(timeout=7)
        sock.close()
        assert not thread.is_alive()
