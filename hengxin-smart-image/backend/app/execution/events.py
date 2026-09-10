"""Parse one invocation's CLI JSONL without trusting model prose or tool claims."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EventSummary:
    session_id: str | None
    usage: dict[str, int] | None
    turn_completed: bool
    error: str | None


def parse_events(path: Path, expected_session: str | None = None) -> EventSummary:
    session = expected_session
    usage = None
    completed = False
    error = None
    terminals = set()
    active_turn = None
    try:
        with Path(path).open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError
                except (ValueError, TypeError):
                    error = 'invalid_event_stream'
                    continue
                kind = event.get('type')
                if kind == 'thread.started':
                    value = event.get('thread_id')
                    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
                        error = 'invalid_session_id'
                    elif session is not None and session != value:
                        error = 'session_mismatch'
                    else:
                        session = value
                elif kind == 'turn.started':
                    active_turn = event.get('turn_id')
                elif kind in ('turn.completed', 'turn.failed'):
                    if kind == 'turn.failed':
                        error = 'turn_failed'
                    turn = event.get('turn_id') or active_turn or '__invocation__'
                    if not isinstance(turn, str):
                        error = 'invalid_turn_id'
                        continue
                    if turn in terminals:
                        continue
                    terminals.add(turn)
                    if kind == 'turn.failed':
                        continue
                    completed = True
                    values = event.get('usage')
                    if values is not None:
                        if not isinstance(values, dict) or any(
                            not isinstance(key, str) or type(value) is not int or value < 0
                            for key, value in values.items()
                        ):
                            error = 'invalid_usage'
                            continue
                        usage = usage or {}
                        for key, value in values.items():
                            usage[key] = usage.get(key, 0) + value
                elif kind == 'error':
                    # Raw upstream errors can contain prompts or credentials.
                    error = 'cli_error'
    except (OSError, UnicodeError):
        error = 'unreadable_event_stream'
    return EventSummary(session, usage, completed, error)
