"""Narrow canonicalization of PostgreSQL CHECK array cast deparser output."""
import re

# Accept only ordinary SQL string literals and the exact observed type/spelling.
# Doubled quotes and commas inside a literal are consumed as part of that token.
LITERAL = r"'(?:''|[^'\\])*'::character varying"
ARRAY_CAST = re.compile(r"\(ARRAY\[(?P<items>" + LITERAL + r"(?:, " + LITERAL
                        + r")*)\]\)::text\[\](?![\w$\[])")
ITEM = re.compile(LITERAL)
QUOTED = re.compile(r"'(?:''|[^'\\])*'|\"(?:\"\"|[^\"\\])*\"")


def constraint_definition(definition):
    """Preserve all text except varchar-literal array -> text[] cast placement.

    PostgreSQL 16 section 4.2.12 documents array-constructor casting as applying
    the cast to each element: https://www.postgresql.org/docs/16/sql-expressions.html
    No general SQL normalization is attempted. Unsupported quoting/comments or
    malformed candidate arrays keep the entire original definition unchanged.
    """
    if not definition.startswith('CHECK ('):
        return definition
    result, cursor = [], 0
    while cursor < len(definition):
        if definition.startswith('(ARRAY[', cursor):
            match = ARRAY_CAST.match(definition, cursor)
            if match is None:
                return definition
            # Full-list regex above guarantees these tokens consume the list.
            items = [item.group() for item in ITEM.finditer(match['items'])]
            result.append('ARRAY[' + ', '.join('(' + item + ')::text' for item in items) + ']')
            cursor = match.end()
        elif definition[cursor] in "'\"":
            match = QUOTED.match(definition, cursor)
            if match is None:
                return definition
            result.append(match.group())
            cursor = match.end()
        elif definition[cursor] in '$\\' or definition.startswith(('--', '/*'), cursor):
            return definition
        else:
            result.append(definition[cursor])
            cursor += 1
    return ''.join(result)
