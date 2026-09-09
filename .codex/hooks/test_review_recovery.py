"""Expired-report recovery and bounded single-writer coordination regressions."""
import json
import threading
import unittest
from unittest.mock import patch

import review_store
import test_review_gate as core


class ReviewRecoveryTests(unittest.TestCase):
    setUp = core.ReviewGateTests.setUp
    git = core.ReviewGateTests.git
    write = core.ReviewGateTests.write
    call = core.ReviewGateTests.call
    approve = core.ReviewGateTests.approve

    def assert_expired_blocks(self):
        with self.assertRaisesRegex(ValueError, '审查报告'):
            core.gate.stop(self.root)
        with self.assertRaisesRegex(ValueError, '审查报告'):
            core.gate.check_commit(self.root)

    def recover_report(self, deleted):
        self.write('app.py', 'print(2)\n')
        self.approve()
        self.git('add', 'app.py')
        state_path = self.root / '.codex/review-state.json'
        original = json.loads(state_path.read_text())['approved']
        if deleted:
            (self.root / 'review.md').unlink()
        else:
            self.write('review.md', '已变化的报告\n')
        self.assert_expired_blocks()
        candidate = self.call('prepare')['candidateId']
        # Preparing is not approval, even when the code snapshot is unchanged.
        self.assertEqual(json.loads(state_path.read_text())['approved'], original)
        self.assert_expired_blocks()
        self.write('docs/new-review.md', '重新审查：Stage 1 PASS；Stage 2 PASS\n')
        self.call('approve', candidateId=candidate, report='docs/new-review.md',
                  stage1='PASS', stage2='PASS')
        self.assertIsNone(core.gate.stop(self.root))
        self.assertIsNone(core.gate.check_commit(self.root))

    def test_modified_report_can_be_replaced_after_new_review(self):
        self.recover_report(deleted=False)

    def test_deleted_report_can_be_replaced_after_new_review(self):
        self.recover_report(deleted=True)

    def test_recovery_does_not_relax_candidate_or_stage_guards(self):
        self.approve()
        (self.root / 'review.md').unlink()
        candidate = self.call('prepare')['candidateId']
        self.write('docs/new-review.md', 'PASS\n')
        valid = dict(candidateId=candidate, report='docs/new-review.md',
                     stage1='PASS', stage2='PASS')
        for replacement in ({'candidateId': '0' * 64}, {'stage1': 'FAIL'},
                            {'stage2': None}):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.call('approve', **(valid | replacement))
            self.assert_expired_blocks()
        self.write('app.py', 'print(3)\n')
        with self.assertRaisesRegex(ValueError, '审查期间文件已变化'):
            self.call('approve', **valid)
        self.assert_expired_blocks()

    def test_recovery_rejects_corrupt_approval_structure(self):
        self.approve()
        state_path = self.root / '.codex/review-state.json'
        state = json.loads(state_path.read_text())
        state['approved']['report']['sha256'] = 'invalid digest'
        state_path.write_text(json.dumps(state), encoding='utf-8')
        for action in ('prepare', 'approve'):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, '结构损坏'):
                self.call(action)

    def test_skill_reference_markdown_is_controlled_but_report_is_not(self):
        self.assertIsNone(core.gate.stop(self.root))
        self.write('docs/review-result.md', 'PASS\n')
        self.assertIsNone(core.gate.stop(self.root))
        name = '.agents/skills/demo/references/policy.md'
        self.write(name, '规则一\n')
        self.assertIn(name, self.call('status')['changedFiles'])
        self.approve()
        self.write(name, '规则二\n')
        self.assertEqual(core.gate.stop(self.root)['decision'], 'block')
        self.git('add', name)
        self.assertIsNotNone(core.gate.check_commit(self.root))

    def test_short_concurrent_transaction_waits_then_succeeds(self):
        acquired, release = threading.Event(), threading.Event()
        failures = []

        def holder():
            try:
                with review_store.transaction(self.root):
                    acquired.set()
                    if not release.wait(3):
                        raise RuntimeError('测试未释放锁')
            except Exception as exc:
                failures.append(exc)

        worker = threading.Thread(target=holder)
        worker.start()
        try:
            self.assertTrue(acquired.wait(3))
            timer = threading.Timer(0.05, release.set)
            timer.start()
            try:
                with patch.object(review_store.time, 'sleep', wraps=review_store.time.sleep) as sleep:
                    self.assertIn('candidateId', self.call('prepare'))
                    self.assertTrue(sleep.called)
            finally:
                timer.join()
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertFalse((self.root / '.codex/.review-state.lock').exists())

    def test_lock_timeout_does_not_delete_foreign_lock(self):
        lock = self.write('.codex/.review-state.lock', 'other process\n')
        with patch.object(review_store, 'LOCK_TIMEOUT', 0.03):
            with self.assertRaisesRegex(RuntimeError, '等待超时'):
                self.call('prepare')
        self.assertEqual(lock.read_text(), 'other process\n')
        self.assertFalse((self.root / '.codex/review-state.json').exists())


if __name__ == '__main__':
    unittest.main()
