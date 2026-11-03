"""Restore comparison retains schema semantics despite PostgreSQL cast rewrites."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('sku_runtime', Path(__file__).with_name('sku-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def check(values, distributed=False, column='kind', suffix=''):
    literals = ["'" + value.replace("'", "''") + "'::character varying" for value in values]
    array = ('ARRAY[' + ', '.join('(' + item + ')::text' for item in literals) + ']'
             if distributed else '(ARRAY[' + ', '.join(literals) + '])::text[]')
    return 'CHECK (((' + column + ')::text = ANY (' + array + ')))' + suffix


class SchemaRestoreTests(unittest.TestCase):
    def test_dump_cast_rewrite_preserves_escaped_literals_and_flags(self):
        values = ['analysis', 'two,parts', "single'quote", '(nested(paren))']
        for column in ('kind', '"odd""column"'):
            for suffix in ('', ' NO INHERIT', ' NOT VALID', ' NO INHERIT NOT VALID'):
                with self.subTest(column=column, suffix=suffix):
                    canonical = check(values, True, column, suffix)
                    self.assertEqual(r.normalized_constraint(check(values, False, column, suffix)), canonical)
                    self.assertEqual(r.normalized_constraint(canonical), canonical)

    def schema_hash(self, definition, column_hash='all-column-fields', index='CREATE UNIQUE INDEX idx ON t (kind)'):
        responses = [column_hash, json.dumps([['t', 'idx', index]]), json.dumps([['t', 'ck', definition]])]
        with patch.object(r, 'sql', side_effect=responses):
            return r.columns(('database',))

    def test_restore_equivalence_keeps_all_other_schema_drift_visible(self):
        original = check(['analysis', 'generation'])
        expected = self.schema_hash(original)
        self.assertEqual(expected, self.schema_hash(check(['analysis', 'generation'], True)))
        variants = [check(['analysis']), check(['analysis', 'generation', 'unexpected']),
                    check(['generation', 'analysis']), check(['analysis', 'generation'], column='status'),
                    check(['analysis', 'generation'], suffix=' NOT VALID'),
                    check(['analysis', 'generation'], suffix=' NO INHERIT'),
                    original.replace('= ANY', '<> ALL'), original.replace('character varying', 'character varying(2)'),
                    'UNIQUE (kind)', 'FOREIGN KEY (kind) REFERENCES other(kind)',
                    'FOREIGN KEY (kind) REFERENCES other(kind) ON DELETE CASCADE']
        for definition in variants:
            with self.subTest(definition=definition):
                self.assertNotEqual(expected, self.schema_hash(definition))
        self.assertNotEqual(expected, self.schema_hash(original, column_hash='type-null-default-or-other-field-changed'))
        self.assertNotEqual(expected, self.schema_hash(original, index='CREATE INDEX idx ON t (kind)'))

    def test_unknown_expression_cast_and_quoted_lookalikes_are_not_rewritten(self):
        original = check(['analysis', 'generation'])
        variants = [original.replace('character varying', 'character(10)'),
                    original.replace("'analysis'::character varying", 'some_function()'),
                    original.replace('::text[]', '::integer[]'),
                    original.replace(')))', ')) AND enabled)'),
                    check(['back\\slash']),
                    "CHECK (note = '" + original.replace("'", "''") + "')"]
        for definition in variants:
            with self.subTest(definition=definition):
                self.assertEqual(r.normalized_constraint(definition), definition)


if __name__ == '__main__':
    unittest.main()
