import signal

from app.execution.verified_stop import stopped


def test_only_recorded_worker_and_exact_process_can_be_signalled():
    identity = {'pid': 123, 'boot': 'boot', 'birth': 'birth', 'node': 'worker-a'}
    calls, checks = [], []
    def inspect(*args):
        checks.append(args)
        return len(checks) == 1
    assert not stopped(identity, 'worker-b', inspect=inspect, kill=lambda *args: calls.append(args))
    assert not checks and not calls
    assert stopped(identity, 'worker-a', inspect=inspect, group_alive=lambda *_: False,
                   kill=lambda *args: calls.append(args), sleep=lambda _: None)
    assert all(args == (123, 'boot', 'birth') for args in checks)
    assert calls == [(123, signal.SIGTERM)]
    assert not stopped(identity | {'pid': 1}, 'worker-a', inspect=inspect, kill=lambda *args: calls.append(args))


def test_force_signal_does_not_claim_exit_until_next_verification(monkeypatch):
    monkeypatch.setattr(signal, 'SIGKILL', 9, raising=False)
    identity = {'pid': 123, 'boot': 'boot', 'birth': 'birth', 'node': 'worker-a'}
    calls = []
    assert not stopped(identity, 'worker-a', inspect=lambda *_: True, group_alive=lambda *_: True,
                       kill=lambda *args: calls.append(args), sleep=lambda _: None)
    assert calls == [(123, signal.SIGTERM), (123, signal.SIGKILL)]
    assert stopped(identity, 'worker-a', inspect=lambda *_: False, group_alive=lambda *_: False, kill=lambda *_: None)


def test_dead_leader_with_live_group_is_not_stopped_or_signalled():
    identity = {'pid': 123, 'boot': 'boot', 'birth': 'birth', 'node': 'worker-a'}
    calls = []
    assert not stopped(identity, 'worker-a', inspect=lambda *_: False, group_alive=lambda *_: True,
                       kill=lambda *args: calls.append(args), sleep=lambda _: None)
    assert calls == []


def test_unverifiable_group_is_not_reported_stopped():
    identity = {'pid': 123, 'boot': 'boot', 'birth': 'birth', 'node': 'worker-a'}
    def unavailable(*_):
        raise ValueError('bad group identity')
    assert not stopped(identity, 'worker-a', inspect=lambda *_: False, group_alive=unavailable)
