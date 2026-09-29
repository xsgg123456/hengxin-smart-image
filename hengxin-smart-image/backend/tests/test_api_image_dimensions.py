from fractions import Fraction
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4
from zipfile import ZipFile
import json

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select

from app.modules.api_image_edits.dimensions import request_dimensions, normalize_result
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiAttempt, ApiFile, ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.relay import RelayClient, RelayError, RelayResult
from app.modules.files.validation import _decode_image
from files_helpers import files_env
from test_api_image_domain import ROOT, enabled_api, upload
from test_api_image_execution import Client, due
from test_api_image_relay import config, response


def encoded(size, kind='PNG', mode='RGB'):
    buffer = BytesIO()
    with Image.new(mode, size, '#123456') as image:
        image.save(buffer, format=kind)
    return buffer.getvalue()


def validated(size, kind='PNG'):
    return _decode_image(SimpleNamespace(file=BytesIO(encoded(size, kind)),
                         filename='result', content_type=None))


@pytest.mark.parametrize(('source', 'expected'), [
    ((800, 800), (1024, 1024)), ((790, 1500), (800, 1520)),
    ((790, 1166), (800, 1184)), ((790, 730), (800, 736)),
    ((1, 2), (16, 16)), ((16, 17), (16, 32)), ((17, 1600), (32, 1632)),
    ((800, 1600), (800, 1600)),
])
def test_size_examples_and_single_edge_extension(source, expected):
    assert request_dimensions(*source) == expected


def test_size_policy_exact_bounds_and_rational_ordering():
    for width, height in [(799, 1231), (1600, 3200), (1570, 2464), (1632, 1600)]:
        edges = []
        for edge in (width, height):
            values = [v for v in range(edge, edge * 102 // 100 + 1) if v % 16 == 0]
            edges.append(values or [(edge + 15) // 16 * 16])
        choices = [(w, h) for w in edges[0] for h in edges[1]]
        expected = sorted(choices, key=lambda p: (abs(Fraction(*p) - Fraction(width, height)),
                          Fraction(p[0] - width, width) + Fraction(p[1] - height, height), *p))[0]
        assert request_dimensions(width, height) == expected


@pytest.mark.parametrize('kind', ['JPEG', 'WEBP', 'PNG'])
def test_output_is_png_with_source_size_even_extreme_ratio(kind):
    output = normalize_result(validated((3, 200), kind), 31, 7, 1024 * 1024)
    assert (output.width, output.height, output.content_type, output.name) == (31, 7, 'image/png', 'result.png')
    with Image.open(BytesIO(output.data)) as image:
        assert image.format == 'PNG' and image.size == (31, 7)


@pytest.mark.parametrize('kind', ['PNG', 'JPEG', 'WEBP'])
def test_matching_dimensions_never_resample(kind, monkeypatch):
    original = validated((31, 7), kind)
    monkeypatch.setattr(Image.Image, 'resize', Mock(side_effect=AssertionError('resampled')))
    output = normalize_result(original, 31, 7, 1024 * 1024)
    assert output.content_type == 'image/png'
    if kind == 'PNG':
        assert output is original


def test_resize_matches_lanczos_pixels():
    buffer = BytesIO()
    pixels = Image.new('RGB', (12, 8))
    pixels.putdata([(i * 17 % 256, i * 3 % 256, i * 7 % 256) for i in range(96)])
    pixels.save(buffer, format='PNG')
    source = _decode_image(SimpleNamespace(file=BytesIO(buffer.getvalue()), filename='r.png', content_type=None))
    output = normalize_result(source, 19, 13, 1024 * 1024)
    with Image.open(BytesIO(output.data)) as image:
        assert image.tobytes() == pixels.resize((19, 13), Image.Resampling.LANCZOS).tobytes()


def test_normalization_retains_output_byte_and_pixel_bounds():
    original = validated((13, 7), 'JPEG')
    with pytest.raises(HTTPException) as byte_error:
        normalize_result(original, 31, 17, 10)
    assert byte_error.value.status_code == 413
    with pytest.raises(HTTPException) as pixel_error:
        normalize_result(original, Image.MAX_IMAGE_PIXELS, 2, 1024 * 1024)
    assert pixel_error.value.status_code == 422


def make_task(web, sizes):
    sources = [web.post(ROOT + '/files', files={'file': ('original.png', encoded(size), 'image/png')}).json()
               for size in sizes]
    payload = {'name': '逐图尺寸', 'prompt': '原提示词',
               'originalFileIds': [p['fileId'] for p in sources],
               'materialFileId': upload(web)['fileId']}
    reply = web.post(ROOT + '/tasks', json=payload, headers={'Idempotency-Key': str(uuid4())})
    assert reply.status_code == 202
    return ROOT + '/tasks/' + reply.json()['taskId']


def test_mixed_task_tracks_actual_request_return_and_png_download(files_env):
    web, factory, store, _ = files_env
    sizes = [(800, 800), (790, 1500), (790, 1166), (790, 730)]
    path = make_task(web, sizes)
    client = Client([RelayResult(image_bytes=encoded((101, 103), 'JPEG')) for _ in sizes])
    for _ in sizes:
        assert execute_next(factory, store, client)
    assert [args[5]['size'] for args in client.calls] == ['1024x1024', '800x1520', '800x1184', '800x736']
    assert all(args[4] == '原提示词' for args in client.calls)
    task = web.get(path).json()
    final_bytes = []
    for item, size in zip(task['items'], sizes):
        assert (item['source']['width'], item['source']['height']) == size
        assert (item['result']['width'], item['result']['height']) == size
        result = web.get(item['result']['url'])
        final_bytes.append(result.content)
        assert web.get(item['result']['url'] + '?download=true').content == result.content
        assert result.headers['content-type'] == 'image/png'
        with Image.open(BytesIO(result.content)) as image:
            assert image.format == 'PNG' and image.size == size
        with factory() as session:
            attempt = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == UUID(item['id'])))
            assert (attempt.request_width, attempt.request_height) == request_dimensions(*size)
            assert (attempt.return_width, attempt.return_height) == (101, 103)
            assert session.get(ApiTask, UUID(task['id'])).parameters['size'] == '1024x1024'
    archive = web.get(path + '/zip')
    assert archive.status_code == 200
    with ZipFile(BytesIO(archive.content)) as zipped:
        assert zipped.namelist() == ['01.png', '02.png', '03.png', '04.png']
        assert [zipped.read(name) for name in zipped.namelist()] == final_bytes


@pytest.mark.parametrize('legacy_snapshot', [False, True])
def test_old_result_revision_and_retries_anchor_original(files_env, legacy_snapshot):
    web, factory, store, _ = files_env
    path = make_task(web, [(790, 730)])
    assert execute_next(factory, store, Client())
    item = web.get(path).json()['items'][0]
    # Install a genuine historical result file with different dimensions.
    old = web.post(ROOT + '/files', files={'file': ('old.jpg', encoded((222, 333), 'JPEG'), 'image/jpeg')}).json()
    with factory.begin() as session:
        row = session.get(ApiItem, UUID(item['id']))
        row.result_id = UUID(old['fileId'])
        session.scalar(select(ApiVersion).where(ApiVersion.item_id == row.id)).file_id = row.result_id
    endpoint = path + '/items/' + item['id']
    reply = web.post(endpoint + '/revise', json={'baseVersion': 1, 'text': '修改'},
                     headers={'Idempotency-Key': str(uuid4())})
    assert reply.status_code == 202
    if legacy_snapshot:
        with factory.begin() as session:
            session.get(ApiItem, UUID(item['id'])).revision_snapshot = None
    client = Client([RelayError('retryable', 'HTTP_503', 'safe'), RelayResult(image_bytes=encoded((222, 333)))])
    assert execute_next(factory, store, client)
    due(factory)
    assert execute_next(factory, store, client)
    assert [args[5]['size'] for args in client.calls] == ['800x736', '800x736']
    final = web.get(path).json()['items'][0]
    assert final['result']['width'] == 790 and final['result']['height'] == 730
    assert final['versions'][0]['picture']['width'] == 222
    assert web.get(old['url']).content == encoded((222, 333), 'JPEG')


def test_conversion_failure_and_staging_retry_never_regenerate(files_env, monkeypatch):
    import app.modules.api_image_edits.execution as execution
    web, factory, store, _ = files_env
    path = make_task(web, [(79, 73)])
    client = Client([RelayResult(image_bytes=encoded((90, 90), 'JPEG'))])
    real = execution.normalize_result
    monkeypatch.setattr(execution, 'normalize_result', Mock(side_effect=OSError('encode failed')))
    assert execute_next(factory, store, client)
    item = web.get(path).json()['items'][0]
    assert item['state'] == 'collecting' and item['result'] is None
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        assert (attempt.return_width, attempt.return_height) == (90, 90)
    monkeypatch.setattr(execution, 'normalize_result', real)
    store.fail_put = True
    due(factory)
    assert execute_next(factory, store, client)
    with factory() as session:
        staging_id = session.get(ApiItem, UUID(item['id'])).staging_file_id
        staged = session.get(ApiFile, staging_id)
        assert (staged.width, staged.height, staged.content_type) == (79, 73, 'image/png')
    store.fail_put = False
    due(factory)
    assert execute_next(factory, store, client)
    final = web.get(path).json()['items'][0]
    assert final['result']['fileId'] == str(staging_id) and len(client.calls) == 1
    assert len(final['versions']) == 1


def test_relay_sends_dynamic_size_and_rejects_other_parameter_changes():
    pool = Mock()
    pool.request.return_value = response()
    client = RelayClient(config(), pool)
    from app.modules.api_image_edits.config import PARAMETERS
    args = (b'x', 'image/png', b'y', 'image/png', 'prompt')
    client.generate(*args, {**PARAMETERS, 'size': '800x1520'})
    payload = json.loads(pool.request.call_args.kwargs['body'])
    assert payload['size'] == '800x1520' and payload['prompt'] == 'prompt'
    for changes in ({'size': '790x1500'}, {'quality': 'low'}, {'model': 'other'}, {'n': 2}):
        with pytest.raises(RelayError):
            client.preflight(*args, {**PARAMETERS, **changes})


def test_preupgrade_frozen_staging_finishes_original_bytes(files_env, monkeypatch):
    import app.modules.api_image_edits.execution as execution
    web, factory, store, _ = files_env
    path = make_task(web, [(79, 73)])
    raw = encoded((90, 90), 'JPEG')
    client = Client([RelayResult(image_bytes=raw)])
    # Reproduce the old worker's format-preserving write, interrupted after put.
    real = execution.normalize_result
    monkeypatch.setattr(execution, 'normalize_result', lambda image, *args: image)
    store.fail_put = True
    assert execute_next(factory, store, client)
    with factory.begin() as session:
        attempt = session.scalar(select(ApiAttempt))
        attempt.request_width = attempt.request_height = None
        attempt.return_width = attempt.return_height = None
        staging_id = session.scalar(select(ApiItem)).staging_file_id
    monkeypatch.setattr(execution, 'normalize_result', real)
    store.fail_put = False
    due(factory)
    assert execute_next(factory, store, client)
    result = web.get(path).json()['items'][0]['result']
    assert result['fileId'] == str(staging_id) and len(client.calls) == 1
    assert web.get(result['url']).content == raw
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        assert attempt.request_width is None and attempt.request_height is None
        assert (attempt.return_width, attempt.return_height) == (90, 90)
