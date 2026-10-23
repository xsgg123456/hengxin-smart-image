"""Extract only explicitly displayed native image-generation evidence."""
import base64
import binascii
import hashlib
from pathlib import Path, PurePosixPath

from .native_rollout import locate, records, session, snapshot

MAX_IMAGES = 100


def _digest(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Invalid native image data')
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Invalid native image encoding') from None
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Native image is not PNG')
    return hashlib.sha256(data).hexdigest()


def _path(value, session_id):
    prefix = f'/home/runner/.codex/generated_images/{session_id}/'
    if (not isinstance(value, str) or not value.startswith(prefix)
            or '\\' in value or any(ord(c) < 32 for c in value)
            or any(part in ('', '.', '..') for part in value[len(prefix):].split('/'))
            or str(PurePosixPath(value)) != value or not value.endswith('.png')):
        raise ValueError('Invalid native image path')
    return value


def _text(item):
    content = item.get('content')
    if not isinstance(content, list):
        raise ValueError('Invalid native final message')
    texts = []
    for block in content:
        if not isinstance(block, dict):
            raise ValueError('Invalid native final content')
        if block.get('type') == 'Text':
            if not isinstance(block.get('text'), str):
                raise ValueError('Invalid native final text')
            texts.append(block['text'])
    return ''.join(texts)


class _Turn:
    def __init__(self, turn_id, session_id, targets):
        self.id = turn_id
        self.session = session_id
        self.targets = targets
        self.generated = {}
        self.paths = set()
        self.displayed = set()
        self.final = None
        self.image_count = 0

    def check_ids(self, payload):
        for name, expected in [('turn_id', self.id), ('thread_id', self.session)]:
            if name in payload and payload[name] != expected:
                raise ValueError('Native rollout turn or thread mismatch')

    def item(self, payload):
        self.check_ids(payload)
        item = payload.get('item')
        if not isinstance(item, dict):
            raise ValueError('Invalid native completed item')
        if item.get('type') == 'Extension' and item.get('kind') == 'image_gen.generation':
            if (payload.get('turn_id') != self.id or payload.get('thread_id') != self.session
                    or item.get('status') != 'completed' or item.get('failure') is not None):
                raise ValueError('Native image generation failed or has no turn identity')
            path = _path(item.get('savedPath'), self.session)
            checksum = _digest(item.get('result'))
            self.image_count += 1
            if self.image_count > MAX_IMAGES or path in self.paths:
                raise ValueError('Too many or ambiguous native images')
            self.paths.add(path)
            # Keep at most 100 digests; never retain image data or reasoning text.
            if self.targets is None or path in self.targets:
                self.generated[path] = checksum
        if item.get('type') == 'AgentMessage' and item.get('phase') == 'final_answer':
            if self.final is not None:
                raise ValueError('Ambiguous native final message')
            self.final = _text(item)

    def output(self, payload):
        metadata = payload.get('internal_chat_message_metadata_passthrough')
        blocks = payload.get('output')
        if not isinstance(blocks, list):
            return
        for block in blocks:
            if not isinstance(block, dict) or block.get('type') != 'input_image':
                continue
            if not isinstance(metadata, dict) or metadata.get('turn_id') != self.id:
                raise ValueError('Native displayed image turn mismatch')
            self.check_ids(metadata)
            value = block.get('image_url')
            if not isinstance(value, str) or not value.startswith('data:image/png;base64,'):
                continue
            self.displayed.add(_digest(value.removeprefix('data:image/png;base64,')))
            if len(self.displayed) > MAX_IMAGES:
                raise ValueError('Too many native displayed images')

    def complete(self, payload):
        self.check_ids(payload)
        if (payload.get('turn_id') != self.id or self.final is None
                or payload.get('last_agent_message') != self.final
                or payload.get('error') is not None or payload.get('failure') is not None
                or payload.get('status') not in (None, 'completed', 'success', 'succeeded')):
            raise ValueError('Incomplete or inconsistent native turn')
        return [dict(path=path, checksum=checksum, cli_turn_id=self.id)
                for path, checksum in self.generated.items()
                if checksum in self.displayed and (self.targets is None or path in self.targets)]


def _turns(home, session_id, cursor=None, targets=None):
    session(session_id)
    active = None
    discarded = False
    seen = set()
    for record in records(home, session_id, cursor):
        payload = record.get('payload')
        if not isinstance(payload, dict):
            if record.get('type') in ('event_msg', 'response_item'):
                raise ValueError('Invalid native rollout payload')
            continue
        kind = payload.get('type')
        if record.get('type') == 'event_msg':
            if kind == 'task_started':
                turn_id = payload.get('turn_id')
                if (active is not None or not isinstance(turn_id, str) or not turn_id
                        or len(turn_id) > 128 or turn_id in seen):
                    raise ValueError('Ambiguous native turn')
                session(turn_id)
                seen.add(turn_id)
                discarded = False
                active = _Turn(turn_id, session_id, targets)
                active.check_ids(payload)
            elif kind in ('task_failed', 'turn_failed', 'turn_aborted', 'task_aborted', 'error'):
                if targets is None:
                    raise ValueError('Native rollout contains a failed turn')
                if active is not None:
                    active.check_ids(payload)
                active, discarded = None, True
            elif kind in ('item_completed', 'task_complete'):
                if discarded:
                    continue
                if active is None:
                    raise ValueError('Native event outside an active turn')
                active.check_ids(payload)
                item = payload.get('item', {})
                failed_image = (kind == 'item_completed' and isinstance(item, dict)
                                and item.get('type') == 'Extension'
                                and item.get('kind') == 'image_gen.generation'
                                and (item.get('status') == 'failed' or item.get('failure') is not None))
                failed_task = kind == 'task_complete' and (
                    payload.get('status') in ('failed', 'aborted', 'cancelled', 'canceled')
                    or payload.get('error') is not None or payload.get('failure') is not None)
                if targets is not None and (failed_image or failed_task):
                    active, discarded = None, True
                    continue
                if kind == 'item_completed':
                    active.item(payload)
                else:
                    result = active.complete(payload)
                    yield active.id, active.final, result
                    active = None
        elif record.get('type') == 'response_item' and kind == 'custom_tool_call_output':
            if discarded:
                continue
            if active is not None:
                active.output(payload)
            elif isinstance(payload.get('output'), list) and any(
                    isinstance(block, dict) and block.get('type') == 'input_image'
                    for block in payload['output']):
                raise ValueError('Native displayed image outside an active turn')
    if active is not None:
        raise ValueError('Truncated native turn')


def read_current(home: Path, session_id: str, cursor: dict, final_text: str) -> list[dict]:
    """Read only the appended CLI turn and return public delivery evidence."""
    if locate(home, session_id) is None:
        if cursor:
            raise ValueError('Native session rollout is missing')
        return []
    result = []
    count = 0
    for _, final, images in _turns(home, session_id, cursor):
        count += 1
        if count > 1 or final != final_text:
            raise ValueError('Native current turn is ambiguous or final text differs')
        result = images
    if not count:
        raise ValueError('Native rollout contains no complete current turn')
    return result


def read_history(home: Path, session_id: str, targets: set[str]) -> dict[str, str]:
    """Find explicit targets only in complete, successful native turns."""
    # Imported at call time: delivery also calls the native evidence parser.
    from markdown_it import MarkdownIt
    from .delivery import non_delivery, references

    for target in targets:
        _path(target, session_id)
    result = {}
    for _, final, images in _turns(home, session_id, targets=targets):
        explicit = list(references(final))
        selected = {logical for _, logical in explicit}
        if not explicit and any(non_delivery(token) for token in MarkdownIt('commonmark').parse(final)
                                if token.type == 'inline'):
            continue
        for item in images:
            if explicit and item['path'] not in selected:
                continue
            if item['path'] in result:
                raise ValueError('Ambiguous native image history')
            result[item['path']] = item['checksum']
    return result
