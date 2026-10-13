"""Approved-list reconciliation / recovery; dry run unless --apply."""
from member_cli import main

if __name__ == '__main__':
    raise SystemExit(main('reconcile'))
