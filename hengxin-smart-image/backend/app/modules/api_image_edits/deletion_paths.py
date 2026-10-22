"""Task-deletion adapter for the common private-workspace cleanup boundary."""
from pathlib import Path

from app.execution import cleanup_paths
from app.execution.cleanup_paths import inspect_fd, linked, tool_link  # compatibility exports


def clean(root, conversation_id):
    cleanup_paths.clean(Path(root).absolute() / 'api-edits', conversation_id)
