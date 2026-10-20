"""Cross-process network admission. Call only while holding the channel row lock."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select

from .config import get_api_settings
from .models import ApiAttempt, ApiItem
from .state import aware


def occupancy(session):
    active = select(ApiAttempt.id).where(ApiAttempt.item_id == ApiItem.id,
        ApiAttempt.state == 'running').exists()
    return session.scalar(select(func.count()).select_from(ApiItem).where(
        or_(ApiItem.state == 'uncertain', active)))


def waiting(session, gate, now):
    settings = get_api_settings()
    if gate.paused:
        return 'channel', None
    if gate.cooldown_until and aware(gate.cooldown_until) > now:
        return 'cooldown', aware(gate.cooldown_until)
    if gate.probe_attempt_id:
        return 'probe_wait', now + timedelta(seconds=5)
    if occupancy(session) >= settings.max_inflight:
        return 'capacity_wait', now + timedelta(seconds=5)
    # Old unknown calls still consume the global budget, but cannot deadlock a
    # later recovery generation that has spare global capacity.
    current = session.scalar(select(func.count()).select_from(ApiAttempt).where(
        ApiAttempt.state == 'running', ApiAttempt.gate_generation == gate.generation))
    if gate.recovering and current >= gate.recovery_limit:
        return 'capacity_wait', now + timedelta(seconds=5)
    if gate.next_send_at and aware(gate.next_send_at) > now:
        return 'rate_wait', aware(gate.next_send_at)
    return None, None


def granted(gate, attempt, now):
    attempt.gate_generation = gate.generation
    attempt.is_probe = bool(gate.cooldown_until)
    if attempt.is_probe:
        gate.probe_attempt_id = attempt.id
    gate.next_send_at = now + timedelta(seconds=get_api_settings().send_interval_seconds)


def cool(gate, now, retry_after=None):
    deadline = now + timedelta(seconds=max(get_api_settings().cooldown_seconds, retry_after or 0))
    gate.cooldown_until = max(aware(gate.cooldown_until) or deadline, deadline)
    gate.generation += 1
    gate.probe_attempt_id = None
    gate.recovering, gate.recovery_limit = True, 1


def block_unrepresentable_wait(gate):
    # Never turn an oversized Retry-After into an earlier send, including resume.
    gate.cooldown_until = datetime.max.replace(tzinfo=timezone.utc)
    gate.generation += 1
    gate.probe_attempt_id = None
    gate.recovering, gate.recovery_limit = True, 1


def outcome(gate, attempt, kind, now, retry_after=None):
    if attempt is None:
        return  # Input/preflight errors have not reached the upstream service.
    current = attempt.gate_generation == gate.generation
    probe = gate.probe_attempt_id == attempt.id
    if kind == 'uncertain':
        if probe:
            cool(gate, now)  # Keep its budget; another image may probe next generation.
        return
    if kind == 'retryable':
        if current:
            gate.failure_streak += 1
        if probe or (current and gate.failure_streak >= get_api_settings().failure_threshold):
            cool(gate, now, retry_after)
        elif retry_after:
            # Retry-After is a channel-wide minimum, including late old responses.
            cool(gate, now, retry_after)
        return
    if not current:
        return  # A late old success cannot reopen a newer cooling generation.
    if probe:
        gate.probe_attempt_id = None
    if kind == 'succeeded':
        gate.failure_streak = 0
        if probe:
            gate.cooldown_until = None
            gate.recovering, gate.recovery_limit = True, 1
        elif gate.recovering and gate.cooldown_until is None:
            gate.recovery_limit = min(get_api_settings().max_inflight, gate.recovery_limit + 1)
            gate.recovering = gate.recovery_limit < get_api_settings().max_inflight
    elif probe:
        cool(gate, now)
