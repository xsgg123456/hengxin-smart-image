"""Interpret one invocation consistently for accounting and final delivery."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.execution.diagnostics import _safe_read, _unique_object

MAX_EVENTS_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class EventSummary:
    session_id: str | None
    usage: dict[str, int] | None
    turn_completed: bool
    error: str | None
    final_text: str | None = None
    usage_error: str | None = None


def parse_events(path: Path, expected_session: str | None = None) -> EventSummary:
    session = None
    usage = {}
    completed = False
    error = diagnostic = usage_error = None
    final_text = candidate = None
    active_turn = None
    generation = 0
    terminals = set()
    try:
        raw = _safe_read(Path(path), MAX_EVENTS_BYTES, allow_windows_fallback=True)
        for line in raw.decode('utf-8').splitlines():
            if not line.strip():
                continue
            event = json.loads(line, object_pairs_hook=_unique_object)
            if not isinstance(event, dict) or not isinstance(event.get('type'), str):
                raise ValueError
            kind = event['type']
            turn_id = event.get('turn_id')
            if turn_id is not None and (not isinstance(turn_id, str) or not turn_id):
                error = error or 'invalid_turn_id'
                continue
            if kind == 'thread.started':
                value = event.get('thread_id')
                if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
                    error = error or 'invalid_session_id'
                elif ((expected_session is not None and value != expected_session)
                      or (session is not None and value != session)):
                    error = error or 'session_mismatch'
                else:
                    session = value
                # A new thread boundary cannot authenticate earlier unowned text.
                candidate = final_text = None
                completed = False
            elif kind == 'error':
                diagnostic = diagnostic or 'cli_error'
            elif kind == 'turn.started' or kind.startswith('item.'):
                if kind.startswith('item.'):
                    item = event.get('item')
                    if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                        raise ValueError
                if kind == 'turn.started' or completed:
                    generation += 1
                    active_turn = turn_id
                elif turn_id is not None and active_turn is not None and turn_id != active_turn:
                    error = error or 'invalid_turn_id'
                completed = False
                candidate = final_text = None
                if kind == 'item.completed':
                    item = event.get('item')
                    if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                        raise ValueError
                    if item['type'] == 'agent_message':
                        text = item.get('text')
                        if not isinstance(text, str):
                            raise ValueError
                        candidate = text if text.strip() and session else None
            elif kind == 'turn.failed':
                completed = False
                candidate = final_text = None
                diagnostic = 'turn_failed'
            elif kind == 'turn.completed':
                if turn_id is not None and active_turn is not None and turn_id != active_turn:
                    error = error or 'invalid_turn_id'
                    continue
                key = turn_id or active_turn or ('implicit', generation)
                if key in terminals:
                    continue
                terminals.add(key)
                completed = True
                final_text = candidate
                candidate = None
                diagnostic = None
                values = event.get('usage')
                if values is not None:
                    if not isinstance(values, dict):
                        usage_error = 'invalid_usage'
                        continue
                    for name, value in values.items():
                        # Preserve independently trustworthy counters; never invent zero.
                        if type(value) is int and value >= 0:
                            usage[name] = usage.get(name, 0) + value
                        else:
                            usage_error = 'invalid_usage'
            else:
                # Unknown substantive events cannot leave an old delivery final.
                completed = False
                candidate = final_text = None
    except OSError:
        error = 'unreadable_event_stream'
    except (ValueError, UnicodeError, RecursionError):
        error = 'invalid_event_stream'
    return EventSummary(session, usage or None, completed, error or (
        diagnostic if not completed else None), final_text, usage_error)
