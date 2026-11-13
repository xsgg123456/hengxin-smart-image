from uuid import uuid4

import pytest

from app.modules.domestic_studio import delivery_context
from test_studio_skill_cache import new_workspace


def test_private_receipt_can_restore_only_its_original_invocation(tmp_path):
    root = tmp_path / 'execution'
    workspace = new_workspace(root / 'domestic-studio')
    workspace.previous_session, workspace.native_cursor, workspace.baseline = None, {}, {}
    owner = delivery_context.identity(uuid4(), uuid4(), workspace.home.parent.name, workspace.control.name)
    delivery_context.remember(workspace, owner)
    delivery_context.remember(workspace, owner)
    restored = delivery_context.restore(root, owner)
    assert restored.work.samefile(workspace.work) and restored.control.samefile(workspace.control)
    wrong = owner | {'jobId': str(uuid4())}
    with pytest.raises(ValueError, match='ownership mismatch'):
        delivery_context.restore(root, wrong)
    with pytest.raises(ValueError, match='context changed'):
        delivery_context.remember(workspace, wrong)


def test_failed_or_missing_exit_cannot_be_treated_as_success(tmp_path):
    root = tmp_path / 'execution'
    workspace = new_workspace(root / 'domestic-studio')
    workspace.previous_session, workspace.native_cursor, workspace.baseline = None, {}, {}
    owner = delivery_context.identity(uuid4(), uuid4(), workspace.home.parent.name, workspace.control.name)
    delivery_context.remember(workspace, owner)
    restored = delivery_context.restore(root, owner)
    with pytest.raises(FileNotFoundError):
        delivery_context.success(restored)
    (restored.control / 'exit.json').write_text('{"exit_code": 1, "reason": null}', encoding='utf-8')
    with pytest.raises(ValueError, match='did not complete'):
        delivery_context.success(restored)
