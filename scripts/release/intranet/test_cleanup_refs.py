import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import cleanup_refs as refs

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='Linux process and symlink references')


def test_ledger_protects_all_four_source_paths_and_resolved_interpreter(tmp_path):
    roots = [tmp_path / name for name in ('front', 'back', 'prevfront', 'prevback', 'runtime')]
    for root in roots:
        root.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(roots[4], target_is_directory=True)
    data = {'current': {'frontend': str(roots[0]), 'backend': str(roots[1])},
            'previous': {'frontend': str(roots[2]), 'backend': str(roots[3]),
                         'native': {'worker': {'python': str(alias / 'bin/python')}}}}
    r = refs.References(tmp_path)
    refs.ledger_refs(r, data)
    assert all(str(p) in r.reasons for p in roots)


def test_process_cwd_fd_maps_environment_and_arguments(tmp_path):
    root, proc = tmp_path / 'releases', tmp_path / 'proc'
    root.mkdir()
    process = proc/'123'
    (process/'fd').mkdir(parents=True)
    (process/'cmdline').write_bytes((str(root/'argument/python')+'\0--flag\0').encode())
    (process/'environ').write_bytes(('PYTHONPATH='+str(root/'env/lib')+'\0').encode())
    (process/'maps').write_text('0000 r-xp 00 0 ' + str(root/'mapped/lib.so'))
    for name, target in [('cwd','working'), ('exe','executable'), ('root','chroot'), ('fd/5','openfile')]:
        (process/name).symlink_to(root/target)
    r = refs.References(root)
    refs.process_refs(r, proc)
    assert set(Path(p).name for p in r.reasons) == {
        'argument', 'env', 'mapped', 'working', 'executable', 'chroot', 'openfile'}


def test_live_process_missing_metadata_fails_closed(tmp_path):
    proc = tmp_path/'123'
    proc.mkdir()
    (proc/'cmdline').write_bytes(b'python\0')
    with pytest.raises(RuntimeError, match='incomplete'):
        refs.process_refs(refs.References(tmp_path/'sources'), tmp_path)


def test_relative_process_arguments_and_library_paths_use_process_cwd(tmp_path):
    root, proc = tmp_path/'sources', tmp_path/'proc'
    process = proc/'123'
    (process/'fd').mkdir(parents=True)
    (process/'cmdline').write_bytes(b'python3\0sources/old/backend/worker.py\0--config=sources/config/settings\0')
    (process/'environ').write_bytes(b'PYTHONPATH=sources/library/lib\0')
    (process/'maps').write_text('')
    for name in ('cwd', 'root'):
        (process/name).symlink_to(tmp_path, target_is_directory=True)
    (process/'exe').symlink_to('/usr/bin/python3')
    r = refs.References(root)
    refs.process_refs(r, proc)
    assert {str(root/n) for n in ('old', 'config', 'library')} <= set(r.reasons)


def test_stopped_container_and_loaded_systemd_references(tmp_path, monkeypatch):
    root = tmp_path/'releases'
    root.mkdir()
    current = root/'current'
    current.mkdir()
    calls = []
    def run(args):
        calls.append(args)
        if args[:3] == ['docker', 'ps', '-aq']:
            return 'stopped-container'
        if args[:2] == ['docker', 'inspect']:
            return json.dumps([{'State': {'Running': False},
                                'Mounts': [{'Source': str(root/'mounted/backend')}]}])
        if args[:2] == ['systemctl', 'list-units']:
            return 'example.service loaded inactive dead Example'
        if args == ['systemctl', 'show', '-p', 'UnitPath', '--value']:
            return str(tmp_path/'empty-units')
        return 'WorkingDirectory=' + str(root/'configured/backend')
    monkeypatch.setattr(refs, 'process_refs', lambda *a: None)
    result = refs.collect(SimpleNamespace(run=run),
                          {'current': {'backend': str(current), 'frontend': str(current)}}, root)
    assert str(root/'mounted') in result and str(root/'configured') in result
    assert ['docker', 'inspect', 'stopped-container'] in calls


def test_mounting_parent_protects_all_releases(tmp_path):
    root = tmp_path/'sources'
    root.mkdir()
    (root/'one').mkdir()
    (root/'two').mkdir()
    r = refs.References(root)
    r.path(str(tmp_path), 'parent-mount', parent_mount=True)
    assert set(r.reasons) == {str(root/'one'), str(root/'two')}


def test_vendor_unloaded_units_and_linked_dropins_are_scanned(tmp_path):
    root, units, external = tmp_path/'sources', tmp_path/'vendor', tmp_path/'external'
    root.mkdir()
    units.mkdir()
    external.mkdir()
    (units/'unloaded.service').write_text('WorkingDirectory='+str(root/'old/backend'))
    (external/'config.conf').write_text('ExecStart='+str(root/'dependency/python'))
    (units/'other.service.d').symlink_to(external, target_is_directory=True)
    r = refs.References(root)
    refs.unit_configs(SimpleNamespace(run=lambda args: str(units)), r)
    assert set(r.reasons) == {str(root/'old'), str(root/'dependency')}


@pytest.mark.parametrize('suffix', ['mount', 'automount', 'socket', 'timer', 'path', 'scope'])
def test_non_service_units_also_protect_source_references(tmp_path, suffix):
    root, units = tmp_path/'sources', tmp_path/'units'
    units.mkdir()
    (units/('example.'+suffix)).write_text('What='+str(root/'old/backend'))
    r = refs.References(root)
    refs.unit_configs(SimpleNamespace(run=lambda args: str(units)), r)
    assert str(root/'old') in r.reasons


def test_dangling_unit_link_skips_missing_file_but_preserves_target_release(tmp_path):
    root, units = tmp_path/'sources', tmp_path/'units'
    units.mkdir()
    (units/'broken.service').symlink_to(tmp_path/'missing')
    (units/'old.service').symlink_to(root/'old/missing.service')
    r = refs.References(root)
    refs.unit_configs(SimpleNamespace(run=lambda args: str(units)), r)
    assert str(root/'old') in r.reasons


def test_unloaded_unit_path_alias_protects_real_target(tmp_path):
    root, units = tmp_path/'sources', tmp_path/'units'
    (root/'old/backend').mkdir(parents=True)
    units.mkdir()
    alias = tmp_path/'alias'
    alias.symlink_to(root/'old', target_is_directory=True)
    (units/'unloaded.service').write_text('WorkingDirectory='+str(alias/'backend'))
    r = refs.References(root)
    refs.unit_configs(SimpleNamespace(run=lambda args: str(units)), r)
    assert str(root/'old') in r.reasons


@pytest.mark.parametrize('source', ['/', '/opt'])
def test_host_parent_bind_retains_all_but_normal_root_mount_does_not(tmp_path, source):
    root = tmp_path/'sources'
    root.mkdir()
    (root/'old').mkdir()
    r = refs.References(root)
    base = '1 0 8:1 / / rw - ext4 /dev/sda1 rw\n'
    refs.mount_refs(r, base)
    assert not r.reasons
    parent = '/' if source == '/' else str(tmp_path)
    refs.mount_refs(r, base + f'2 1 8:1 {parent} /srv/copy rw - ext4 /dev/sda1 rw\n')
    assert str(root/'old') in r.reasons
