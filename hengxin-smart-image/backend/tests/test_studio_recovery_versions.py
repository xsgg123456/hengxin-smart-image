"""A captured original has one identity across both manual entry points."""
from uuid import UUID
import pytest
from app.overseas.studio import delivery_context, delivery_snapshot
from app.overseas.studio.output_files import validated
from app.overseas.studio.models import OutputFile, Picture
from app.overseas.execution.models import Job
from test_overseas_studio_file_recovery import (
    missed, studio, materials, overseas, listed, take, count, png, send, finish,
)


def capture(case, turn, name, data):
    with case.factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        identity = delivery_context.identity(job)
    control = case.root / 'control' / turn['id'] / 'delivery'
    target = '/work/' + name
    delivery_snapshot.begin(control, identity, 'done', 'thread-1', [target])
    return delivery_snapshot.capture(control, target, validated(data, name))['items'][0]['pictureId']


@pytest.mark.parametrize('first_source', ['work', 'snapshot'])
@pytest.mark.parametrize('name,data,model', [('design.zip', b'one original', OutputFile),
                                          ('design.png', png(), Picture)])
def test_two_sources_share_one_original_in_either_order(missed, first_source, name, data, model):
    (missed.work / name).write_bytes(data)
    identity = capture(missed, missed.turn, name, data)
    choices = {item['source']: item for item in listed(missed)['items']}
    second_source = 'snapshot' if first_source == 'work' else 'work'
    first = take(missed, [choices[first_source]]).json()
    second = take(missed, [choices[second_source]]).json()
    assert first['errors'] == second['errors'] == []
    assert first['saved'] == second['saved']
    assert first['saved'][0]['id'] == identity
    assert count(missed, model) == 1


def test_new_turn_snapshot_keeps_its_own_delivery_even_with_same_bytes(missed):
    name, data = 'design.zip', b'same bytes delivered again'
    (missed.work / name).write_bytes(data)
    first_id = capture(missed, missed.turn, name, data)
    assert take(missed).json()['errors'] == []
    response = send(missed.client, missed.task, key='second-delivery',
                    conversationId=str(missed.cid))
    assert response.status_code == 200, response.text
    second = response.json()['turns'][-1]
    finish(missed.factory, second)
    second_id = capture(missed, second, name, data)
    assert second_id != first_id
    result = take(missed).json()
    assert result['errors'] == []
    assert {row['id'] for row in result['saved']} == {first_id, second_id}
    assert count(missed, OutputFile) == 2
