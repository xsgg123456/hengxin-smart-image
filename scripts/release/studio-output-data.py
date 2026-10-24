"""Read-only invariants for the additive overseas_0022 output table."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('studio_output_data_base',
    Path(__file__).with_name('overseas-studio-sessions-data.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TABLE, base.ADDED = 'overseas_studio_output_files', {}
TABLE = base.TABLE


def before(sql):
    names = base.tables(sql)
    assert TABLE not in names, 'Output table already exists'
    return dict(tables=names, columns=base.columns(sql), rows=base.original_rows(sql))


def verify(sql, baseline):
    assert set(base.tables(sql)) == set(baseline['tables']) | {TABLE}, 'Unexpected migrated tables'
    assert [row for row in base.columns(sql) if row['table_name'] != TABLE] == baseline['columns'], 'Existing columns changed'
    assert base.original_rows(sql) == baseline['rows'], 'Original business data changed'
    assert sql('SELECT count(*) FROM ' + TABLE) == '0', 'Output migration inserted business data'
