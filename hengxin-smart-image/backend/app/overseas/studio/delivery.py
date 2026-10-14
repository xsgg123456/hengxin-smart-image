"""Accept explicit final image references only; never discover draft files."""
from io import BytesIO
from pathlib import PurePosixPath
import re
import unicodedata
from types import SimpleNamespace
from urllib.parse import unquote

from fastapi import HTTPException
from markdown_it import MarkdownIt

from app.execution.delivery_markdown import _legacy_space_paths
from app.execution.diagnostics import _safe_read
from app.execution.final_delivery import _local_file
from app.execution.output_collector import OutputCollectionError, _root
from app.modules.files.validation import MAX_UPLOAD_BYTES, validate_image

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
NON_DELIVERY = re.compile(
    r'临时|草稿|初稿|工作稿|试验|测试图|中间(?:产物|文件|图片|图|结果|版本)|过程(?:文件|图片|图)|候选|'
    r'未交付|不交付|未(?:定稿|完成|完稿)|非正式|'
    r'\b(?:draft|temporary|intermediate|candidate|wip|experimental|experimentation|'
    r'preliminary|provisional|unfinished|incomplete|unapproved)\b|'
    r'\b(?:test(?:ing)?|trial|rough)[\s-]+(?:images?|pictures?|renders?|outputs?|files?|sketch(?:es)?)\b|'
    r'\b(?:testing[\s-]+only|for[\s-]+testing|work[\s-]+in[\s-]+progress|working[\s-]+copy)\b', re.I)
FORMAL = re.compile(r'正式(?:交付|成品|图片|图)|最终(?:交付|成品|结果|设计|图片|图)|'
                    r'交付(?:图片|结果|成品)|\b(?:final\s+(?:delivery|images?|results?|designs?)|deliverables)\b', re.I)
FILE_PROSE = re.compile(r'[/\\]|\.(?:png|jpe?g|webp)\b', re.I)
DECLINED = re.compile(
    r'(?:不|非|未|没|勿|禁止)[^。！？\n.!?]{0,32}(?:正式|最终|交付|成品|定稿)|'
    r'仅(?:供|作|用于|用作)?(?:预览|参考|演示|测试|试验|实验)|待(?:确认|审核|定稿)|预览稿|样稿|试做|试作|实验图|'
    r'\b(?:not|never|no|non|cannot|can[’\x27]t|isn[’\x27]t|aren[’\x27]t|wasn[’\x27]t|weren[’\x27]t)'
    r'(?:[\s-]+[\w’\x27]+){0,6}[\s-]+(?:final|deliver\w*|finished|approved)\b|'
    r'\b(?:preview[\s-]+only|for[\s-]+preview|pending[\s-]+approval)\b', re.I)


def formal_prose(token):
    """File names, image captions, link labels and code cannot declare delivery."""
    parts, link_depth = [], 0
    for child in token.children or []:
        if child.type == 'link_open':
            link_depth += 1
        elif child.type == 'link_close':
            link_depth -= 1
        elif not link_depth and child.type == 'text' and not FILE_PROSE.search(child.content):
            parts.append(child.content)
        elif child.type in ('softbreak', 'hardbreak'):
            parts.append(' ')
    return bool(FORMAL.search(''.join(parts)))


def visible_text(token):
    """Image alt is an inline subtree too, not an already plain text string."""
    if token.children is not None:
        return ''.join(visible_text(child) for child in token.children)
    if token.type in ('text', 'text_special', 'code_inline', 'image'):
        return token.content
    return ' ' if token.type in ('softbreak', 'hardbreak') else ''


def description_labels(token):
    """Visit descriptions at every nesting level, including an image inside alt."""
    yield token.content
    yield visible_text(token)
    title = token.attrGet('title')
    if title:
        yield title
        for part in MarkdownIt('commonmark').parseInline(title):
            yield from description_labels(part)
    for child in token.children or []:
        yield from description_labels(child)


def non_delivery(token):
    """Apply the same negation rules to visible prose, alt and title labels."""
    labels = list(description_labels(token))
    # Conservatively recognize negation even when literal decoration or invisible
    # formatting surrounds it. This affects eligibility only, never saved text.
    normalized = [''.join(char for char in unicodedata.normalize('NFKC', label)
                          if char not in '*_~`' and unicodedata.category(char) != 'Cf')
                  for label in labels]
    return any(NON_DELIVERY.search(label) or DECLINED.search(label) for label in labels + normalized)


def delivery_blocks(tokens):
    """Keep non-delivery scope across blank lines and nested neutral headings.

    Inspect complete sections before yielding links, so a trailing draft notice
    also excludes the preceding unqualified previews. Explicit formal sections
    may start a new scope, but never override a non-delivery parent heading.
    """
    sections, parents, depth = [], [], None
    current = dict(blocked=False, tokens=[])
    sections.append(current)
    for token in tokens:
        if token.type == 'heading_open':
            depth = int(token.tag[1:])
        if token.type != 'inline':
            continue
        # A negated delivery declaration always wins over the formal words inside it.
        negative = non_delivery(token)
        formal = not negative and formal_prose(token)
        if depth is not None:
            while parents and parents[-1][0] >= depth:
                parents.pop()
            parents.append((depth, negative))
            blocked = any(value for _, value in parents) or (current['blocked'] and not formal)
            current = dict(blocked=blocked, tokens=[])
            sections.append(current)
            depth = None
        elif negative:
            current['blocked'] = True
        elif formal and not any(value for _, value in parents):
            current = dict(blocked=False, tokens=[])
            sections.append(current)
        current['tokens'].append(token)
    return [token for section in sections if not section['blocked'] for token in section['tokens']]


def references(text):
    """A link in the completed final answer is delivery, not a tool-side file."""
    parser = MarkdownIt('commonmark')
    parser.validateLink = lambda _url: True  # Files are validated below, not fetched.
    for token in delivery_blocks(parser.parse(_legacy_space_paths(text))):
        for child in token.children or []:
            target = (child.attrGet('src') if child.type == 'image' else
                      child.attrGet('href') if child.type == 'link_open'
                      and child.markup != 'autolink' else None)
            if target is None:
                continue
            try:
                decoded = unquote(target, errors='strict')
            except UnicodeError:
                yield target, None
                continue
            logical = decoded.removeprefix('sandbox:')
            if PurePosixPath(logical).suffix.lower() in EXTENSIONS:
                yield decoded, logical
            elif child.type == 'image':
                yield decoded, None


def collect_delivery(workspace, summary):
    """Return valid formal images and warnings without discarding public text."""
    if not summary.turn_completed or summary.error or not summary.final_text:
        return [], []
    delivered, warnings, seen = [], [], set()
    try:
        root = _root(workspace.home / '.codex', summary.session_id)
        links = list(references(summary.final_text))
    except (ValueError, OSError, TypeError, RecursionError):
        return [], ['正式交付图片的引用无法读取，文字回复已保留。']
    for target, logical in links:
        try:
            if logical is None:
                raise OutputCollectionError('invalid_image_reference')
            path, _ = _local_file(logical, workspace.work, workspace.home / '.codex',
                                  root, workspace.baseline)
            identity = path.resolve()
            if identity in seen:
                continue
            data = _safe_read(path, MAX_UPLOAD_BYTES, allow_windows_fallback=True)
            image = validate_image(SimpleNamespace(file=BytesIO(data), filename=path.name,
                                                    content_type=None))
            delivered.append((target, image))
            seen.add(identity)
        except (OutputCollectionError, HTTPException, OSError, ValueError):
            warnings.append('一张正式交付图片未通过文件或归属校验，文字回复已保留。')
    return delivered, warnings
