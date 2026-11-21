"""Streaming protocol, real subprocess and storage regression checks (no model calls)."""
import json
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.execution import log_capture
from app.execution.capture_json import JsonRow, SMALL_ROW
from app.execution.credential_errors import authentication_failed, execution_error_code
from app.execution.events import parse_events
from app.overseas.studio.completion import read as read_studio
from app.execution.process import execute


def run_child(code, root):
    return execute([sys.executable, '-c', code], 'frozen prompt', root, 120,
                   lambda: False, lambda *identity: None)


START = {'type': 'thread.started', 'thread_id': 'real-session'}
FINAL = {'type': 'item.completed', 'item': {'id': 'final', 'type': 'agent_message',
                                           'text': '![result](/work/image.png)'}}
DONE = {'type': 'turn.completed', 'usage': {'output_tokens': 8}}


class CaptureTest(unittest.TestCase):
    def test_large_record_validates_whole_structure_and_utf8(self):
        prefix = b'{"type":"item.completed","item":{"type":"mcp_tool_call","result":{"content":[{"text":"'
        for suffix, valid in [(b'"}]}}}', True), (b'\\q"}]}}}', False), (b'\xff"}]}}}', False),
                              (b'"}]}},"type":"turn.completed"}', False),
                              (b'"}]}}}{"type":"turn.completed"}', False)]:
            with self.subTest(suffix=suffix):
                row = JsonRow()
                row.feed(prefix)
                row.feed(b'X' * SMALL_ROW)
                row.feed(suffix)
                if valid:
                    value, _ = row.finish()
                    self.assertEqual(value['item']['result'], {})
                else:
                    with self.assertRaises(ValueError):
                        row.finish()

    def test_large_mcp_content_streams_and_checks_every_element(self):
        prefix = b'{"type":"item.completed","item":{"type":"mcp_tool_call","result":{"content":['
        chunk = b'{"type":"text","text":"line"},' * 1000
        for last, valid in [(b'null', True), (b'{"a":1,"\\u0061":2}', False),
                            (b'{"a":1,}', False), (b'[true false]', False), (b'01', False)]:
            with self.subTest(last=last):
                row = JsonRow()
                row.feed(prefix)
                for _ in range(28):
                    row.feed(chunk)
                row.feed(last + b']}}}')
                if valid:
                    event, raw = row.finish()
                    self.assertEqual(event['item']['result'], {})
                    self.assertLess(len(raw), 1024)
                else:
                    with self.assertRaises(ValueError):
                        row.finish()

    def test_fragmented_python_encoding_does_not_reach_detail_and_tools_close(self):
        def tool(kind, identity, **extra):
            return {'type': 'item.' + kind, 'item': {'type': 'command_execution', 'id': identity, **extra}}
        with tempfile.TemporaryDirectory() as folder, ExitStack() as files:
            root = Path(folder)
            with patch.object(log_capture, 'DETAIL_BUDGET', 512 * 1024):
                capture = log_capture.LogCapture(root, files)
            fragment = 'aBZ1' * 19
            code = "Path('/work/final.png').write_bytes(base64.b64decode(\n" + (repr(fragment) + '\n') * 56 + '))'
            def send(value):
                capture.feed('stdout', json.dumps(value).encode() + b'\n')
            send(tool('started', 'A', command=code))
            for _ in range(9):
                capture.feed('stderr', b'z' * 65535 + b'\n')
            send(tool('started', 'B'))
            send(tool('completed', 'A'))
            send(tool('completed', 'B'))
            send(tool('started', 'C'))
            send(tool('completed', 'C'))
            capture.finish()
            raw = (root / 'detail.log').read_bytes()
            self.assertNotIn(fragment.encode(), raw)
            self.assertIn(b'/work/final.png', raw)
            rows = [json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()]
            self.assertEqual([(e['item']['id'], e['type']) for e in rows if 'item' in e],
                [('A', 'item.started'), ('B', 'item.started'), ('A', 'item.completed'), ('B', 'item.completed')])

    def test_command_diagnostics_use_only_allowed_fields_for_every_encoding(self):
        hex_part = '89504e47' * 9 + '0d0a'
        custom = 'tile[7,9]-4d*' * 55
        commands = [
            "bytes.fromhex(" + ('"' + hex_part + '"\n') * 84 + ")",
            "rebuild_tiles(" + repr(custom) + ")",
            "inspect /work/final.png",
        ]
        with tempfile.TemporaryDirectory() as folder, ExitStack() as files:
            root = Path(folder)
            capture = log_capture.LogCapture(root, files)
            sizes = []
            for index, command in enumerate(commands):
                item = dict(type='command_execution', id=str(index), command=command,
                            status='failed', exit_code=7, aggregated_output=custom,
                            other=hex_part, stderr=hex_part)
                event = dict(type='item.completed', item=item)
                raw = json.dumps(event).encode()
                capture.feed('stdout', raw + b'\n')
                sizes.append(len(raw))
            capture.finish()
            details = [json.loads(line) for line in (root / 'detail.log').read_bytes().splitlines()]
            for index, row in enumerate(details):
                self.assertEqual(row, dict(type='item.completed', itemType='command_execution',
                    status='failed', recordBytes=sizes[index], exitCode=7, omitted=True,
                    targets=['/work/final.png'] if index == 2 else []))
            events = [json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()]
            self.assertEqual([e['item']['id'] for e in events], ['0', '1', '2'])
            self.assertTrue(all(e['item']['status'] == 'failed' for e in events))

    @unittest.skipUnless(sys.platform == 'linux', 'Requires Linux process groups')
    def test_both_readers_receive_final_after_28000_mcp_fragments(self):
        code = '\n'.join([
            'import json',
            'print(' + repr(json.dumps(START)) + ')',
            "content = [{'type':'text','text':'line'}] * 28000",
            "print(json.dumps({'type':'item.completed','item':{'type':'mcp_tool_call','result':{'content':content}}}))",
            'print(' + repr(json.dumps(FINAL)) + ')',
            'print(' + repr(json.dumps(DONE)) + ')',
        ])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = run_child(code, root)
            self.assertEqual((receipt['reason'], receipt['exit_code']), (None, 0))
            for read in (parse_events, read_studio):
                summary = read(root / 'events.jsonl', START['thread_id'])
                self.assertTrue(summary.turn_completed)
                self.assertIsNone(summary.error)
                self.assertEqual(summary.final_text, FINAL['item']['text'])

    @unittest.skipUnless(sys.platform == 'linux', 'Requires Linux process groups')
    def test_early_stderr_authentication_evidence_survives_tail_and_resets(self):
        code = ("import sys; out=sys.stderr.buffer; out.write(b'codex_login::auth failed to refresh token\\n'); "
                "out.write((b'progress '*512 + b'\\n')*800); sys.exit(7)")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = run_child(code, root)
            self.assertNotIn(b'codex_login::auth', (root / 'stderr.log').read_bytes())
            self.assertEqual(execution_error_code(root, receipt), 'authentication_failed')
            self.assertEqual(execution_error_code(root, {'reason':'storage_failed'}), 'storage_failed')
            run_child("print('codex_login::auth failed to refresh token')", root)
            self.assertFalse(authentication_failed(root))

    def test_stderr_first_compacts_once_and_retains_boundaries_and_diagnostics(self):
        tool = {'type': 'item.completed', 'item': {'id': 'cmd-1', 'type': 'command_execution'}}
        failed = {'type': 'item.completed', 'item': {'type': 'command_execution', 'status': 'failed'}}
        wrong_thread = {**tool, 'thread_id': 'other'}
        with tempfile.TemporaryDirectory() as folder, ExitStack() as files:
            root = Path(folder)
            with patch.object(log_capture, 'DETAIL_BUDGET', 512 * 1024):
                capture = log_capture.LogCapture(root, files)
            capture.feed('stderr', b'X' * 64 * 1024 + b'\n')
            for _ in range(8):
                capture.feed('stderr', b'y' * 64 * 1024 + b'\n')
            for event in [START, *([tool] * 100), failed, wrong_thread, FINAL, DONE, tool, tool]:
                capture.feed('stdout', json.dumps(event).encode() + b'\n')
            capture.feed('stderr', b'codex_login::auth failed to refresh token\n')
            capture.finish()
            events = [json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()]
            self.assertEqual(events, [{'type': 'platform.log_compacted'}, START, tool, failed,
                                      wrong_thread, FINAL, DONE, tool])
            summary = json.loads((root / 'detail-summary.json').read_bytes())
            self.assertGreaterEqual(summary['omittedRecords'], 100)
            self.assertEqual(summary['records']['stdout'], 107)
            self.assertIn(b'codex_login::auth', (root / 'stderr.log').read_bytes())
            self.assertNotIn(b'X' * 200, (root / 'detail.log').read_bytes())

    @unittest.skipUnless(sys.platform == 'linux', 'Requires Linux process groups')
    def test_quarter_gibibyte_command_then_final_receipt(self):
        code = '\n'.join([
            'import sys,json',
            'out = sys.stdout.buffer',
            'out.write(' + repr(json.dumps(START).encode() + b'\n') + ')',
            '''out.write(b'{"type":"item.completed","item":{"type":"command_execution","command":"')''',
            "block = b'Z' * (1024 * 1024)",
            'for i in range(257): out.write(block)',
            '''out.write(b'"}}\\n')''',
            'out.write(' + repr(json.dumps(FINAL).encode() + b'\n') + ')',
            'out.write(' + repr(json.dumps(DONE).encode() + b'\n') + ')',
        ])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = run_child(code, root)
            self.assertEqual((receipt['exit_code'], receipt['reason']), (0, None))
            rows = [json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()]
            self.assertEqual(rows[-2:], [FINAL, DONE])
            self.assertEqual(rows[0], START)
            self.assertEqual(len(rows), 5)
            total = sum((root / name).stat().st_size for name in
                        ('detail.log', 'stderr.log', 'detail-summary.json'))
            self.assertLessEqual(total, 128 * 1024 * 1024)
            self.assertGreater(json.loads((root / 'detail-summary.json').read_bytes())['rawBytes'],
                               256 * 1024 * 1024)

    @unittest.skipUnless(sys.platform == 'linux', 'Uses Linux /dev/full')
    def test_disk_full_cannot_publish_success_and_second_invocation_starts_fresh(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'detail.log').symlink_to('/dev/full')
            code = 'print(' + repr(json.dumps(DONE)) + ')'
            receipt = run_child(code, root)
            self.assertEqual(receipt['reason'], 'storage_failed')
            self.assertEqual(receipt, json.loads((root / 'exit.json').read_bytes()))
            (root / 'detail.log').unlink()
            receipt = run_child('import sys; sys.exit(7)', root)
            self.assertEqual((receipt['reason'], receipt['exit_code']), (None, 7))
            self.assertEqual((root / 'events.jsonl').read_bytes(), b'')
