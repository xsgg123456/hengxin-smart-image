import copy

import pytest

import joint_studio_packages as packages


def manifests():
    old = {'files': {'backend/pyproject.toml': 'same', 'backend/uv.lock': 'same',
                     'backend/migrations/env.py': 'before', 'backend/migrations/versions/0032_existing.py': 'old'},
           'runtime_inputs': {'codex': 'same'}}
    new = copy.deepcopy(old)
    new['files']['backend/migrations/env.py'] = 'after'
    new['files'].update({name: 'new' for name in packages.MIGRATIONS})
    return old, new


def test_only_approved_additive_migration_inputs_are_allowed():
    old, new = manifests()
    packages.check_inputs(old, new)


@pytest.mark.parametrize('case', ['missing', 'existing_revision_changed', 'dependency_changed',
                                   'unexpected_migration', 'runtime_changed', 'already_present'])
def test_other_schema_and_dependency_changes_are_rejected(case):
    old, new = manifests()
    if case == 'missing': new['files'].pop(next(iter(packages.MIGRATIONS)))
    elif case == 'existing_revision_changed': new['files']['backend/migrations/versions/0032_existing.py'] = 'changed'
    elif case == 'dependency_changed': new['files']['backend/uv.lock'] = 'changed'
    elif case == 'unexpected_migration': new['files']['backend/migrations/versions/0044_extra.py'] = 'new'
    elif case == 'runtime_changed': new['runtime_inputs']['codex'] = 'changed'
    else: old['files'][next(iter(packages.MIGRATIONS))] = 'old'
    with pytest.raises(RuntimeError):
        packages.check_inputs(old, new)


def test_revision_chain_must_be_contiguous(tmp_path):
    folder = tmp_path / 'backend/migrations/versions'
    folder.mkdir(parents=True)
    for index, filename in enumerate(packages.VERSIONS):
        (folder / filename).write_text(f"revision = '{33 + index:04d}'\ndown_revision = '{32 + index:04d}'\n")
    packages.check_revisions(tmp_path)
    (folder / packages.VERSIONS[-1]).write_text("revision='0043'\ndown_revision='0001'\n")
    with pytest.raises(RuntimeError, match='revision chain'):
        packages.check_revisions(tmp_path)
