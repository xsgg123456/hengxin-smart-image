"""Bound the working set of a single JSONL row while validating discarded strings."""
import codecs
import json
import re

from app.execution.event_json import decode_event
from app.execution.detail_json import DetailContainer


SMALL_ROW = 256 * 1024
MAX_SEMANTIC_ROW = 64 * 1024 * 1024 - 1
_DETAIL_KEYS = {b'"command"', b'"aggregated_output"', b'"output"', b'"result"',
                b'"input"', b'"arguments"', b'"stdout"', b'"stderr"', b'"data"',
                b'"base64"', b'"image_url"', b'"b64_json"', b'"delta"'}
_STRING = re.compile(rb'(?:[^"\\\x00-\x1f]+|\\(?:["\\/bfnrt]|u[0-9A-Fa-f]{4}))+')


class _LargeRow:
    """Replace only long values of known detail fields. Validate the complete row.

    Keep the rest of the JSON grammar for the normal duplicate-aware decoder.
    Splits within UTF-8, quoted field names, and escape sequences are supported.
    """
    def __init__(self):
        self.result = bytearray()
        self.decoder = codecs.getincrementaldecoder('utf-8')()
        self.quoted = self.detail = self.omitted = False
        self.pending_key = self.colon = False
        self.token_start = self.shape = 0
        self.container = None
        self.carry = b''

    def punctuation(self, plain):
        for char in plain:
            if self.container is not None:
                self.container.plain(char)
                if not self.container.stack:
                    self.container = None
                continue
            if self.colon and char in b'[{':
                self.container = DetailContainer(char)
                self.result.extend(b'{}' if char == 123 else b'[]')
                self.colon = self.pending_key = False
                continue
            self.result.append(char)
            if char in b' \r\t\n':
                continue
            if char in b'{}[],:':
                self.shape += 1
                if self.shape > 131072:
                    raise ValueError('Excessive event structure')
            self.colon = self.pending_key and char == 58
            self.pending_key = False

    def feed(self, data):
        self.decoder.decode(data)
        data = self.carry + data
        self.carry = b''
        pos = 0
        while pos < len(data):
            if not self.quoted:
                end = data.find(b'"', pos)
                plain = data[pos:] if end < 0 else data[pos:end]
                self.punctuation(plain)
                if end < 0:
                    break
                self.quoted, self.detail, self.omitted = True, self.colon, False
                self.pending_key = self.colon = False
                self.token_start = len(self.result)
                if self.container is not None:
                    self.container.start_string()
                else:
                    self.result.append(34)
                pos = end + 1
                continue
            match = _STRING.match(data, pos)
            if match:
                end = match.end()
                if self.detail and len(self.result) - self.token_start + end - pos > 4096:
                    if not self.omitted:
                        del self.result[self.token_start + 1:]
                        self.result.extend(b'[detail omitted]')
                        self.omitted = True
                if self.container is not None:
                    self.container.string_part(data[pos:end])
                elif not self.omitted:
                    self.result.extend(data[pos:end])
                pos = end
            if pos == len(data):
                break
            if data[pos] == 34:
                if self.container is not None:
                    self.container.end_string()
                else:
                    self.result.append(34)
                    self.pending_key = (len(self.result) - self.token_start < 32
                                        and bytes(self.result[self.token_start:]) in _DETAIL_KEYS)
                self.quoted = False
                pos += 1
            elif data[pos] == 92 and len(data) - pos < 6:
                self.carry = data[pos:]
                break
            else:
                raise ValueError('Invalid JSON string')
        if len(self.result) > MAX_SEMANTIC_ROW:
            raise ValueError('Excessive semantic event')

    def finish(self):
        self.decoder.decode(b'', final=True)
        if self.quoted or self.carry or self.container is not None:
            raise ValueError('Unterminated JSON string')
        return self.result


class JsonRow:
    def __init__(self):
        self.small = bytearray()
        self.large = None
        self.preview = b''
        self.invalid = False
        self.size = 0

    def feed(self, data):
        self.size += len(data)
        if self.invalid:
            return
        if self.large is None and len(self.small) + len(data) <= SMALL_ROW:
            self.small.extend(data)
            return
        try:
            if self.large is None:
                self.preview = bytes(self.small[:8192])
                if len(self.preview) < 8192:
                    self.preview += data[:8192 - len(self.preview)]
                self.large = _LargeRow()
                self.large.feed(self.small)
                self.small.clear()
            self.large.feed(data)
        except (UnicodeError, ValueError):
            self.invalid = True
            self.large = None

    def finish(self):
        if self.invalid:
            raise ValueError('Invalid CLI event')
        raw = self.small if self.large is None else self.large.finish()
        if not raw.strip():
            return None, raw
        event = decode_event(bytes(raw).decode('utf-8'))
        if not isinstance(event.get('type'), str) or event['type'] == 'platform.log_compacted':
            raise ValueError('Invalid CLI event type')
        return event, raw


def semantic(event):
    """Keep the fields interpreted by completion, transcript and credential readers."""
    keys = ('type', 'turn_id', 'thread_id', 'status', 'error', 'failure', 'message', 'usage')
    record = {key: event[key] for key in keys if key in event}
    if 'item' in event:
        item = event['item']
        if isinstance(item, dict):
            fields = ('id', 'type', 'status', 'error', 'failure', 'exit_code')
            if item.get('type') in ('agent_message', 'reasoning'):
                fields += ('text',)
            item = {key: item[key] for key in fields if key in item}
        record['item'] = item
    # UTF-8 so Chinese public replies fit the same byte limit as their source.
    raw = json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8', 'backslashreplace')
    if len(raw) > MAX_SEMANTIC_ROW:
        raise ValueError('Excessive semantic event')
    return raw + b'\n'
