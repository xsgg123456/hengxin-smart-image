"""Classify bounded executor evidence without exposing raw logs to callers."""
from pathlib import Path
from app.execution.diagnostics import _safe_read
from app.execution.event_file import lines
from app.execution.event_json import decode_event

AUTH_STDERR_MARKER = 'stderr-authentication.code'
AUTH_STDERR_CODE = b'authentication_failed\n'

def _tail(path: Path, limit=128 * 1024):
    try:
        return _safe_read(path, limit, tail=True, allow_windows_fallback=True).decode('utf-8', errors='replace')
    except (OSError, ValueError):
        return ''


def authentication_failed(control):
    try:
        if _safe_read(Path(control) / AUTH_STDERR_MARKER, len(AUTH_STDERR_CODE),
                      allow_windows_fallback=True) == AUTH_STDERR_CODE:
            return True
    except (OSError, ValueError):
        pass
    try:
        for line in lines(Path(control) / 'events.jsonl'):
            try:
                event = decode_event(line)
            except (ValueError, RecursionError):
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
    except (OSError, ValueError):
        pass
    return any('codex_login::auth' in line and 'failed to refresh token' in line.lower()
               for line in _tail(Path(control) / 'stderr.log').splitlines())


def execution_error_code(control, receipt):
    # Platform stop reasons outrank earlier transient authentication diagnostics.
    reason = receipt.get('reason')
    if reason in ('timeout', 'output_limit', 'cancelled', 'storage_failed'):
        return reason
    return 'authentication_failed' if authentication_failed(control) else 'execution_failed'
