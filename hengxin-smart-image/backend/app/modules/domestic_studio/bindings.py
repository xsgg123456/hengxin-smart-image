"""Atomic domestic workspace-to-Skill bindings.

Catalog validation and immutable installation snapshots are delegated to the
Skill catalog; all callers must share the execution admission lock.
"""
from collections.abc import Callable, Mapping

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.execution.models import ExecutionGate
from .models import WorkspaceBinding
from .policy import WORKSPACES, freeze_bound_skill, require_workspace


def lock_admission(session: Session) -> None:
    # REPEATABLE READ keeps the earlier transaction snapshot after waiting on
    # the gate; refreshing the ORM object alone would still see stale bindings.
    if session.get_bind().dialect.name == 'postgresql':
        driver = session.connection().connection.driver_connection
        if getattr(driver, 'autocommit', None) is not False:
            raise RuntimeError('Domestic studio bindings require transactional connections')
        if session.scalar(text('SHOW transaction_isolation')) != 'read committed':
            raise RuntimeError('Domestic studio bindings require READ COMMITTED transactions')
    if session.scalar(select(ExecutionGate).where(ExecutionGate.id == 1).with_for_update()) is None:
        raise RuntimeError('Execution gate missing; apply domestic migrations')


def read_bindings(session: Session) -> dict[str, str | None]:
    rows = session.scalars(select(WorkspaceBinding).execution_options(populate_existing=True)).all()
    values = {row.workspace: row.skill_id for row in rows}
    return {workspace: values.get(workspace) for workspace in WORKSPACES}


def save_bindings(session: Session, requested: Mapping[str, str | None],
                  verify_enabled: Callable[[str], None], *,
                  expected: Mapping[str, str | None]) -> dict[str, str | None]:
    """Validate all five bindings before making any changes; caller commits."""
    if set(requested) != set(WORKSPACES) or set(expected) != set(WORKSPACES):
        raise HTTPException(422, '请提交全部五个工作台的绑定')
    lock_admission(session)
    if read_bindings(session) != dict(expected):
        raise HTTPException(409, '工作台绑定已被其他管理员修改，请重新加载后核对')
    for skill_id in requested.values():
        if skill_id is not None:
            if (not isinstance(skill_id, str) or not skill_id.strip()
                    or skill_id != skill_id.strip() or len(skill_id) > 100):
                raise HTTPException(422, 'Skill 标识无效')
            verify_enabled(skill_id)
    for workspace, skill_id in requested.items():
        row = session.scalar(select(WorkspaceBinding).where(
            WorkspaceBinding.workspace == workspace).execution_options(populate_existing=True))
        if skill_id is None:
            if row is not None:
                session.delete(row)
        elif row is None:
            session.add(WorkspaceBinding(workspace=workspace, skill_id=skill_id))
        else:
            row.skill_id = skill_id
    session.flush()
    return read_bindings(session)


def assert_unbound(session: Session, skill_id: str) -> None:
    """Call in the same transaction before disabling or removing a package."""
    lock_admission(session)
    row = session.scalar(select(WorkspaceBinding.workspace).where(
        WorkspaceBinding.skill_id == skill_id).limit(1))
    if row is not None:
        raise HTTPException(409, '此 Skill 正被工作台使用，请先更换或解除绑定')


def freeze_for_send(session: Session, workspace: str, requested_skill_id: str | None,
                    freeze: Callable[[str], Mapping[str, object]]) -> Mapping[str, object]:
    """Call while creating the execution record; caller commits the snapshot."""
    require_workspace(workspace)
    lock_admission(session)
    binding = session.scalar(select(WorkspaceBinding).where(
        WorkspaceBinding.workspace == workspace).execution_options(populate_existing=True))
    return freeze_bound_skill(workspace, binding.skill_id if binding else None,
                              requested_skill_id, freeze)
