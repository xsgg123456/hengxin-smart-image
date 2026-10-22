"""Retention adapter for the common private-workspace cleanup boundary."""
from app.execution import cleanup_paths


def clean(root, resource_id, cache_only=False):
    cleanup_paths.clean(root, resource_id, cache_only=cache_only)
