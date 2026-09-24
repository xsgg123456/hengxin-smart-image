"""Read literal imagegen arguments without evaluating JavaScript or exposing code."""
import json
import re

SPACE = re.compile(r'[ \t\v\f\r\n\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+')
TOKEN = re.compile(SPACE.pattern + r'|//[^\r\n\u2028\u2029]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|-?\d+(?:\.\d+)?|.', re.S)
IDENTIFIER = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?')
HELPERS = {'generatedImage', 'text'}
RESERVED_BINDINGS = set('await break case catch class const continue debugger default '
    'delete do else enum export extends false finally for function if import in '
    'instanceof let new null return super switch this throw true try typeof var '
    'void while with yield implements interface package private protected public '
    'static eval arguments tools'.split()) | HELPERS


def string_value(token):
    if len(token) < 2 or token[-1] != token[0]:
        raise ValueError('unterminated string')
    if token[0] == '"':
        return json.loads(token)
    if token[0] == '`' and '${' in token:
        raise ValueError('dynamic template')
    # Decode JS escapes without executing expressions; preserve Unicode text.
    body, output, index = token[1:-1], [], 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}
    while index < len(body):
        char = body[index]
        index += 1
        if char != '\\':
            if token[0] == "'" and char in '\r\n\u2028\u2029':
                raise ValueError('newline in string')
            output.append(char)
            continue
        char = body[index]
        index += 1
        if char in ('u', 'x'):
            count = 4 if char == 'u' else 2
            digits = body[index:index + count]
            if len(digits) != count or not re.fullmatch(r'[0-9a-fA-F]+', digits):
                raise ValueError('invalid escape')
            output.append(chr(int(digits, 16)))
            index += count
        elif char in escapes or char in "\\\"'`/$":
            if char == '0' and index < len(body) and body[index].isdigit():
                raise ValueError('legacy escape')
            output.append(escapes.get(char, char))
        else:
            raise ValueError('unsupported escape')
    return ''.join(output)


def literal(tokens, index, depth=0):
    if depth > 15:
        raise ValueError('nested literal')
    token = tokens[index]
    if token.startswith(('"', "'", '`')):
        return string_value(token), index + 1
    if token in ('null', 'true', 'false'):
        return {'null': None, 'true': True, 'false': False}[token], index + 1
    if NUMBER.fullmatch(token):
        return float(token), index + 1
    if token not in ('{', '['):
        raise ValueError('nonliteral expression')
    mapping = token == '{'
    result = {} if mapping else []
    end = '}' if mapping else ']'
    index += 1
    while tokens[index] != end:
        if mapping:
            key = tokens[index]
            if key.startswith(('"', "'")):
                key = string_value(key)
            elif not IDENTIFIER.fullmatch(key):
                raise ValueError('invalid property name')
            if tokens[index + 1] != ':' or key in result:
                raise ValueError('invalid property')
            index += 2
        value, index = literal(tokens, index, depth + 1)
        if mapping:
            result[key] = value
        else:
            result.append(value)
        if tokens[index] == end:
            break
        if tokens[index] != ',':
            raise ValueError('nonliteral expression')
        index += 1
    return result, index + 1


def image_calls(code):
    tokens = [t for t in TOKEN.findall(code) if not SPACE.fullmatch(t) and not t.startswith(('//', '/*'))]
    relevant = 'image_gen__imagegen' in tokens
    # Parse the entire program, not call-shaped substrings. Prior expressions can
    # fail/exit, and even trailing syntax errors prevent the whole exec from running.
    # This deliberately excludes ASI, dynamic expressions and multiple image calls.
    index, bindings, result_binding, call = 0, set(), None, None
    try:
        while index < len(tokens):
            if tokens[index] == ';':
                index += 1
                continue
            binding = None
            if tokens[index] in ('const', 'let'):
                binding = tokens[index + 1]
                if (call is not None or not IDENTIFIER.fullmatch(binding)
                        or binding in RESERVED_BINDINGS or binding in bindings
                        or tokens[index + 2] != '='):
                    raise ValueError('unsupported declaration')
                bindings.add(binding)
                index += 3
            if tokens[index] == 'await':
                index += 1
                if tokens[index:index + 4] != ['tools', '.', 'image_gen__imagegen', '(']:
                    raise ValueError('unsupported await')
            if tokens[index:index + 4] == ['tools', '.', 'image_gen__imagegen', '(']:
                if call is not None:
                    raise ValueError('multiple calls cannot prove later execution')
                call, index = literal(tokens, index + 4)
                if (tokens[index] != ')' or not isinstance(call, dict)
                        or not isinstance(call.get('prompt'), str)):
                    raise ValueError('incomplete arguments')
                result_binding = binding
                index += 1
            elif binding is not None:
                _, index = literal(tokens, index)
            elif (call is not None and result_binding is not None and tokens[index] in HELPERS
                    and tokens[index + 1:index + 4] == ['(', result_binding, ')']):
                index += 4
            else:
                raise ValueError('unsupported statement')
            if index < len(tokens):
                if tokens[index] != ';':
                    raise ValueError('explicit statement separator required')
                index += 1
    except (ValueError, IndexError, TypeError):
        return [], relevant
    return ([call] if call is not None else []), False
