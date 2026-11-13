import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

import joint_studio_paths as paths


pytestmark = pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0,
                                reason='requires isolated root Linux directory identities')


def adapter():
    def write(path, data, mode=0o600, exclusive=False):
        with open(path, 'xb' if exclusive else 'wb') as stream:
            stream.write(data)
        os.chmod(path, mode)
    return SimpleNamespace(safe=lambda *args, **kwargs: None, write=write)


def test_exact_permissions_idempotence_and_boot_rule(tmp_path):
    root, socket, boot = tmp_path / 'domestic', tmp_path / 'socket', tmp_path / 'boot.conf'
    paths.provision(adapter(), root, socket, boot)
    paths.provision(adapter(), root, socket, boot)
    for path, gid, mode in ((root, 0, 0o755), (root / 'local-skills', 0, 0o755),
                            (root / 'skill-transfers', 0, 0o700), (root / 'studio-locks', 986, 0o2770),
                            (root / 'release-gate', 0, 0o755),
                            (socket, 10001, 0o750)):
        info = path.stat()
        assert info.st_uid == 0 and info.st_gid == gid and stat.S_IMODE(info.st_mode) == mode
    assert boot.read_bytes() == paths.TMPFILES_CONTENT and stat.S_IMODE(boot.stat().st_mode) == 0o644
    for name in ('workers', 'ingress'):
        assert not paths.gate_state(adapter(), name, root / 'release-gate')


def test_release_gate_rejects_tampering_and_persists_transitions(tmp_path):
    root, socket, boot = tmp_path / 'domestic', tmp_path / 'socket', tmp_path / 'boot.conf'
    u = adapter()
    paths.provision(u, root, socket, boot)
    gate = root / 'release-gate'
    paths.set_gate(u, 'workers', True, gate)
    assert paths.gate_state(u, 'workers', gate)
    assert not paths.gate_state(u, 'ingress', gate)
    paths.set_gate(u, 'workers', False, gate)
    (gate / 'workers').unlink()
    (gate / 'workers').symlink_to(gate / 'ingress')
    with pytest.raises(RuntimeError, match='identity'):
        paths.gate_state(u, 'workers', gate)


@pytest.mark.parametrize('case', ['symlink', 'unsafe_mode', 'existing_skill', 'boot_drift'])
def test_refuses_existing_unknown_paths_without_rewriting_them(tmp_path, case):
    root, socket, boot = tmp_path / 'domestic', tmp_path / 'socket', tmp_path / 'boot.conf'
    if case == 'symlink':
        (tmp_path / 'other').mkdir()
        root.symlink_to(tmp_path / 'other', target_is_directory=True)
    else:
        paths.provision(adapter(), root, socket, boot)
        if case == 'unsafe_mode': (root / 'local-skills').chmod(0o777)
        elif case == 'existing_skill': (root / 'local-skills' / 'unknown').write_text('preserve')
        else: boot.write_text('preserve')
    with pytest.raises(RuntimeError):
        paths.provision(adapter(), root, socket, boot)
    if case == 'existing_skill': assert (root / 'local-skills' / 'unknown').read_text() == 'preserve'
    if case == 'boot_drift': assert boot.read_text() == 'preserve'


def test_requires_both_native_identities_in_shared_group():
    valid = {name: {'user': 1001, 'group': 1001, 'extra_groups': [986]} for name in
             ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions')}
    paths.identities(valid)
    valid['hengxin-domestic-deletions']['extra_groups'] = []
    with pytest.raises(RuntimeError, match='cannot share'):
        paths.identities(valid)
