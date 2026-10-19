"""Classify bounded executor evidence without exposing raw logs to callers."""
import json
from pathlib import Path


def _tail(path: Path, limit=128 * 1024):
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - limit))
            return stream.read(limit).decode('utf-8', errors='replace')
    except OSError:
        return ''


def authentication_failed(control):
    for line in _tail(Path(control) / 'events.jsonl').splitlines():
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        message = event.get('message') if event.get('type') == 'error' else None
        if event.get('type') == 'turn.failed' and isinstance(event.get('error'), dict):
            message = event['error'].get('message')
        if isinstance(message, str) and any(value in message.lower() for value in (
            'workspace routing discovery unauthorized (401)',
            '401 unauthorized', 'refresh_token_reused', 'refresh_token_expired',
            'refresh_token_invalidated', 'authentication token is invalid',
        )):
            return True
    return any('codex_login::auth' in line and 'failed to refresh token' in line.lower()
               for line in _tail(Path(control) / 'stderr.log').splitlines())


def execution_error_code(control, receipt):
    # Platform stop reasons outrank earlier transient authentication diagnostics.
    reason = receipt.get('reason')
    if reason in ('timeout', 'output_limit', 'cancelled'):
        return reason
    return 'authentication_failed' if authentication_failed(control) else 'execution_failed'
