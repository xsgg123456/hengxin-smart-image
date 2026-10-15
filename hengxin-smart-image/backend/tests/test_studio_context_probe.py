"""Production recovery proof compares restored bytes to independent old sources."""
import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.execution.workspace import prepare_workspace
from app.overseas.studio.context_assets import identity, safe_name
from app.overseas.studio.context_workspace import inspect, prepare

spec = importlib.util.spec_from_file_location('context_probe',
    Path(__file__).with_name('studio_context_probe.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


@pytest.fixture
def restored(tmp_path):
    auth = tmp_path / 'auth.json'; auth.write_text('{}')
    turn = uuid4()
    ws = prepare_workspace(tmp_path, uuid4(), turn, auth)
    source = dict(id=str(uuid4()), name='original.csv', bucket='fixture', object_key='original',
        content_type='text/csv', size_bytes=6, checksum=hashlib.sha256(b'a,b\n1,2').hexdigest())
    raw = b'a,b\n1,2'
    source['size_bytes'] = len(raw)
    (ws.work / 'inputs').mkdir()
    (ws.work / 'inputs/1.csv').write_bytes(raw)
    (ws.work / 'note.txt').write_bytes(b'independent original note')
    history = [dict(turn_id=str(turn), inputs=[source])]
    plan = inspect(ws, history)
    canonical = '/work/inputs/' + identity(source) + '/' + safe_name(source['name'])
    plan['inputs'] = [dict(path=canonical, checksum=source['checksum'], size_bytes=len(raw))]
    prepare(ws, history, [], lambda _: pytest.fail('Original should be restored locally'))
    return ws, plan


def actual(ws):
    return {**p.hashes(ws.work), **p.hashes(ws.inputs_root, 'inputs/')}


def test_every_legacy_source_and_frozen_original_is_accounted_for(restored):
    ws, plan = restored
    assert p.verify_sources(ws.home.parent, plan, actual(ws)) == dict(
        sourceDigest=plan['digest'], sourceFilesVerified=2, sourceInputsVerified=1)


@pytest.mark.parametrize('fault', ['missing-index', 'wrong-index', 'target-content',
    'original-missing', 'old-source-changed', 'input-count'])
def test_circular_target_hashes_cannot_hide_lost_or_wrong_source(restored, fault):
    ws, plan = restored
    index = json.loads(ws.context_index.read_text())
    if fault == 'missing-index': index['files'] = []
    if fault == 'wrong-index': index['files'][0]['path'] = '/work/other.txt'
    if fault == 'target-content': (ws.work / 'note.txt').write_bytes(b'wrong target')
    if fault == 'original-missing':
        (ws.inputs_root / plan['inputs'][0]['path'].removeprefix('/work/inputs/')).unlink()
    if fault == 'old-source-changed': (ws.round_work / 'note.txt').write_bytes(b'changed source')
    if fault == 'input-count': plan['inputFiles'] = 2
    ws.context_index.write_text(json.dumps(index))
    with pytest.raises(ValueError):
        p.verify_sources(ws.home.parent, plan, actual(ws))
