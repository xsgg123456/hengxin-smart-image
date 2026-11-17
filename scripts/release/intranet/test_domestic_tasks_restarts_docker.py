"""Opt-in real Docker Compose regression; no production services or databases.

TEST_TASKS_DOCKER=1 python -m unittest discover -s scripts/release/intranet
  -p test_domestic_tasks_restarts_docker.py -v
The engine journal/config flow and scoped start adapter are real; native services,
health endpoints and schema mutation are simulated. Docker actions are real and
restricted to a unique project with no mounts, ports or persistent volumes.
"""
import copy
import json
import os
import subprocess
import unittest
import uuid
from contextlib import ExitStack
from unittest.mock import Mock, patch

import domestic_tasks_engine as tasks
import engine
from scope_actions import Actions
import scopes
import snapshot
import test_engine


@unittest.skipUnless(os.environ.get('TEST_TASKS_DOCKER') == '1', 'explicit local Docker opt-in required')
class DockerRestartTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_engine.EngineTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.u = engine.u
        self.project = 'hx-tasks-restart-' + uuid.uuid4().hex[:10]
        self.names = ('domestic-api', 'domestic-ui')
        self.others = ('overseas-api', 'shared-ui')
        services = {n: {'image': 'python:3.12.10-slim-bookworm',
                        'container_name': self.project + '-' + n,
                        'command': ['python', '-c', 'import signal,time,sys; '
                                    'signal.signal(signal.SIGTERM, lambda *a: sys.exit(0)); time.sleep(3600)'],
                        'restart': 'on-failure:7' if n == 'domestic-api' else 'unless-stopped'}
                    for n in (*self.names, *self.others)}
        self.old = json.dumps({'services': services}).encode()
        candidate = copy.deepcopy(services)
        candidate['domestic-api']['labels'] = {'test.source': 'candidate'}
        self.new = json.dumps({'services': candidate}).encode()
        f = self.fixture
        f.compose.write_bytes(self.old)
        (f.work / 'backup-0').write_bytes(self.old)
        (f.work / 'compose.candidate.json').write_bytes(self.new)
        f.baseline['configs'][0]['sha256'] = snapshot.sha(self.old)
        f.baseline['candidate'] = snapshot.sha(self.new)
        engine._save('prepared.json', f.baseline)
        self.addCleanup(self.cleanup_docker)
        self.compose('up', '-d', '--pull', 'never')
        self.untouched = self.inspect(self.others)
        self.initial = self.inspect(self.names)
        original = {'app_command': self.app, 'remove_stop_overrides': Mock()}
        actions = Actions(self.u, 'domestic', 'full', original, {}, self.u.RELEASE)
        actions.health = Mock()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(scopes.replace(self.u, NATIVE={}, APPS=self.names, ENTRIES=self.names,
            run=self.docker_run, compose=self.compose, containers=lambda: self.inspect(self.names),
            app_command=actions.app_command, start_apps=actions.start_apps,
            stop_apps=lambda: self.app('stop', self.names)))
        self.stack.enter_context(patch.object(engine, '_quiesce'))
        self.stack.enter_context(patch.object(tasks.fence, 'assert_held'))
        self.before = {'schema': {'domestic': '0043', 'overseas': '0026'}}
        self.schema = self.before['schema'].copy()
        self.stack.enter_context(patch.object(snapshot, 'schemas', side_effect=lambda _: self.schema.copy()))

    def docker_run(self, argv, **kwargs):
        argv = [self.project + arg.removeprefix('hengxin-lan')
                if arg.startswith('hengxin-lan-') else arg for arg in argv]
        return subprocess.run(argv, check=True, capture_output=True, text=True,
                              timeout=180).stdout

    def compose(self, *args, candidate=False, config=None):
        path = config or (self.fixture.work / 'compose.candidate.json' if candidate else self.fixture.compose)
        return self.docker_run(['docker', 'compose', '-p', self.project, '-f', str(path), *args])

    def app(self, action, names, candidate=False):
        args = ('up', '-d', '--no-deps', '--pull', 'never') if action == 'up' else ('stop', '--timeout', '-1')
        return self.compose(*args, *names, candidate=candidate)

    def inspect(self, names):
        return {name: json.loads(self.docker_run(['docker', 'inspect', self.project + '-' + name]))[0]
                for name in names}

    def cleanup_docker(self):
        self.compose('down', '--timeout', '5')
        self.assertEqual(self.docker_run(['docker', 'ps', '-aq', '--filter',
                                  'label=com.docker.compose.project=' + self.project]).strip(), '')
        self.assertEqual(self.docker_run(['docker', 'network', 'ls', '-q', '--filter',
                                  'label=com.docker.compose.project=' + self.project]).strip(), '')

    def assert_restored(self):
        tasks.check_restarts(self.u)
        for name, row in self.inspect(self.names).items():
            self.assertNotEqual(row['Id'], self.initial[name]['Id'])
            self.assertTrue(row['State']['Running'])
        for name, row in self.inspect(self.others).items():
            before = self.untouched[name]
            self.assertEqual((row['Id'], row['State']['StartedAt'], row['HostConfig']['RestartPolicy']),
                             (before['Id'], before['State']['StartedAt'], before['HostConfig']['RestartPolicy']))

    def test_plain_up_reproduces_drift_then_scoped_hook_restores(self):
        tasks.freeze(self.u)
        self.app('stop', self.names)
        self.app('up', self.names)
        for name, row in self.inspect(self.names).items():
            self.assertEqual(row['Id'], self.initial[name]['Id'])
            self.assertEqual(row['HostConfig']['RestartPolicy']['Name'], 'no')
        with tasks.context({'before': self.before}, 99):
            self.u.start_apps({})
        self.assert_restored()

    def test_precommit_failure_restores_old_compose_and_exact_policies(self):
        with patch.object(tasks, 'migrate', side_effect=RuntimeError('precommit failure')), \
                tasks.context({'before': self.before}, 99):
            with self.assertRaisesRegex(RuntimeError, 'precommit failure'):
                engine.apply()
        self.assertEqual(self.fixture.compose.read_bytes(), self.old)
        self.assertTrue((self.fixture.work / 'rolled-back.json').exists())
        self.assert_restored()

    def commit_schema(self, *args):
        self.schema['domestic'] = '0044'

    def test_successful_candidate_keeps_exact_restart_policies(self):
        with patch.object(tasks, 'migrate', side_effect=self.commit_schema), \
                tasks.context({'before': self.before}, 99):
            self.assertEqual(engine.apply(), 'applied')
        self.assertEqual(self.fixture.compose.read_bytes(), self.new)
        self.assertTrue((self.fixture.work / 'applied.json').exists())
        self.assert_restored()

    def test_committed_start_failure_only_recovers_forward(self):
        with patch.object(tasks, 'migrate', side_effect=self.commit_schema), \
                patch.object(self.u, 'start_apps', side_effect=RuntimeError('startup interrupted')), \
                tasks.context({'before': self.before}, 99):
            with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
                engine.apply()
        self.assertEqual(self.fixture.compose.read_bytes(), self.new)
        self.assertFalse((self.fixture.work / 'rolled-back.json').exists())
        with patch.object(tasks, 'check_migration'), \
                patch.object(tasks.forward, 'stop_existing', side_effect=lambda u: self.app('stop', self.names)), \
                tasks.context({'before': self.before}, 99):
            tasks.resume({'before': self.before}, 99)
        self.assertTrue((self.fixture.work / 'applied.json').exists())
        self.assertFalse((self.fixture.work / 'rolled-back.json').exists())
        self.assert_restored()


if __name__ == '__main__':
    unittest.main()
