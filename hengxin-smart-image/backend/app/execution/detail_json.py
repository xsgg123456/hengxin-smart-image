"""Validate discarded JSON containers without retaining their array elements."""
import json
import re

_ATOM = re.compile(rb'(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?)\Z')


class DetailContainer:
    def __init__(self, opener):
        self.stack = []
        self.atom = bytearray()
        self.key = bytearray()
        self.key_bytes = self.key_count = 0
        self.open(opener)

    def open(self, char):
        if len(self.stack) >= 512:
            raise ValueError('Excessive JSON nesting')
        self.stack.append([{} if char == 123 else None, 'first'])

    def value(self):
        keys, state = self.stack[-1]
        if state != 'value' and not (keys is None and state == 'first'):
            raise ValueError('Unexpected JSON value')
        self.stack[-1][1] = 'after'

    def flush_atom(self):
        if self.atom:
            if not _ATOM.fullmatch(self.atom):
                raise ValueError('Invalid JSON literal')
            self.value()
            self.atom.clear()

    def plain(self, char):
        if char not in b'{}[],: \t\r\n':
            self.atom.append(char)
            if len(self.atom) > 65536:
                raise ValueError('Excessive JSON literal')
            return
        self.flush_atom()
        keys, state = self.stack[-1]
        if char in b' \t\r\n':
            return
        if char in b'[{':
            self.value()
            self.open(char)
        elif char in b']}':
            if (keys is None) != (char == 93) or state not in ('first', 'after'):
                raise ValueError('Unexpected JSON close')
            if keys is not None:
                self.key_bytes -= sum(keys.values())
                self.key_count -= len(keys)
            self.stack.pop()
        elif char == 44 and state == 'after':
            self.stack[-1][1] = 'value' if keys is None else 'key'
        elif char == 58 and state == 'colon':
            self.stack[-1][1] = 'value'
        else:
            raise ValueError('Unexpected JSON punctuation')

    def start_string(self):
        self.flush_atom()
        keys, state = self.stack[-1]
        self.reading_key = keys is not None and state in ('first', 'key')
        if not self.reading_key:
            self.value()

    def string_part(self, value):
        if self.reading_key:
            self.key.extend(value)
            if len(self.key) > 65536:
                raise ValueError('Excessive JSON key')

    def end_string(self):
        if self.reading_key:
            # Escaped and literal spellings of the same key are duplicates.
            name = json.loads(b'"' + self.key + b'"')
            keys = self.stack[-1][0]
            if name in keys:
                raise ValueError('Duplicate detail key')
            keys[name] = len(self.key)
            self.key_count += 1
            self.key_bytes += len(self.key)
            if self.key_count > 131072 or self.key_bytes > 8 * 1024 * 1024:
                raise ValueError('Excessive simultaneous JSON keys')
            self.key.clear()
            self.stack[-1][1] = 'colon'
