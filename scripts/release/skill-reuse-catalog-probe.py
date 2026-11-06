"""Offline real-installed Skill probe; writes only a new isolated scratch conversation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


def probe(skill_root, scratch, code_root):
    from app.execution.workspace import prepare_workspace
    from app.overseas.execution import materials, skill_cache
    from app.overseas.management import installed_catalog as catalog
    from app.overseas.management.installed_tree import read_file
    from app.overseas.studio import context_workspace

    if Path(skill_cache.__file__).resolve() != code_root / 'app/overseas/execution/skill_cache.py':
        raise ValueError('Probe imported wrong installed code')
    if scratch.exists() or not scratch.is_absolute() or scratch.is_symlink():
        raise ValueError('Probe requires a fresh absolute scratch directory')
    for parent in scratch.parents:
        if parent.is_symlink():
            raise ValueError('Probe scratch cannot traverse links')
    release = json.loads(read_file(skill_root / 'current.json', protected=True))['release']
    _, manifest = catalog.release_manifest(skill_root, release, protected=True)
    items = manifest['items']
    if not items:
        raise ValueError('No real installed Skill to verify')
    item = next((v for v in items if 'walmart' in v['name'].lower()), items[0])
    skill = dict(name=item['name'], checksum=item['checksum'], installedRelease=release)
    # Retain real source validation and permissions; do not load production credentials/config.
    catalog.root_config = lambda: (skill_root, True)
    scratch.mkdir(mode=0o700)
    conversation = uuid4()

    def prepare():
        workspace = prepare_workspace(scratch, conversation, uuid4(), None, copy_auth=False)
        context_workspace.prepare(workspace, [], [], lambda _: (_ for _ in ()).throw(
            ValueError('Unexpected attachment download')))
        materials.prepare(SimpleNamespace(payload={'skill': skill}), workspace)
        return workspace

    first = prepare()
    session = first.home / '.codex' / 'sessions' / 'probe-history.jsonl'
    session.parent.mkdir()
    session.write_bytes(b'isolated continuity sentinel\n')
    artifact = first.work / 'probe-work.txt'
    artifact.write_bytes(b'isolated work sentinel\n')
    original = {p: p.read_bytes() for p in (session, artifact)}

    def fingerprint():
        return {p.relative_to(first.local_skill).as_posix():
                (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_ino, p.stat().st_mtime_ns)
                for p in first.local_skill.rglob('*') if p.is_file()}

    before = fingerprint()
    second = prepare()
    if (first.local_skill != second.local_skill or fingerprint() != before
            or any(p.read_bytes() != raw for p, raw in original.items())
            or len(list(first.local_skill.parent.parent.iterdir())) != 1
            or (first.round_work / 'skills').exists() or (second.round_work / 'skills').exists()):
        raise ValueError('Real Skill reuse or history preservation failed')
    return dict(result='REAL_INSTALLED_SKILL_REUSE_PASS', uid=os.getuid(),
                skill=item['name'], files=len(before),
                uniqueBytes=sum(p.stat().st_size for p in first.local_skill.rglob('*') if p.is_file()),
                rounds=2, contentCopies=1, historyPreserved=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--code-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.skill_root, args.scratch, args.code_root.resolve())))
