"""Markdown structure determines references; prose numbering determines slots."""
import re
from pathlib import PurePosixPath
from urllib.parse import unquote

from markdown_it import MarkdownIt

from app.execution.output_collector import OutputCollectionError

_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
_DIGITS = r'[0-9零一二三四五六七八九十]+'
_NUMBER = re.compile(r'(?:主图|图片|图)\s*[（(]?\s*(' + _DIGITS + r')|第\s*(' + _DIGITS + r')\s*张')
_ORDERED = re.compile(r'^(' + _DIGITS + r')\s*[.、)）]\s*')


def _number(value: str) -> int:
    if value.isascii() and value.isdecimal():
        return int(value)
    digits = dict(zip('零一二三四五六七八九', range(10)))
    if value in digits:
        return digits[value]
    parts = value.split('十')
    if len(parts) == 2 and all(not part or part in digits for part in parts):
        return digits.get(parts[0], 1) * 10 + digits.get(parts[1], 0)
    raise OutputCollectionError('invalid_final_reply')


def _numbers(text: str) -> set[int]:
    numbers = {_number(a or b) for a, b in _NUMBER.findall(text)}
    plain = text.strip(' *()（）')
    if re.fullmatch(_DIGITS, plain):
        numbers.add(_number(plain))
    return numbers


def _context_numbers(prefix: str) -> set[int]:
    # Read the nearest numbered heading/list between this and the prior link.
    # Suffixes and intervening explanation do not erase an explicit image number.
    for line in reversed(prefix.splitlines()):
        line = line.strip()
        heading = line.startswith('#')
        clean = re.sub(r'^#{1,6}\s*', '', line).strip('* ')
        ordered = _ORDERED.match(clean)
        if ordered:
            return {_number(ordered[1])} | _numbers(clean[ordered.end():])
        if _NUMBER.match(clean) or heading:
            return _numbers(clean)
    return set()



def _legacy_space_paths(text: str) -> str:
    """Retain the CLI's historical bare paths with spaces as angle destinations.

    This only normalizes link syntax; the Markdown parser still excludes code,
    escaped examples, and reference definitions from delivered content.
    """
    pattern = re.compile(r'(?<!\\)(!?\[[^\[\]\n]*\])\(')
    cursor = 0
    result = []
    for match in pattern.finditer(text):
        if match.start() < cursor:
            continue
        start = end = match.end()
        depth = 1
        while end < len(text) and text[end] != '\n':
            if text[end] == '\\':
                end += 2
                continue
            if text[end] == '(':
                depth += 1
            elif text[end] == ')':
                depth -= 1
                if not depth:
                    break
            end += 1
        if depth:
            continue
        target = text[start:end]
        if target.startswith('<') or not any(c.isspace() for c in target):
            continue
        destination = re.sub(r'\s+["\'][^"\']*["\']$', '', target).strip()
        if PurePosixPath(destination).suffix.lower() not in _EXTENSIONS:
            continue
        result.append(text[cursor:match.end()])
        result.append('<' + destination + '>' + target[len(destination):] + ')')
        cursor = end + 1
    result.append(text[cursor:])
    return ''.join(result)


def delivery_links(text: str) -> list[tuple[str, str, int | None]]:
    parser = MarkdownIt('commonmark')
    # File security belongs to _local_file, not a renderer's URL whitelist.
    parser.validateLink = lambda url: True
    tokens = parser.parse(_legacy_space_paths(text))
    result = []
    context = ''
    for token in tokens:
        if token.type == 'list_item_open' and token.info:
            context += '\n' + token.info + '. '
        if token.type == 'heading_open':
            context += '\n# '
        if token.type != 'inline':
            continue
        children = token.children or []
        index = 0
        inside_link = False
        while index < len(children):
            child = children[index]
            if child.type == 'image':
                label, target = child.content, child.attrGet('src')
            elif child.type == 'link_open' and child.markup != 'autolink':
                close = index + 1
                while close < len(children) and children[close].type != 'link_close':
                    close += 1
                label = ''.join(c.content for c in children[index + 1:close]
                                if c.type in ('text', 'image'))
                target = child.attrGet('href')
                inside_link = True
                # A linked preview and its enclosing download can both be delivered.
            else:
                if child.type == 'link_close':
                    inside_link = False
                if not inside_link and child.type in ('text', 'softbreak', 'hardbreak'):
                    context += child.content or '\n'
                index += 1
                continue
            try:
                target = unquote(target or '', errors='strict')
            except UnicodeError:
                raise OutputCollectionError('invalid_final_reply') from None
            if PurePosixPath(target).suffix.lower() not in _EXTENSIONS:
                if child.type == 'image':
                    raise OutputCollectionError('invalid_output_image')
                index += 1
                continue
            numbers = _context_numbers(context) | _numbers(label)
            if len(numbers) > 1:
                raise OutputCollectionError('invalid_final_reply')
            result.append((label, target, next(iter(numbers), None)))
            context = ''
            index += 1
        context += '\n'
    return result
