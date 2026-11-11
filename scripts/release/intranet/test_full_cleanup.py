"""Full cleanup orchestration, with real ledger files and isolated category boundaries."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import catalog
import full_cleanup


@pytest.fixture
def world(tmp_path, monkeypatch):
    root, state, sources = [tmp_path/name for name in ('lan', 'state', 'sources')]
    for path in (root, state, sources):
        path.mkdir()
    current = dict(backend=str(sources/'B'), frontend=str(sources/'C'))
    previous = dict(backend=str(sources/'B'), frontend=str(sources/'B'))
    images = {'web': 'sha256:shared', 'db': 'sha256:db'}
    value = dict(version=1, current=catalog.record(current, images, str(state/'tx-C')),
                 previous=catalog.record(previous, images, str(state/'tx-B')),
                 known_images=list(images.values()), artifacts={}, staged={}, unowned=['unknown'])
    data = dict(current=current, previous=previous, pending=None, last=None, retention=value)
    writes, calls = [], []
    def report(name, content):
        writes.append(name)
        (state/name).write_text(json.dumps(content))
    store = SimpleNamespace(root=state, report=report)
    u = SimpleNamespace(ROOT=root)
    monkeypatch.setattr(full_cleanup.snapshot, 'RELEASES', sources)
    monkeypatch.setattr(full_cleanup.snapshot, 'capture', lambda *a, **k: copy.deepcopy(data['current']))
    monkeypatch.setattr(full_cleanup.catalog.image_gc, 'capture', lambda *a: images.copy())
    monkeypatch.setattr(full_cleanup.artifact_gc, 'allocated', lambda paths: sum(
        p.stat().st_size for base in paths if base.exists() for p in base.rglob('*') if p.is_file()))
    monkeypatch.setattr(full_cleanup.image_gc, 'layer_bytes', lambda u: 1000)
    def category(name):
        def execute(*args, **kwargs):
            calls.append((name, args, kwargs))
            return dict(status='complete' if kwargs['apply'] else 'preview', deleted=[])
        return execute
    for name, module in [('sources', full_cleanup.cleanup), ('images', full_cleanup.image_gc),
                         ('artifacts', full_cleanup.artifact_gc)]:
        monkeypatch.setattr(module, 'execute', category(name))
    return SimpleNamespace(data=data, u=u, store=store, writes=writes, calls=calls, root=tmp_path)


def test_preview_does_not_write_and_uses_one_catalog_for_every_category(world):
    w = world
    saved = copy.deepcopy(w.data)
    before = sorted(str(p) for p in w.root.rglob('*'))
    result = full_cleanup.execute(w.u, w.store, w.data)
    assert result['status'] == 'preview' and result['unowned'] == ['unknown']
    assert not w.writes and w.data == saved
    assert sorted(str(p) for p in w.root.rglob('*')) == before
    assert [c[0] for c in w.calls] == ['sources', 'images', 'artifacts']
    image_args = w.calls[1][1]
    assert image_args[2] == w.data['retention']['current']['images']
    assert image_args[3] == w.data['retention']['previous']['images']
    artifact_args = w.calls[2][1]
    assert artifact_args[3:5] == catalog.protected(w.data)
    assert all(not c[2]['apply'] for c in w.calls)


@pytest.mark.parametrize('phase', ['prepared', 'deploying', 'recovered'])
def test_pending_blocks_before_any_inspection_or_write(world, monkeypatch, phase):
    w = world
    w.data['pending'] = {'phase': phase}
    monkeypatch.setattr(full_cleanup.snapshot, 'capture', lambda *a, **k: pytest.fail('pending must block first'))
    with pytest.raises(RuntimeError, match='Pending release'):
        full_cleanup.execute(w.u, w.store, w.data, apply=True)
    assert not w.writes and not w.calls


@pytest.mark.parametrize('category', ['sources', 'images', 'artifacts'])
def test_category_failure_preserves_success_and_other_categories_continue(world, monkeypatch, category):
    w = world
    original = copy.deepcopy(w.data)
    modules = {'sources': full_cleanup.cleanup, 'images': full_cleanup.image_gc, 'artifacts': full_cleanup.artifact_gc}
    def failure(*args, **kwargs):
        assert (w.store.root/'intranet.json').exists()  # Ownership durable before deleting evidence.
        raise OSError('isolated cleanup failure')
    monkeypatch.setattr(modules[category], 'execute', failure)
    result = full_cleanup.execute(w.u, w.store, w.data, apply=True)
    assert result['status'] == 'warning'
    assert result['results'][category] == dict(status='warning', error='OSError', deleted=[])
    assert set(c[0] for c in w.calls) == set(modules) - {category}
    assert w.data == original
    assert json.loads((w.store.root/'intranet.json').read_text()) == original
    receipt = json.loads((w.store.root/'intranet-complete-cleanup.json').read_text())
    assert receipt == result
    assert result['net_released_bytes'] == result['before_bytes'] - result['after_bytes']


def test_catalog_drift_stops_all_deletion_and_writes(world):
    w = world
    w.data['retention']['previous']['state_sha256'] = 'tampered'
    with pytest.raises(RuntimeError, match='catalog drift'):
        full_cleanup.execute(w.u, w.store, w.data, apply=True)
    assert not w.writes and not w.calls
