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
        self.displayed = {}
        self.public = {}
        self.candidates = []
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
            if item.get('status') != 'completed' or item.get('failure') is not None:
                return  # A recovered tool failure cannot veto the final response.
            if payload.get('turn_id') != self.id or payload.get('thread_id') != self.session:
                raise ValueError('Native image generation has no turn identity')
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
            # Confirmation tools can emit final_answer AgentMessages too. Only
            # task_complete identifies the actual response that ended this turn.
            self.candidates.append((_text(item), self.displayed.copy(), self.public.copy()))
            if len(self.candidates) > 1000:
                raise ValueError('Too many native final candidates')

    def output(self, payload):
        metadata = payload.get('internal_chat_message_metadata_passthrough')
        blocks = payload.get('output')
        if not isinstance(blocks, list) or not any(
                isinstance(block, dict) and block.get('type') == 'input_image' for block in blocks):
            return
        self.displayed = {}
        for block in blocks:
            if not isinstance(block, dict) or block.get('type') != 'input_image':
                continue
            if not isinstance(metadata, dict) or metadata.get('turn_id') != self.id:
                raise ValueError('Native displayed image turn mismatch')
            self.check_ids(metadata)
            value = block.get('image_url')
            if not isinstance(value, str) or not value.startswith('data:image/png;base64,'):
                continue
            self.displayed[_digest(value.removeprefix('data:image/png;base64,'))] = None
            self.public.update(self.displayed)
            if len(self.public) > MAX_IMAGES:
                raise ValueError('Too many native displayed images')

    def complete(self, payload):
        self.check_ids(payload)
        matching = [(text, images, public) for text, images, public in self.candidates
                    if text == payload.get('last_agent_message')]
        if (payload.get('turn_id') != self.id or not matching
                or payload.get('error') is not None or payload.get('failure') is not None
                or payload.get('status') not in (None, 'completed', 'success', 'succeeded')):
            raise ValueError('Incomplete or inconsistent native turn')
        self.final, displayed, public = matching[-1]
        # Non-image verification tools leave the latest presentation intact.
        # A new process image must not join a later redisplayed historical batch.
        if self.targets is not None:
            selected = self.generated.items()
        else:
            # Presentation order is authoritative. Identical generated pixels
            # shown once cannot justify collecting several process file paths.
            paths = {checksum: path for path, checksum in self.generated.items()}
            selected = [(paths.get(checksum), checksum) for checksum in displayed]
        return [dict(path=path, checksum=checksum, cli_turn_id=self.id) for path, checksum in selected]


def _turns(home, session_id, cursor=None, targets=None, end_cursor=None, current=False):
    session(session_id)
    active = None
    discarded = False
    seen = set()
    for record in records(home, session_id, cursor, end_cursor, first_turn_only=current):
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
            elif kind == 'error':
                # Diagnostics are not terminal. A later normal task_complete
                # may confirm a successfully recovered invocation.
                if active is not None:
                    active.check_ids(payload)
            elif kind in ('task_failed', 'turn_failed', 'turn_aborted', 'task_aborted'):
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
                if failed_image:
                    continue
                if targets is not None and failed_task:
                    active, discarded = None, True
                    continue
                if kind == 'item_completed':
                    active.item(payload)
                else:
                    result = active.complete(payload)
                    yield active.id, active.final, result
                    active = None
                    if current:
                        return
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


def _generated_paths(home, session_id, end_cursor):
    """Find prior image locations, without imposing the old turn's outcome.

    The current completed presentation selects pixels. An earlier failed or
    interrupted invocation can still have left a usable, completed image.
    """
    for record in records(home, session_id, end_cursor=end_cursor):
        payload = record.get('payload')
        if record.get('type') != 'event_msg' or not isinstance(payload, dict):
            continue
        item = payload.get('item')
        if (payload.get('type') != 'item_completed' or payload.get('thread_id') != session_id
                or not isinstance(item, dict) or item.get('type') != 'Extension'
                or item.get('kind') != 'image_gen.generation' or item.get('status') != 'completed'
                or item.get('failure') is not None):
            continue
        try:
            path, checksum = _path(item.get('savedPath'), session_id), _digest(item.get('result'))
        except ValueError:
            continue  # Unrelated broken historical records cannot veto valid pixels.
        yield path, checksum


def read_current(home: Path, session_id: str, cursor: dict, final_text: str,
                 end_cursor: dict | None = None) -> list[dict]:
    """Read only the appended CLI turn and return public delivery evidence."""
    if locate(home, session_id) is None:
        if cursor or end_cursor:
            raise ValueError('Native session rollout is missing')
        return []
    result = []
    count = 0
    for _, final, images in _turns(home, session_id, cursor, end_cursor=end_cursor, current=True):
        count += 1
        if count > 1 or final != final_text:
            raise ValueError('Native current turn is ambiguous or final text differs')
        result = images
    if not count:
        raise ValueError('Native rollout contains no complete current turn')
    if any(item['path'] is None for item in result):
        # Redisplay does not necessarily call imagegen again. Match only pixels
        # shown in THIS completed reply to prior same-session image locations.
        # The pre-invocation cursor excludes current/later turns from history.
        historical = {}
        if cursor:
            historical = {checksum: path for path, checksum in _generated_paths(home, session_id, cursor)}
        for item in result:
            if item['path'] is None:
                item['path'] = historical.get(item['checksum'])
                if item['path'] is None:
                    raise ValueError('Displayed native image file is not yet available')
    return result


def read_history(home: Path, session_id: str, targets: set[str],
                 end_cursor: dict | None = None) -> dict[str, str]:
    """Authenticate explicit same-session files without a prior delivery gate."""
    for target in targets:
        _path(target, session_id)
    result = {}
    for _, _, images in _turns(home, session_id, targets=targets, end_cursor=end_cursor):
        for item in images:
            if item['path'] in result:
                raise ValueError('Ambiguous native image history')
            result[item['path']] = item['checksum']
    return result
