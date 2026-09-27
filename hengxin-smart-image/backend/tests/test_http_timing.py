import asyncio
import re

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from starlette.concurrency import run_in_threadpool

from app.http_timing import HttpTimingMiddleware, _work


def sql_count(response):
    return int(re.search(r'sql;desc="(\d+)"', response.headers['server-timing'])[1])


def test_request_queries_include_threadpool_and_remain_isolated():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    app = FastAPI()
    app.add_middleware(HttpTimingMiddleware)

    def query():
        with engine.connect() as connection:
            connection.execute(text('select :secret'), {'secret': 'do-not-log'})

    @app.get('/query/{count}')
    async def queries(count: int):
        for _ in range(count):
            await run_in_threadpool(query)
            await asyncio.sleep(0)
        return {'ok': True}

    @app.get('/denied')
    def denied():
        query()
        raise HTTPException(403, 'forbidden')

    async def check():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            responses = await asyncio.gather(*(client.get(f'/query/{n}') for n in [1, 7, 0, 3]))
            assert [sql_count(response) for response in responses] == [1, 7, 0, 3]
            assert all('do-not-log' not in str(response.headers) for response in responses)
            denied_response = await client.get('/denied')
            assert denied_response.status_code == 403 and sql_count(denied_response) == 1
            assert sql_count(await client.get('/query/0')) == 0
    try:
        asyncio.run(check())
        assert _work.get() is None
    finally:
        engine.dispose()


def test_headers_measure_before_stream_without_buffering(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('app.http_timing.perf_counter', lambda: clock[0])
    messages = []

    async def source(scope, receive, send):
        clock[0] += 0.025
        _work.get().statements = 2
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        assert messages, 'headers must reach downstream before the body exists'
        clock[0] += 60
        await send({'type': 'http.response.body', 'body': b'original', 'more_body': False})

    async def send(message):
        messages.append(message)

    asyncio.run(HttpTimingMiddleware(source)({'type': 'http'}, None, send))
    assert messages[0]['headers'] == [(b'server-timing', b'app;dur=25.00, sql;desc="2"')]
    assert messages[1]['body'] == b'original'
    assert _work.get() is None


def test_error_resets_context_and_non_http_is_untouched():
    async def broken(scope, receive, send):
        assert _work.get() is not None
        raise RuntimeError('injected')

    with pytest.raises(RuntimeError, match='injected'):
        asyncio.run(HttpTimingMiddleware(broken)({'type': 'http'}, None, None))
    assert _work.get() is None

    async def websocket(scope, receive, send):
        assert _work.get() is None
        return 'untouched'

    assert asyncio.run(HttpTimingMiddleware(websocket)({'type': 'websocket'}, None, None)) == 'untouched'
