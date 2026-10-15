"""Runner → persisted transcript → API, using a fake CLI boundary only."""
from uuid import UUID
import pytest
from app.overseas.execution import runner
from app.overseas.execution.models import Job
from app.overseas.studio.models import Turn
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_cli_event_json import wire, SEARCH_ID


@pytest.mark.parametrize('mode', ['success', 'invalid', 'exit', 'timeout', 'incomplete', 'failed'])
def test_real_runner_search_compatibility(studio, monkeypatch, tmp_path, mode):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path)
    def execute(command, prompt, control, timeout, monitor, started):
        started(123, 'boot', 'birth')
        raw = wire([] if mode == 'incomplete' else
                   ['{"type":"turn.failed"}'] if mode == 'failed' else None)
        if mode == 'invalid':
            raw += '{"type":"turn.completed","usage":{"input_tokens":1,"input_tokens":2}}\n'
        (control / 'events.jsonl').write_text(raw, encoding='utf-8')
        assert not monitor()
        return dict(exit_code=1 if mode == 'exit' else 0,
                    reason='timeout' if mode == 'timeout' else None)
    monkeypatch.setattr(runner, 'execute', execute)
    turn = send(client, task).json()['turns'][0]
    runner.run(factory, turn['jobId'])
    root = ROOT + '/tasks/' + task['id'] + '/studio'
    row = client.get(root).json()['turns'][0]
    assert row['status'] == ('succeeded' if mode == 'success' else 'failed')
    assert row['reply'] == '完整最终回复'
    records = client.get(root + '/transcript').json()['items']
    assert len([r for r in records if r['itemId'] == SEARCH_ID]) == 2
    assert [r['text'] for r in records if r['kind'] == 'message'] == ['完整最终回复']
    if mode == 'invalid':
        assert 'EVENT_STREAM_INVALID' in row['error']
        assert '检查配置或输入' not in row['error']
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).execution_count == 1
        assert session.get(Turn, UUID(turn['id'])).event_invalid == (mode == 'invalid')
