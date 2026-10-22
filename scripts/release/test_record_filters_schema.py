"""Reject schema drift while accepting the proven PostgreSQL cast reparse."""
import copy
import json

import pytest
from test_record_filters_release import module

n = module('domestic-record-filters-schema')
v = module('domestic-record-filters-verify')
VALUES = ['pending', 'approved', 'rejected', 'withdrawn']


def forms(values=VALUES):
    items = ["'" + value.replace("'", "''") + "'::character varying" for value in values]
    prefix, suffix = 'CHECK (((status)::text = ANY (', ')))'
    return (prefix + '(ARRAY[' + ', '.join(items) + '])::text[]' + suffix,
            prefix + 'ARRAY[' + ', '.join('(' + item + ')::text' for item in items) + ']' + suffix)


BEFORE, AFTER = forms()


@pytest.mark.parametrize('values', [VALUES, [''], ['a,b', "it's approved"], ['a', 'a'],
                                  ['a])::text[]', '中文', ' spaced ']])
def test_exact_cast_forms_equal_preserving_literal_tokens(values):
    before, after = forms(values)
    assert n.constraint_definition(before) == after
    assert n.constraint_definition(after) == after


@pytest.mark.parametrize('values', [VALUES[::-1], ['pending'], VALUES + ['extra'],
                                  VALUES + ['pending'], ['pending', 'approved', 'rejected', 'changed'],
                                  ['a,b'], ['a', 'b'], ["it's approved"]])
def test_enum_values_order_and_duplicates_remain_different(values):
    assert n.constraint_definition(forms(values)[0]) != n.constraint_definition(BEFORE)


@pytest.mark.parametrize('old,new', [('status', 'role'), (' = ANY ', ' <> ANY '),
                                  (' = ANY ', ' = ALL '), ('::text =', '::varchar ='),
                                  ('character varying', 'character'),
                                  ('character varying', 'character varying(10)'),
                                  ('::text[]', '::varchar[]'), ('CHECK (', 'CHECK ( '),
                                  ('approved', 'APPROVED')])
def test_column_operator_cast_type_and_external_text_drift_retained(old, new):
    assert n.constraint_definition(BEFORE.replace(old, new)) != n.constraint_definition(BEFORE)


@pytest.mark.parametrize('fragment', [
    '(ARRAY[])::text[]', "(ARRAY['a'::character varying,])::text[]",
    "(ARRAY['a'::character varying, 'unterminated::character varying])::text[]",
    "(ARRAY['a'::character varying, NULL::character varying])::text[]",
    "(ARRAY['a'::character varying, fn()::character varying])::text[]",
    "(ARRAY['a'::character varying,'b'::character varying])::text[]",
    "(ARRAY['a'::character varying,  'b'::character varying])::text[]",
    "(ARRAY[E'a\\n'::character varying])::text[]",
    "(ARRAY['a\\b'::character varying])::text[]",
    "(ARRAY['a'::character varying])::text[][]",
    "(ARRAY['a'::character varying])::text[]wrong",
    "(ARRAY['a'::character varying])::varchar[]",
    "(ARRAY['a'::character varying])::text[] /* comment */",
])
def test_unsupported_or_malformed_candidate_remains_exact(fragment):
    definition = 'CHECK (status = ANY (' + fragment + '))'
    assert n.constraint_definition(definition) == definition


@pytest.mark.parametrize('wrapper', ["CHECK (note = '{}')", 'CHECK ("{}" IS NOT NULL)',
                                    'CHECK (note = $$ {} $$)', 'UNIQUE ({})'])
def test_array_text_inside_quotes_or_non_check_is_untouched(wrapper):
    raw = "(ARRAY['a'::character varying])::text[]"
    if wrapper == "CHECK (note = '{}')":
        raw = raw.replace("'", "''")
    definition = wrapper.format(raw)
    assert n.constraint_definition(definition) == definition


def test_multiple_supported_arrays_keep_all_external_text():
    before = BEFORE[:-1] + ' AND ' + forms(['member', 'admin'])[0][7:] + ' NOT VALID'
    after = AFTER[:-1] + ' AND ' + forms(['member', 'admin'])[1][7:] + ' NOT VALID'
    assert n.constraint_definition(before) == after


def test_duplicate_and_quoted_comma_not_collapsed_or_split():
    assert n.constraint_definition(forms(['a', 'a'])[0]) != n.constraint_definition(forms(['a'])[0])
    assert n.constraint_definition(forms(['a,b'])[0]) != n.constraint_definition(forms(['a', 'b'])[0])
    assert n.constraint_definition(forms(["a'b"])[0]) != n.constraint_definition(forms(['ab'])[0])


def test_state_normalizes_only_constraint_definitions(monkeypatch):
    structure = {'columns': [{'column_default': BEFORE}], 'indexes': [{'indexdef': BEFORE}],
                 'constraints': [{'relation': 'receipts', 'name': 'status_check', 'definition': BEFORE},
                                 {'relation': 'receipts', 'name': 'receipts_pkey', 'definition': 'PRIMARY KEY (id)'}]}
    columns = {'receipts': ['id', 'status']}
    def query(_database, sql):
        if sql == v.SCHEMA:
            return json.dumps(structure)
        if 'FROM pg_tables' in sql:
            return 'receipts'
        return '2:full-row-fingerprint'
    monkeypatch.setattr(v.b, 'query', query)
    monkeypatch.setattr(v.s.p, 'columns', lambda _: columns)
    expected = copy.deepcopy(structure)
    expected['constraints'][0]['definition'] = AFTER
    assert v.state(('db', 'user', 'name')) == {
        'rows': {'receipts': '2:full-row-fingerprint'}, 'schema': expected, 'columns': columns}
    assert structure['constraints'][0]['definition'] == BEFORE
