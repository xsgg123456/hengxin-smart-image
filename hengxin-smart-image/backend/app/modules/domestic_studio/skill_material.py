"""Materialize a verified domestic snapshot using the shared Skill cache."""
from app.overseas.execution import skill_cache
from app.overseas.execution.skill_content import entry


def prepare(frozen, workspace, catalog):
    if not isinstance(frozen, dict):
        raise ValueError('Domestic Studio Skill snapshot missing')

    def describe(skill, _get_store, _workspace):
        package = catalog.frozen_package(skill)
        return package.name, {path: entry(path, content) for path, content in package.files.items()}, package.files.__getitem__

    skill_cache.prepare(frozen, workspace, None, describe_content=describe)
    workspace.use_skill = True
