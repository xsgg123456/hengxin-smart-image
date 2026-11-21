"""Read old and compact event streams independently from the detail log budget."""
import json
import os
from types import SimpleNamespace

import pytest

from app.execution import event_file
from app.execution.events import parse_events
from app.execution.credential_errors import execution_error_code
from app.overseas.studio import completion, transcript


def row(kind, **fields):
    return (json.dumps({'type': kind, **fields}) + '\n').encode()


def test_legacy_rows_past_original_total_limit_and_notice_after_completion(tmp_path):
    path = tmp_path / 'events.jsonl'
    tool = row('item.completed', item={'type': 'command_execution', 'aggregated_output': 'x' * 1024**2})
    final = '![result](/work/result.png)'
    with path.open('wb') as stream:
        stream.write(row('thread.started', thread_id='legacy'))
        for _ in range(65):
            stream.write(tool)
        stream.write(row('item.completed', item={'type': 'agent_message', 'text': final}))
        stream.write(row('turn.completed', usage={'output_tokens': 8}))
        stream.write(row(event_file.COMPACTED))
    for read in (parse_events, completion.read):
        result = read(path, 'legacy')
        assert not result.error and result.turn_completed and result.final_text == final
        assert result.usage == {'output_tokens': 8}


def test_before_thread_notice_is_durable_without_becoming_reply(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_bytes(row(event_file.COMPACTED) + row('thread.started', thread_id='session'))
    turn = SimpleNamespace(event_invalid=False, event_offset=0, event_session_id=None)
    channel = SimpleNamespace(session_id=None)
    saved = []
    with path.open('rb') as stream:
        for _ in range(2):
            transcript.consume(None, turn, channel, stream, final=True,
                               append_entry=lambda _, __, value: saved.append(value))
    assert saved == [('platform:log_compacted', 'notice', event_file.COMPACTED_NOTICE, 'completed')]
    assert turn.event_offset == path.stat().st_size and channel.session_id == 'session'


def test_single_oversize_and_linked_evidence_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / 'events.jsonl'
    path.write_bytes(row('turn.completed'))
    os.link(path, tmp_path / 'also-linked')
    for read in (parse_events, completion.read):
        assert read(path).error == 'invalid_event_stream'
    (tmp_path / 'also-linked').unlink()
    monkeypatch.setattr(event_file, 'MAX_EVENT_LINE', 10)
    for read in (parse_events, completion.read):
        assert read(path).error == 'invalid_event_stream'


def test_early_auth_diagnostic_survives_later_progress_and_storage_error_wins(tmp_path):
    path = tmp_path / 'events.jsonl'
    with path.open('wb') as stream:
        stream.write(row('error', message='401 Unauthorized'))
        stream.write(row('item.updated', item={'type': 'reasoning', 'text': 'z' * 140000}))
    assert execution_error_code(tmp_path, {}) == 'authentication_failed'
    assert execution_error_code(tmp_path, {'reason': 'storage_failed'}) == 'storage_failed'
