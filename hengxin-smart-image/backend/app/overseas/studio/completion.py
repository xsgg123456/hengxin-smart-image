"""Read Studio CLI completion without treating extension notifications as turns."""
from pathlib import Path

from app.execution.diagnostics import _safe_read
from app.execution.event_json import decode_event
from app.execution.events import EventSummary, MAX_EVENTS_BYTES
from .native_rollout import session as check_session

SUCCESS = (None, 'completed', 'success', 'succeeded')
FAILURE = ('failed', 'aborted', 'cancelled', 'canceled')
TERMINAL_FAILURES = {'turn.failed', 'turn.aborted', 'turn.cancelled', 'turn.canceled',
                     'task.failed', 'task.aborted', 'task.cancelled', 'task.canceled'}


class _Completion:
    def __init__(self, expected):
        self.expected = expected
        self.session = self.turn = None
        self.candidate = self.final = None
        self.completed = False
        self.error = self.diagnostic = self.usage_error = None
        self.usage, self.terminals = {}, set()
        self.generation = 0

    def clear(self):
        self.completed = False
        self.candidate = self.final = None

    def identity(self, event):
        turn = event.get('turn_id')
        if turn is not None:
            if not isinstance(turn, str) or not turn:
                raise ValueError('Invalid CLI turn ID')
            if event['type'] not in ('thread.started', 'turn.started'):
                if self.turn is not None and turn != self.turn:
                    self.error = 'invalid_turn_id'
                elif self.turn is None:
                    self.turn = turn
        thread = event.get('thread_id')
        if thread is not None:
            check_session(thread)
            if ((self.expected is not None and thread != self.expected)
                    or (self.session is not None and thread != self.session)):
                self.error = 'session_mismatch'
        return turn

    def consume(self, event):
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            raise ValueError('Invalid CLI event')
        kind, turn = event['type'], self.identity(event)
        if kind == 'thread.started':
            value = event.get('thread_id')
            check_session(value)
            if not self.error:
                self.session = value
            self.clear()
            self.turn = None
        elif kind == 'turn.started':
            self.generation += 1
            self.turn = turn
            self.clear()
            self.diagnostic = None
        elif kind in ('item.started', 'item.updated', 'item.completed'):
            item = event.get('item')
            if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                raise ValueError('Invalid CLI item')
            if self.completed:
                self.generation += 1
                self.turn = turn
            self.clear()
            if kind == 'item.completed' and item['type'] == 'agent_message':
                text = item.get('text')
                if not isinstance(text, str):
                    raise ValueError('Invalid CLI message')
                self.candidate = text if self.session else None
        elif kind == 'turn.completed':
            self.complete(event, turn)
        elif kind == 'error' or kind in TERMINAL_FAILURES:
            # A diagnostic may be followed by a real successful completion in
            # the same turn. A failure after completion invalidates that success.
            if kind != 'error' or self.completed:
                self.clear()
            self.diagnostic = 'cli_error' if kind == 'error' else 'turn_failed'
        elif (event.get('status') in FAILURE or event.get('error') is not None
              or event.get('failure') is not None):
            self.clear()
            self.diagnostic = 'turn_failed'
        elif kind.startswith(('turn.', 'task.')) and kind.endswith(('.ended', '.finished', '.stopped')):
            # An unknown terminal protocol is not an ignorable progress notice.
            self.clear()
            self.error = 'unknown_terminal_event'
        # Optional fields, delta records and future notifications neither prove
        # completion nor erase the last explicit turn.completed receipt.

    def complete(self, event, turn):
        status = event.get('status')
        if status not in SUCCESS:
            self.clear()
            if status in FAILURE:
                self.diagnostic = 'turn_failed'
            else:
                self.error = 'invalid_completion_status'
            return
        if event.get('error') is not None or event.get('failure') is not None:
            self.clear()
            self.diagnostic = 'turn_failed'
            return
        key = turn or self.turn or ('implicit', self.generation)
        if key in self.terminals:
            return
        self.terminals.add(key)
        self.completed = True
        self.final, self.candidate = self.candidate, None
        self.diagnostic = None
        values = event.get('usage')
        if values is None:
            return
        if not isinstance(values, dict):
            self.usage_error = 'invalid_usage'
            return
        for name, value in values.items():
            if type(value) is int and value >= 0:
                self.usage[name] = self.usage.get(name, 0) + value
            else:
                self.usage_error = 'invalid_usage'

    def summary(self):
        return EventSummary(self.session, self.usage or None, self.completed,
                            self.error or self.diagnostic, self.final, self.usage_error)


def read(path: Path, expected_session: str | None = None) -> EventSummary:
    """Read event evidence; the runner must independently require exit code 0."""
    state = _Completion(expected_session)
    try:
        raw = _safe_read(Path(path), MAX_EVENTS_BYTES, allow_windows_fallback=True)
        for line in raw.decode('utf-8').splitlines():
            if line.strip():
                state.consume(decode_event(line))
    except OSError:
        state.error = 'unreadable_event_stream'
    except (ValueError, UnicodeError, RecursionError):
        state.error = 'invalid_event_stream'
    return state.summary()
