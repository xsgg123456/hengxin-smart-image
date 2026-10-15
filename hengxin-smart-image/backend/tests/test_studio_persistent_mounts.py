"""Mount wiring uses the same command constructor as the Linux worker."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.execution import workspace as runtime
from app.execution.persistent_mounts import mounts
from app.overseas.execution import materials


def space(tmp_path):
    for folder in ('home', 'work', 'round', 'control', 'inputs'):
        (tmp_path / folder).mkdir()
    index = tmp_path / 'index.json'
    index.write_text('{}')
    return SimpleNamespace(home=tmp_path / 'home', work=tmp_path / 'work',
        control=tmp_path / 'control', round_work=tmp_path / 'round',
        inputs_root=tmp_path / 'inputs', context_index=index, persistent=True,
        local_skill=None, skill_name='demo', skill_path='/work/skills/demo', use_skill=False)


@pytest.mark.parametrize('selected', [False, True])
def test_controlled_files_and_selected_skill_stay_outside_writable_work(tmp_path, monkeypatch, selected):
    ws = space(tmp_path)
    skill = {'name': 'demo', 'files': {'SKILL.md': 'skill'}} if selected else None
    job = SimpleNamespace(payload={'skill': skill, 'inputs': [], 'text': 'user'})
    materials.prepare(job, ws)
    assert not (ws.work / 'input.json').exists()
    assert (ws.round_work / 'input.json').is_file()
    assert not (ws.work / 'skills').exists()
    if selected:
        assert ws.local_skill == ws.round_work / 'skills/demo'
    files = [tmp_path / n for n in ('codex', 'codex-code-mode-host', 'bwrap')]
    for file in files:
        file.touch()
    monkeypatch.setattr(runtime, 'os', SimpleNamespace(name='posix', environ={}))
    args = runtime.sandbox_command(ws, str(files[0]), ['exec'], str(files[2]))
    assert ['--ro-bind', str(ws.inputs_root), '/work/inputs'] == args[args.index(str(ws.inputs_root)) - 1:args.index(str(ws.inputs_root)) + 2]
    assert args.index(str(ws.work)) < args.index(str(ws.inputs_root))
    assert '--remount-ro' in args
    assert args[args.index('/work/skills') - 1] == '--tmpfs'
    assert str(ws.control / 'input.json') in args
    assert str(ws.context_index) in args
    if selected:
        assert str(ws.local_skill) in args
    else:
        assert str(ws.round_work / 'skills/demo') not in args


def test_persistent_controlled_target_must_be_correct_kind(tmp_path):
    ws = space(tmp_path)
    (ws.control / 'input.json').write_text('{}')
    (ws.work / 'inputs').write_text('block mount')
    with pytest.raises(ValueError):
        mounts(ws)


@pytest.mark.skipif(__import__('os').name != 'posix', reason='Linux link boundary')
def test_model_cannot_redirect_next_round_input_mount(tmp_path):
    ws = space(tmp_path)
    (ws.control / 'input.json').write_text('{}')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (ws.work / 'inputs').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        mounts(ws)
