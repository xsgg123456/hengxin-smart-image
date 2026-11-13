"""Server-side boundaries for the five domestic workspaces.

The caller obtains a binding under the execution-admission lock and passes the
existing Skill freezer. Client-supplied Skill IDs are never authoritative.
"""
from collections.abc import Callable, Mapping
from types import MappingProxyType

from fastapi import HTTPException


WORKSPACES: Mapping[str, bool] = MappingProxyType({
    'camera': True,
    'case': True,
    'product': False,
    'scene': False,
    'phone': False,
})


def require_workspace(workspace: str) -> str:
    if workspace not in WORKSPACES:
        raise HTTPException(404, '工作台不存在')
    return workspace


def require_archive_workspace(workspace: str) -> None:
    require_workspace(workspace)
    if not WORKSPACES[workspace]:
        raise HTTPException(403, '产品替换工作台不支持归档')


def freeze_bound_skill(
    workspace: str,
    binding_id: str | None,
    requested_skill_id: str | None,
    freeze: Callable[[str], Mapping[str, object]],
) -> Mapping[str, object]:
    """Resolve an installed, enabled Skill from the trusted binding only.

    The caller must hold the same admission lock used by binding changes and
    keep the returned immutable snapshot in the submitted execution payload.
    """
    require_workspace(workspace)
    if requested_skill_id is not None:
        raise HTTPException(422, '当前工作台自动使用已绑定的 Skill')
    if not binding_id or not binding_id.strip():
        raise HTTPException(409, '该工作台暂不可用，请联系管理员配置')
    snapshot = freeze(binding_id)
    skill = snapshot.get('skill') if isinstance(snapshot, Mapping) else None
    if not isinstance(skill, Mapping) or skill.get('id') != binding_id:
        raise HTTPException(409, '该工作台的 Skill 不可用，请联系管理员配置')
    return snapshot
