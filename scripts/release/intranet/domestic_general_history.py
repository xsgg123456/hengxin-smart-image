"""Preserve all studio rows while introducing one new product workspace."""
import domestic_workspaces_history as workspaces


def capture(u):
    workspaces.check_constraints(u, expanded=True)
    return workspaces.rows(u)


def verify(u, expected):
    products = workspaces.OLD_PRODUCTS | workspaces.NEW_PRODUCTS | {'general'}
    workspaces.check_values(u, products, workspaces.OLD_REPLACEMENTS | {'edit'})
    if workspaces.rows(u) != expected:
        raise RuntimeError('Domestic historical rows changed during general workspace migration')
