from datetime import timezone

HEARTBEAT_MAX_AGE = 30

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def fresh(heartbeat, now):
    return 0 <= (now - aware(heartbeat.checked_at)).total_seconds() <= HEARTBEAT_MAX_AGE

def number(value):
    return value if type(value) is int and value >= 0 else None

def configured(data):
    values = [data.get(key) for key in ('cli', 'isolation', 'authenticationConfigured')]
    if any(value is False for value in values):
        return False
    return True if all(value is True for value in values) else None
