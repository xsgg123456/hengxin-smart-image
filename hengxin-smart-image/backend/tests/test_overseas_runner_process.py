"""Real local child processes; stdlib-only so Linux validation needs no model."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('overseas_process_under_test',
    Path(__file__).parents[1] / 'app/execution/process.py')
process = importlib.util.module_from_spec(spec)
spec.loader.exec_module(process)


@unittest.skipUnless(sys.platform == 'linux', 'Linux process-group and /proc evidence required')
class ProcessTests(unittest.TestCase):
    def test_timeout_confirms_process_exit_and_persists_receipt(self):
        self.stopped('timeout')

    def test_cancel_confirms_process_exit_and_persists_receipt(self):
        self.stopped('cancelled')

    def stopped(self, reason):
        with tempfile.TemporaryDirectory(prefix='hx-overseas-process-') as directory:
            identities = []
            receipt = process.execute([sys.executable, '-c', 'import time; time.sleep(120)'],
                'test input', directory, .2 if reason == 'timeout' else 120,
                lambda: reason == 'cancelled', lambda *identity: identities.append(identity))
            self.assertEqual(receipt['reason'], reason)
            self.assertNotEqual(receipt['exit_code'], 0)
            self.assertEqual(len(identities), 1)
            self.assertFalse(process.same_process(*identities[0]))
            self.assertEqual(json.loads((Path(directory) / 'exit.json').read_text()), receipt)

    def test_stdin_and_completed_protocol_stream(self):
        with tempfile.TemporaryDirectory(prefix='hx-overseas-process-') as directory:
            code = ('import json,sys; assert sys.stdin.read() == "frozen input"; '
                    'print(json.dumps({"type":"thread.started","thread_id":"test-local"})); '
                    'print(json.dumps({"type":"turn.completed"}))')
            receipt = process.execute([sys.executable, '-c', code], 'frozen input', directory,
                                      10, lambda: False, lambda *identity: None)
            self.assertEqual(receipt['exit_code'], 0)
            self.assertIsNone(receipt['reason'])
            lines = (Path(directory) / 'events.jsonl').read_text().splitlines()
            self.assertEqual(json.loads(lines[-1])['type'], 'turn.completed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
