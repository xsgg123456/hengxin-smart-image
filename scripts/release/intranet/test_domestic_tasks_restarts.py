"""Real scoped start dispatch and restart-policy failure injection (no Docker)."""
import copy
import json
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest

import domestic_tasks_engine as tasks
import engine
from scope_actions import Actions
import scopes
import snapshot
import test_engine


@contextmanager
def scoped_start(u, live, compose):
    original = {'app_command': lambda action, names, candidate=False: compose(action, *names),
                'remove_stop_overrides': Mock()}
    actions = Actions(u, 'domestic', 'full', original, {}, u.RELEASE)
    actions.health = Mock()
    with scopes.replace(u, NATIVE={}, APPS=('domestic-api', 'domestic-ui'),
                        ENTRIES=('domestic-api', 'domestic-ui'), containers=lambda: live,
                        compose=compose, start_apps=actions.start_apps, app_command=actions.app_command):
        yield


class RestartTests(test_engine.EngineTests):
    def setUp(self):
        super().setUp()
        services = {'domestic-api': {'restart': 'on-failure:7'},
                    'domestic-ui': {'restart': 'unless-stopped'}}
        self.old = json.dumps({'services': services}).encode()
        self.new = json.dumps({'services': services, 'candidate': True}).encode()
        self.compose.write_bytes(self.old)
        (self.work / 'backup-0').write_bytes(self.old)
        (self.work / 'compose.candidate.json').write_bytes(self.new)
        self.baseline['configs'][0]['sha256'] = snapshot.sha(self.old)
        self.baseline['candidate'] = snapshot.sha(self.new)
        engine._save('prepared.json', self.baseline)
        self.live = {n: {'Id': n, 'State': {'Running': True}, 'HostConfig': {'RestartPolicy': p}}
                     for n, p in {'domestic-api': {'Name': 'on-failure', 'MaximumRetryCount': 7},
                                  'domestic-ui': {'Name': 'unless-stopped', 'MaximumRetryCount': 0}}.items()}
        self.calls, self.bad = [], False

    def compose_action(self, action, *args):
        self.calls.append((action, args))
        if action == 'up' and '--force-recreate' in args and not self.bad:
            for name, policy in tasks.restart_policies(engine.u).items():
                if name in args:
                    self.live[name]['HostConfig']['RestartPolicy'] = policy

    def freeze(self, u):
        (self.work / 'tasks-restarts.json').write_text('{}')
        for row in self.live.values():
            row['HostConfig']['RestartPolicy'] = {'Name': 'no', 'MaximumRetryCount': 0}

    @contextmanager
    def scenario(self, commit=True):
        before = {'schema': {'domestic': '0043', 'overseas': '0026'}}
        schema = copy.deepcopy(before['schema'])
        def migrate(*args):
            if not commit:
                raise RuntimeError('precommit failure')
            schema['domestic'] = '0044'
        with scoped_start(engine.u, self.live, self.compose_action), \
             patch.object(tasks, 'freeze', side_effect=self.freeze), \
             patch.object(tasks, 'migrate', side_effect=migrate), \
             patch.object(tasks.fence, 'assert_held'), \
             patch.object(snapshot, 'schemas', side_effect=lambda _: schema.copy()), \
             patch.object(engine, '_quiesce'), tasks.context({'before': before}, 99):
            yield before

    def test_restart_restored_through_actual_scoped_start_after_precommit_failure(self):
        with self.scenario(commit=False):
            with pytest.raises(RuntimeError, match='precommit failure'):
                engine.apply()
            tasks.check_restarts(engine.u)
        assert self.compose.read_bytes() == self.old
        assert (self.work / 'rolled-back.json').exists()
        assert all('--force-recreate' in args for action, args in self.calls if action == 'up')

    def test_restart_verified_for_candidate_and_applied_retry(self):
        with self.scenario():
            assert engine.apply() == 'applied'
            tasks.check_restarts(engine.u)
            self.live['domestic-api']['HostConfig']['RestartPolicy']['MaximumRetryCount'] = 8
            with pytest.raises(RuntimeError, match='restart policy'):
                engine.apply()

    def test_failed_policy_restore_never_marks_rollback_success(self):
        self.bad = True
        with self.scenario(commit=False):
            with pytest.raises(RuntimeError, match='RECOVERY_UNCONFIRMED'):
                engine.apply()
        assert not (self.work / 'rolled-back.json').exists()

    def test_failed_candidate_policy_keeps_forward_recovery_required(self):
        self.bad = True
        with self.scenario():
            with pytest.raises(RuntimeError, match='RECOVERY_UNCONFIRMED'):
                engine.apply()
        assert self.compose.read_bytes() == self.new
        assert not (self.work / 'applied.json').exists()
        assert not (self.work / 'rolled-back.json').exists()


def test_freeze_captures_exact_policy_before_any_update(tmp_path):
    from types import SimpleNamespace
    names = ('domestic-api', 'domestic-ui')
    compose = tmp_path / 'compose.json'
    compose.write_text(json.dumps({'services': {names[0]: {'restart': 'on-failure:7'},
                                               names[1]: {'restart': 'unless-stopped'}}}))
    live = {n: {'Id': n, 'HostConfig': {'RestartPolicy': p}} for n, p in zip(names, (
        {'Name': 'on-failure', 'MaximumRetryCount': 7}, {'Name': 'unless-stopped', 'MaximumRetryCount': 0}))}
    run = Mock()
    u = SimpleNamespace(APPS=names, WORK=tmp_path, COMPOSE=compose, containers=lambda: live,
                        write=lambda p, data, **kw: p.write_bytes(data), run=run)
    tasks.freeze(u)
    assert json.loads((tmp_path / 'tasks-restarts.json').read_bytes()) == {
        n: {'id': n, 'policy': row['HostConfig']['RestartPolicy']} for n, row in live.items()}
    assert [call.args[0][-1] for call in run.call_args_list] == ['hengxin-lan-' + n for n in names]
