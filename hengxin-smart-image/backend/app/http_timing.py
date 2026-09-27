"""Request-local, pre-response timing. Never capture SQL text, parameters or URLs."""
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.datastructures import MutableHeaders


@dataclass
class RequestWork:
    statements: int = 0
    collecting: bool = True


_work: ContextVar[RequestWork | None] = ContextVar('http_request_work', default=None)


@event.listens_for(Engine, 'before_cursor_execute')
def count_statement(connection, cursor, statement, parameters, context, executemany):
    work = _work.get()
    if work is not None and work.collecting:
        work.statements += 1


class HttpTimingMiddleware:
    """app = ASGI entry to headers; sql = statements before headers, not DB time.

    The mutable request-local object is shared with FastAPI's worker threads, but
    never with another request. No response body is buffered or inspected.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        work = RequestWork()
        token = _work.set(work)
        started = perf_counter()

        async def measured_send(message):
            if message['type'] == 'http.response.start':
                work.collecting = False
                elapsed_ms = (perf_counter() - started) * 1000
                headers = MutableHeaders(scope=message)
                headers.append('Server-Timing',
                               f'app;dur={elapsed_ms:.2f}, sql;desc="{work.statements}"')
            await send(message)

        try:
            await self.app(scope, receive, measured_send)
        finally:
            work.collecting = False
            _work.reset(token)
