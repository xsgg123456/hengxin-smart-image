"""Domestic workspace names shared by request validation, permissions and ORM constraints."""
from types import MappingProxyType
from typing import Literal, get_args

NewProduct = Literal['camera', 'case', 'film', 'cable', 'earbud', 'accessory']
Replacement = Literal['product', 'scene', 'phone', 'edit']
WorkspaceName = NewProduct | Replacement

ARCHIVE_WORKSPACES = get_args(NewProduct)
WORKSPACES = MappingProxyType(dict.fromkeys(ARCHIVE_WORKSPACES, True) | dict.fromkeys(get_args(Replacement), False))
WORKSPACE_CHECK = f"workspace IN {tuple(WORKSPACES)}"
ARCHIVE_WORKSPACE_CHECK = f"workspace IN {ARCHIVE_WORKSPACES}"
