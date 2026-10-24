"""Native historical images traverse the real runner, database and download API."""
import base64
import hashlib
import pytest
import json
from app.overseas.execution import runner
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas, send, reply_only_process


def test_historical_native_without_new_generation_must_not_complete_with_zero(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    initial = runner.execute

    def first(*args):
        receipt = initial(*args)
        work = case.workspace
        data = (work.work / 'output0.png').read_bytes()
        native = work.home / '.codex/generated_images/session-123/old.png'
        native.parent.mkdir(parents=True)
        native.write_bytes(data)
        history = work.home / '.codex/sessions/rollout-session-123.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        rows.insert(2, dict(type='event_msg', payload=dict(type='item_completed',
            turn_id=args[2].name, thread_id='session-123', item=dict(type='Extension',
                kind='image_gen.generation', status='completed', failure=None,
                savedPath='/home/runner/.codex/generated_images/session-123/old.png',
                result=base64.b64encode(data).decode()))))
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return receipt

    monkeypatch.setattr(runner, 'execute', first)
    case.run()
    case.complete(expected=1)
    original = case.downloaded()[0]
    second = reply_only_process(case, '')

    def redisplay(*args):
        receipt = second(*args)
        history = case.workspace.home / '.codex/sessions/rollout-session-123.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        rows.insert(-2, dict(type='response_item', payload=dict(type='custom_tool_call_output',
            call_id='display-historical-image', output=[dict(type='input_image',
                image_url='data:image/png;base64,' + base64.b64encode(original).decode())],
            internal_chat_message_metadata_passthrough=dict(turn_id=args[2].name))))
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return receipt

    monkeypatch.setattr(runner, 'execute', redisplay)
    turn = send(case.client, case.task, key='historical-native-again').json()['turns'][-1]
    runner.run(case.factory, turn['jobId'])
    latest = case.view()['turns'][-1]
    print(json.dumps(dict(status=latest['status'], deliveryStatus=latest['deliveryStatus'],
                         pictureCount=len(latest['pictures']), error=latest['deliveryError'])))
    assert len(latest['pictures']) == 1, 'Final historical native image was silently lost'
    assert case.client.get(latest['pictures'][0]['url']).content == original


def test_successfully_generated_image_from_failed_old_turn_can_be_redisplayed(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    initial = runner.execute
    original = []

    def first(*args):
        initial(*args)
        work = case.workspace
        data = (work.work / 'output0.png').read_bytes()
        original.append(data)
        native = work.home / '.codex/generated_images/session-123/old.png'
        native.parent.mkdir(parents=True)
        native.write_bytes(data)
        history = work.home / '.codex/sessions/rollout-session-123.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        rows.insert(2, dict(type='event_msg', payload=dict(type='item_completed',
            turn_id=args[2].name, thread_id='session-123', item=dict(type='Extension',
                kind='image_gen.generation', status='completed', failure=None,
                savedPath='/home/runner/.codex/generated_images/session-123/old.png',
                result=base64.b64encode(data).decode()))))
        rows[-1] = dict(type='event_msg', payload=dict(type='task_failed', turn_id=args[2].name))
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        events_path = args[2] / 'events.jsonl'
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        events[-1] = dict(type='turn.failed', error=dict(message='connection lost after generation'))
        events_path.write_text('\n'.join(json.dumps(row) for row in events))
        return dict(exit_code=1)

    monkeypatch.setattr(runner, 'execute', first)
    case.run()
    assert case.current()['status'] == 'failed'
    assert case.current()['pictures'] == []
    assert case.view()['activeTurnId'] is None
    second = reply_only_process(case, '')

    def redisplay(*args):
        receipt = second(*args)
        history = case.workspace.home / '.codex/sessions/rollout-session-123.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        rows.insert(-2, dict(type='response_item', payload=dict(type='custom_tool_call_output',
            call_id='display-old-valid-image', output=[dict(type='input_image',
                image_url='data:image/png;base64,' + base64.b64encode(original[0]).decode())],
            internal_chat_message_metadata_passthrough=dict(turn_id=args[2].name))))
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return receipt

    monkeypatch.setattr(runner, 'execute', redisplay)
    response = send(case.client, case.task, key='old-successful-image-new-successful-final')
    assert response.status_code == 200, response.text
    turn = response.json()['turns'][-1]
    runner.run(case.factory, turn['jobId'])
    latest = case.view()['turns'][-1]
    print(json.dumps(dict(status=latest['status'], deliveryStatus=latest['deliveryStatus'],
                         pictureCount=len(latest['pictures']), error=latest['deliveryError'])))
    assert len(latest['pictures']) == 1, 'A successful old generation is wrongly gated by its old turn failure'
    assert case.client.get(latest['pictures'][0]['url']).content == original[0]


@pytest.mark.parametrize('earlier_failure', [False, True])
def test_final_native_after_handled_generation_failure(studio, monkeypatch, tmp_path, earlier_failure):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    initial = runner.execute
    original = []

    def completed_with_native(*args):
        receipt = initial(*args)
        data = (case.workspace.work / 'output0.png').read_bytes()
        original.append(data)
        native = case.workspace.home / '.codex/generated_images/session-123/final.png'
        native.parent.mkdir(parents=True)
        native.write_bytes(data)
        encoded = base64.b64encode(data).decode()
        turn = args[2].name
        def event(kind, **kwargs):
            return dict(type='event_msg', payload=dict(type=kind, turn_id=turn, **kwargs))
        rows = [dict(type='session_meta', payload=dict(id='session-123')),
                event('task_started')]
        if earlier_failure:
            rows.append(event('item_completed', thread_id='session-123', item=dict(
                type='Extension', kind='image_gen.generation', id='failed-attempt',
                status='failed', failure=dict(message='temporary service failure'))))
        rows += [event('item_completed', thread_id='session-123', item=dict(
            type='Extension', kind='image_gen.generation', id='successful-retry',
            status='completed', failure=None,
            savedPath='/home/runner/.codex/generated_images/session-123/final.png', result=encoded)),
            dict(type='response_item', payload=dict(type='custom_tool_call_output',
                call_id='present-final', output=[dict(type='input_image',
                    image_url='data:image/png;base64,' + encoded)],
                internal_chat_message_metadata_passthrough=dict(turn_id=turn))),
            event('item_completed', thread_id='session-123', item=dict(type='AgentMessage',
                phase='final_answer', content=[dict(type='Text', text='')])),
            event('task_complete', last_agent_message='')]
        history = case.workspace.home / '.codex/sessions/rollout-session-123.jsonl'
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        events_file = args[2] / 'events.jsonl'
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        events[-2]['item']['text'] = ''
        events_file.write_text('\n'.join(json.dumps(row) for row in events))
        assert receipt == dict(exit_code=0)
        return receipt

    monkeypatch.setattr(runner, 'execute', completed_with_native)
    case.run()
    first = case.current()
    if earlier_failure:
        case.recover()
    latest = case.current()
    print(json.dumps(dict(earlierFailure=earlier_failure, before=first['deliveryStatus'],
        status=latest['status'], deliveryStatus=latest['deliveryStatus'],
        pictureCount=len(latest['pictures']), executionCount=case.job().execution_count,
        cliCalls=len(case.commands), originalSha256=hashlib.sha256(original[0]).hexdigest())))
    assert len(latest['pictures']) == 1, 'Handled earlier tool failure vetoes valid final native image'
    assert case.client.get(latest['pictures'][0]['url']).content == original[0]
    case.complete(expected=1)
