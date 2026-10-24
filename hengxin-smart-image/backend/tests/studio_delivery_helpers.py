"""Real runner/API harness with only process and external storage substituted."""
from datetime import timedelta
import json
from uuid import UUID

from sqlalchemy import func, select

from app.db.timestamps import utcnow
from app.overseas.execution import reconcile, runner
from app.overseas.execution.models import Job
from app.overseas.studio import delivery_recovery
from app.overseas.studio.models import Picture
from app.overseas.tasks import cleanup_process
from test_overseas_materials import materials
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_tasks import overseas, ROOT


class DeliveryCase:
    def __init__(self, fixture, monkeypatch, tmp_path, count=3):
        self.client, self.factory, self.actor, self.task, _, self.store = fixture
        self.commands = fake_runtime(fixture, monkeypatch, tmp_path, image_count=count)
        monkeypatch.setattr(cleanup_process, 'group_alive', lambda _job: False)
        monkeypatch.setattr(reconcile, 'same_process', lambda *_args: False)
        monkeypatch.setattr(delivery_recovery, 'get_store', lambda: self.store)
        self.root = ROOT + '/tasks/' + self.task['id'] + '/studio'
        self.turn = send(self.client, self.task).json()['turns'][0]
        self.job_id = UUID(self.turn['jobId'])
        self.puts = []
        self.real_put = self.store.put

        def put(record, data):
            self.puts.append(record.object_key)
            self.real_put(record, data)

        self.put = put
        monkeypatch.setattr(self.store, 'put', put)

    @property
    def workspace(self):
        return self.commands[-1][0]

    def run(self):
        runner.run(self.factory, self.job_id)

    def view(self):
        response = self.client.get(self.root)
        assert response.status_code == 200, response.text
        return response.json()

    def current(self):
        return next(turn for turn in self.view()['turns'] if turn['id'] == self.turn['id'])

    def job(self):
        with self.factory() as session:
            row = session.get(Job, self.job_id)
            session.expunge(row)
            return row

    def due(self):
        with self.factory.begin() as session:
            row = session.get(Job, self.job_id)
            row.lease_until = utcnow() - timedelta(seconds=1)
            row.result = {**(row.result or {}),
                'deliveryRetryAt': (utcnow() - timedelta(seconds=1)).isoformat()}

    def recover(self):
        self.due()
        reconcile.reconcile_once(self.factory)

    def count(self, model=Picture):
        with self.factory() as session:
            return session.scalar(select(func.count()).select_from(model))

    def downloaded(self):
        result = []
        for picture in self.current()['pictures']:
            response = self.client.get(picture['url'])
            assert response.status_code == 200, response.text
            result.append(response.content)
        return result

    def complete(self, expected=3):
        turn = self.current()
        assert turn['status'] == 'succeeded', turn
        assert turn['deliveryStatus'] == dict(state='complete', expected=expected, saved=expected)
        assert len(turn['pictures']) == len(self.downloaded()) == expected
        assert self.view()['activeTurnId'] is None
        assert self.job().execution_count == 1
        assert len(self.commands) == 1


def reply_only_process(case, reply):
    """A second CLI turn presents an existing file without writing any images."""
    def execute(_command, _prompt, control, _timeout, monitor, started):
        started(123, 'boot', 'birth')
        assert not monitor()
        events = [dict(type='thread.started', thread_id='session-123'), dict(type='turn.started'),
            dict(type='item.completed', item=dict(type='agent_message', text=reply)),
            dict(type='turn.completed')]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(row) for row in events))
        history = case.workspace.home / '.codex/sessions/rollout-session-123.jsonl'
        records = [dict(type='event_msg', payload=dict(type='task_started', turn_id=control.name)),
            dict(type='event_msg', payload=dict(type='item_completed', turn_id=control.name,
                thread_id='session-123', item=dict(type='AgentMessage', phase='final_answer',
                    content=[dict(type='Text', text=reply)]))),
            dict(type='event_msg', payload=dict(type='task_complete', turn_id=control.name,
                last_agent_message=reply))]
        with history.open('a', encoding='utf-8') as stream:
            stream.write(''.join(json.dumps(row) + '\n' for row in records))
        return dict(exit_code=0)
    return execute
