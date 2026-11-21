"""Per-invocation diagnostic budget and append-only, independent protocol evidence."""
import json
import re
import time
from collections import Counter, deque
from contextlib import ExitStack

from app.execution.capture_json import JsonRow, semantic
from app.execution.credential_errors import AUTH_STDERR_CODE, AUTH_STDERR_MARKER


DETAIL_BUDGET = 128 * 1024 * 1024
_STDERR_TAIL = 128 * 1024
_SUMMARY_RESERVE = 64 * 1024
_ENCODED = re.compile(rb'[A-Za-z0-9+/=_-]{160,}')
_FOLDED = re.compile(rb'(?:[A-Za-z0-9+/=]{40,}(?:\\r\\n|\\n|[ \t])+){2,}[A-Za-z0-9+/=]*')
_ENCODING_CONTEXT = re.compile(rb'base64|b64decode|frombase64string|atob\s*\(', re.I)
_IMAGE_PATH = re.compile(rb'''(?:^|[\s"'(=])((?:/work/)?[a-z][a-z0-9_-]{0,31}\.(?:png|jpe?g|webp|avif|gif|bmp|tiff?))(?=[\s"'),;]|$)''', re.I)
_ITEM_EVENTS = ('item.started', 'item.updated', 'item.completed')
_ITEM_STATUSES = ('in_progress', 'pending', 'running', 'completed', 'success', 'failed',
                  'cancelled', 'canceled', 'aborted', 'declined')
COMPACTED = b'{"type":"platform.log_compacted"}\n'
_TOOLS = ('command_execution', 'file_change', 'mcp_tool_call', 'web_search',
          'todo_list', 'image_generation')
_MAX_OPEN_TOOLS = 4096


def _ordinary_tool(event):
    if not event or event['type'] not in ('item.started', 'item.updated', 'item.completed'):
        return False
    item = event.get('item')
    if not isinstance(item, dict) or item.get('type') not in _TOOLS:
        return False
    for value in (event, item):
        if (value.get('error') is not None or value.get('failure') is not None
                or value.get('exit_code') not in (None, 0)
                or value.get('status') not in (None, 'in_progress', 'running', 'completed', 'success')):
            return False
    return all(event.get(key) is None or isinstance(event[key], str) for key in ('thread_id', 'turn_id'))


def _redact(raw):
    # Replace unbroken runs first so giant image payloads never enter a
    # backtracking match for command output containing folded MIME Base64.
    return _FOLDED.sub(b'[encoded data omitted]', _ENCODED.sub(b'[encoded data omitted]', raw))


class LogCapture:
    def __init__(self, control, files: ExitStack):
        self.control = control
        self.events = files.enter_context((control / 'events.jsonl').open('wb'))
        self.detail = files.enter_context((control / 'detail.log').open('wb'))
        self.stderr = files.enter_context((control / 'stderr.log').open('wb'))
        self.budget = DETAIL_BUDGET
        self.headroom = max(0, self.budget - _STDERR_TAIL - _SUMMARY_RESERVE)
        self.raw = self.written = self.omitted = 0
        self.compacted = False
        self.tool_context = None
        self.tool_id = None
        self.tool_completed = False
        self.open_tools = set()
        self.auth_recorded = False
        self.auth_source = self.auth_failure = False
        self.auth_overlap = b''
        (control / AUTH_STDERR_MARKER).unlink(missing_ok=True)
        self.recent = deque(maxlen=24)
        self.counts = Counter()
        self.stdout = JsonRow()
        self.err_head = bytearray()
        self.err_tail = bytearray()
        self.err_size = 0
        self.stderr_tail = bytearray()
        self.next_checkpoint = time.monotonic() + 5
        self.dirty = False
        (control / 'detail-summary.json').unlink(missing_ok=True)

    def _compact(self):
        if not self.compacted:
            self.events.write(COMPACTED)
            self.events.flush()
            self.compacted = True

    def feed(self, channel, data):
        self.raw += len(data)
        if self.raw > self.budget:
            self._compact()
        for index, part in enumerate(data.split(b'\n')):
            if index:
                if channel == 'stdout':
                    self._out()
                else:
                    self._err()
            if channel == 'stdout':
                self.stdout.feed(part)
            else:
                self._stderr_auth(part)
                self.err_size += len(part)
                self.err_head.extend(part[:max(0, 8192 - len(self.err_head))])
                self.err_tail.extend(part)
                if len(self.err_tail) > 8192:
                    del self.err_tail[:-8192]

    def _stderr_auth(self, part):
        if self.auth_recorded:
            return
        chunk = self.auth_overlap + part
        self.auth_source |= b'codex_login::auth' in chunk
        self.auth_failure |= b'failed to refresh token' in chunk.lower()
        self.auth_overlap = chunk[-22:]
        if self.auth_source and self.auth_failure:
            with (self.control / AUTH_STDERR_MARKER).open('xb') as marker:
                marker.write(AUTH_STDERR_CODE)
            self.auth_recorded = True

    def _record(self, channel, name, raw, size, shortened=False):
        self.dirty = True
        self.counts[channel] += 1
        if not self.compacted and self.written + len(raw) + 1 <= self.headroom:
            self.detail.write(raw)
            self.detail.write(b'\n')
            self.written += len(raw) + 1
        else:
            self._compact()
            shortened = True
        if shortened:
            self.omitted += 1
        self.recent.append({'source': channel, 'event': name, 'bytes': size})

    def _out(self):
        row, self.stdout = self.stdout, JsonRow()
        event = None
        name = 'invalid'
        try:
            event, raw = row.finish()
            if event is None:
                return
            message = semantic(event)
            name = event['type'][:64]
            item = event.get('item')
            if isinstance(item, dict) and isinstance(item.get('type'), str):
                name += '/' + item['type'][:64]
        except (ValueError, TypeError, UnicodeError, RecursionError):
            # A malformed row remains a permanent failure for every reader.
            # Neither a prefix nor a later valid completion can authenticate it.
            event, message, raw = None, b'null\n', b'[invalid CLI event]'
        item = (event or {}).get('item')
        identity = item.get('id') if isinstance(item, dict) else None
        can_open = (not isinstance(identity, str) or
                    len(identity) <= 1024 and (len(self.open_tools) < _MAX_OPEN_TOOLS or identity in self.open_tools))
        if (not can_open and isinstance(item, dict) and item.get('type') in _TOOLS
                and event['type'] in ('item.started', 'item.updated')):
            self._compact()
            # A boundary still clears any older reply; avoid advertising a new
            # running tool whose eventual close we cannot afford to track.
            message = semantic({**event, 'item': {**item, 'type': 'compacted_tool_progress'}})
        if self._keep_event(event, can_open):
            self.events.write(message)
        is_command = isinstance(item, dict) and item.get('type') == 'command_execution'
        shortened = bool(is_command or row.large or row.invalid)
        if shortened:
            raw = self._brief(event, row.preview, row.size)
        elif self.compacted:
            raw = b''
        else:
            # Inspect decoded command strings too (e.g. JSON Unicode escapes).
            command = item.get('command') if event and isinstance(item, dict) else None
            if (_ENCODING_CONTEXT.search(raw) or isinstance(command, str)
                    and _ENCODING_CONTEXT.search(command.encode('utf-8', 'backslashreplace'))):
                redacted = self._brief(event, raw, row.size)
            else:
                redacted = _redact(raw)
            shortened = redacted != raw
            raw = redacted
        self._record('stdout', name, raw, row.size, shortened)

    def _brief(self, event, prefix, size):
        item = (event or {}).get('item')
        item = item if isinstance(item, dict) else {}
        command = item.get('command')
        source = command.encode('utf-8', 'backslashreplace') if isinstance(command, str) else prefix
        targets = []
        for match in _IMAGE_PATH.finditer(source):
            path = match[1]
            if not re.search(rb'[A-Za-z0-9]{24,}', path) and path not in targets:
                targets.append(path)
                if len(targets) == 2:
                    break
        kind, tool, status = (event or {}).get('type'), item.get('type'), item.get('status')
        result = dict(type=kind if kind in _ITEM_EVENTS else 'other',
                      itemType=tool if tool in _TOOLS else 'other',
                      status=status if status in _ITEM_STATUSES else None, recordBytes=size,
                      targets=[p.decode('ascii') for p in targets], omitted=True)
        code = item.get('exit_code')
        if type(code) is int and -(2**31) <= code < 2**31:
            result['exitCode'] = code
        return json.dumps(result).encode()

    def _keep_event(self, event, can_open):
        # Adjacent ordinary items clear the delivery candidate exactly once.
        # Retain the representative item's terminal update for live transcript.
        # A new identity, reply, failure or turn boundary always starts a new run.
        item = (event or {}).get('item')
        is_tool = isinstance(item, dict) and item.get('type') in _TOOLS
        identity = item.get('id') if is_tool else None
        identified = isinstance(identity, str) and bool(identity)
        completed = bool(event and event.get('type') == 'item.completed')
        if identified and completed and identity in self.open_tools:
            self.open_tools.remove(identity)
            context = (event.get('thread_id'), event.get('turn_id'))
            if self.tool_context == context and self.tool_id == identity:
                self.tool_completed = True
            elif self.tool_context != context:
                self.tool_context = None
            return True
        if not self.compacted or not _ordinary_tool(event):
            if can_open and identified and event.get('type') in ('item.started', 'item.updated'):
                self.open_tools.add(identity)
            self.tool_context = None
            return True
        context = (event.get('thread_id'), event.get('turn_id'))
        identity = event['item'].get('id')
        completed = event['type'] == 'item.completed'
        if context != self.tool_context:
            self.tool_context, self.tool_id, self.tool_completed = context, identity, completed
            if can_open and identified and not completed:
                self.open_tools.add(identity)
            return True
        if completed and self.tool_id == identity and not self.tool_completed:
            self.tool_completed = True
            return True
        return False

    def _err(self):
        shortened = self.err_size > len(self.err_head)
        head = _redact(self.err_head)
        if shortened:
            # Redact a run crossing either display boundary as well.
            head = re.sub(rb'[A-Za-z0-9+/=_-]+$', b'', head)
            tail = re.sub(rb'^[A-Za-z0-9+/=_-]+', b'', self.err_tail)
            head += b' [detail omitted] ' + _redact(tail)
        self._record('stderr', 'stderr', head, self.err_size, shortened or head != self.err_head)
        self.stderr_tail.extend(head + b'\n')
        if len(self.stderr_tail) > _STDERR_TAIL:
            del self.stderr_tail[:-_STDERR_TAIL]
        self.err_head.clear()
        self.err_tail.clear()
        self.err_size = 0
        self.auth_overlap = b''
        self.auth_failure = self.auth_source = False

    def flush_events(self):
        self.events.flush()
        if self.dirty and time.monotonic() >= self.next_checkpoint:
            self._checkpoint()

    def finish(self):
        if self.stdout.size:
            self._out()
        if self.err_size:
            self._err()
        self._checkpoint()

    def _checkpoint(self):
        self.stderr.seek(0)
        self.stderr.write(self.stderr_tail)
        self.stderr.truncate()
        self.stderr.flush()
        self.events.flush()
        self.detail.flush()
        summary = dict(rawBytes=self.raw, headBytes=self.written, compacted=self.compacted,
                       omittedRecords=self.omitted, records=self.counts, recent=list(self.recent))
        temporary = self.control / 'detail-summary.tmp'
        temporary.write_text(json.dumps(summary), encoding='utf-8')
        temporary.replace(self.control / 'detail-summary.json')
        self.next_checkpoint = time.monotonic() + 5
        self.dirty = False
