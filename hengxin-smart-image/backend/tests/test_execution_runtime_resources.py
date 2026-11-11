from types import SimpleNamespace

import pytest

from app.execution import workspace


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    binary = tmp_path / 'bin' / 'codex'
    binary.parent.mkdir()
    binary.touch()
    binary.with_name('codex-code-mode-host').touch()
    bwrap = tmp_path / 'outer-bwrap'
    bwrap.touch()
    monkeypatch.setattr(workspace, 'os', SimpleNamespace(name='posix', environ={}))
    ws = workspace.Workspace(tmp_path / 'home', tmp_path / 'work', tmp_path / 'control', use_skill=False)
    return tmp_path, binary, lambda: workspace.sandbox_command(ws, binary, ['sandbox', '--', 'true'], bwrap)


@pytest.mark.parametrize('location', ['bin/codex-resources', 'codex-resources'])
def test_inner_bwrap_is_visible_beside_remapped_cli(runtime, location):
    root, _, build = runtime
    folder = root / location
    folder.mkdir()
    nested = folder / 'bwrap'
    nested.touch()
    argv = build()
    i = argv.index('/opt/codex-resources/bwrap')
    assert argv[i-2:i+1] == ['--ro-bind', str(nested), '/opt/codex-resources/bwrap']
    assert '--clearenv' in argv and '--cap-drop' in argv
    assert '--unshare-user' in argv and '--unshare-pid' in argv
    assert 'danger-full-access' not in argv


def test_old_distribution_still_uses_system_bwrap(runtime):
    _, _, build = runtime
    assert '/opt/codex-resources/bwrap' not in build()


def test_resource_directory_refused_as_executable(runtime):
    root, _, build = runtime
    (root / 'codex-resources' / 'bwrap').mkdir(parents=True)
    with pytest.raises(RuntimeError, match='Invalid Codex sandbox resource'):
        build()


def test_document_configuration_only_added_readonly(runtime):
    _, _, build = runtime
    argv = build()
    for path in ('/etc/fonts', '/etc/libreoffice', '/var/cache/fontconfig'):
        if workspace.Path(path).exists():
            i = argv.index(path)
            assert argv[i-1:i+2] == ['--ro-bind', path, path]
