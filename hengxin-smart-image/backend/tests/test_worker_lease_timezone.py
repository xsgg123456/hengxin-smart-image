from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.worker import leases


def test_lease_expiry_converts_aware_database_timezone(monkeypatch):
    now = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(leases, 'utcnow', lambda: now)
    shanghai = timezone(timedelta(hours=8))
    assert not leases.lease_active(SimpleNamespace(lease_until=(now - timedelta(seconds=1)).astimezone(shanghai)))
    assert leases.lease_active(SimpleNamespace(lease_until=(now + timedelta(seconds=1)).astimezone(shanghai)))
    assert not leases.lease_active(SimpleNamespace(lease_until=(now - timedelta(seconds=1)).replace(tzinfo=None)))
    assert not leases.lease_active(SimpleNamespace(lease_until=None))
