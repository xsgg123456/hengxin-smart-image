from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.worker import maintenance


def control_for(*, busy=False, missing=False, cancel_ack=True):
    queues = [{'name': 'cli'}]
    def inspect(**kwargs):
        def reply(value):
            return None if missing else {'node': value}
        return SimpleNamespace(active_queues=lambda: reply(list(queues)),
            active=lambda: reply([{'id': 'running'}] if busy else []),
            reserved=lambda: reply([]), scheduled=lambda: reply([]))
    def cancel(*args, **kwargs):
        queues.clear()
        return [{'node': {'ok': 'cancelled'}}] if cancel_ack else None
    return SimpleNamespace(inspect=inspect, cancel_consumer=cancel, add_consumer=Mock())


@pytest.mark.parametrize('busy,db_idle,missing,ack', [
    (True, True, False, True), (False, False, False, True),
    (False, True, True, True), (False, True, False, False),
])
def test_unsafe_restart_refused(monkeypatch, busy, db_idle, missing, ack):
    control = control_for(busy=busy, missing=missing, cancel_ack=ack)
    monkeypatch.setattr(maintenance, 'database_idle', lambda _: db_idle)
    restart = Mock()
    with pytest.raises(RuntimeError):
        maintenance.drain_restart(control, None, 'node', restart)
    restart.assert_not_called()
    if not missing:
        control.add_consumer.assert_called_once()


def test_idle_restart_and_failed_restart_restore(monkeypatch):
    monkeypatch.setattr(maintenance, 'database_idle', lambda _: True)
    for fail in (False, True):
        control = control_for()
        restart = Mock(side_effect=RuntimeError('restart failed') if fail else None)
        if fail:
            with pytest.raises(RuntimeError):
                maintenance.drain_restart(control, None, 'node', restart)
            control.add_consumer.assert_called_once()
        else:
            maintenance.drain_restart(control, None, 'node', restart)
            control.add_consumer.assert_not_called()
        restart.assert_called_once()
