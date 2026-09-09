"""Review snapshot regressions using real Git blobs in isolated repositories."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("review_gate", Path(__file__).with_name("review_gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="review-gate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "测试")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.write("app.py", "print(1)\n")
        self.git("add", "app.py")
        self.git("commit", "-qm", "初始化")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, encoding="utf-8").stdout

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
        return target

    def call(self, action, **data):
        return gate.run(self.root, "review-" + action, data)

    def approve(self, candidate=None, **extra):
        if candidate is None:
            candidate = self.call("prepare")["candidateId"]
        self.write("review.md", "# 审查报告\nStage 1: PASS\nStage 2: PASS\n")
        data = dict(candidateId=candidate, report="review.md", stage1="PASS", stage2="PASS")
        data.update(extra)
        return self.call("approve", **data)

    def blocked(self):
        self.assertEqual(gate.stop(self.root)["decision"], "block")

    def test_clean_checkout_and_empty_repository(self):
        self.assertIsNone(gate.stop(self.root))
        with tempfile.TemporaryDirectory() as empty:
            subprocess.run(["git", "init", "-q", empty], check=True)
            self.assertIsNone(gate.stop(Path(empty)))

    def test_first_dirty_is_blocked(self):
        self.write("app.py", "print(2)\n")
        self.blocked()

    def test_first_untracked_is_blocked(self):
        self.write("new.py", "print(2)\n")
        self.blocked()

    def test_first_deletion_is_blocked(self):
        (self.root / "app.py").unlink()
        self.blocked()

    def test_legacy_clean_cannot_approve_dirty(self):
        self.write("app.py", "print(2)\n")
        self.write(".codex/.needs-review", "clean\n")
        self.write(".codex/.review-snapshot.json", "{}")
        self.blocked()

    def test_approval_survives_repeated_stop_and_status(self):
        self.write("app.py", "print(2)\n")
        result = self.approve()
        self.assertTrue(result["approved"])
        for _ in range(3):
            self.assertIsNone(gate.stop(self.root))
            status = self.call("status")
            self.assertTrue(status["approved"])
            self.assertEqual(status["currentId"], status["reviewedId"])
            self.assertEqual(status["changedFiles"], [])

    def test_change_during_review_rejects_approval(self):
        candidate = self.call("prepare")["candidateId"]
        self.write("app.py", "print(2)\n")
        with self.assertRaises(Exception):
            self.approve(candidate)
        self.blocked()

    def test_new_prepare_supersedes_old_candidate(self):
        old = self.call("prepare")["candidateId"]
        self.write("app.py", "print(2)\n")
        current = self.call("prepare")["candidateId"]
        self.assertNotEqual(old, current)
        with self.assertRaises(Exception):
            self.approve(old)
        self.approve(current)
        self.assertIsNone(gate.stop(self.root))

    def test_status_preserves_previous_approval_after_edit(self):
        self.approve()
        reviewed = self.call("status")["reviewedId"]
        self.write("app.py", "print(2)\n")
        for _ in range(2):
            status = self.call("status")
            self.assertEqual(status["reviewedId"], reviewed)
            self.assertFalse(status["approved"])
            self.assertIn("app.py", status["changedFiles"])
            self.blocked()

    def test_config_and_framework_files_require_review(self):
        self.assertIsNone(gate.stop(self.root))
        for name in ("config.json", "config.yaml", "package-lock.json", "AGENTS.md",
                     ".codex/hooks/custom.py", ".agents/skills/custom/SKILL.md"):
            with self.subTest(path=name):
                path = self.write(name, "{}\n")
                self.blocked()
                path.unlink()
                self.assertIsNone(gate.stop(self.root))

    def test_ignored_generated_and_ordinary_docs_do_not_trigger(self):
        self.write(".gitignore", "cache/\n")
        self.approve()
        for name in ("cache/new.py", "node_modules/mod/index.js", "dist/app.js",
                     "build/generated.py", "README.md", "notes/review.md"):
            self.write(name, "generated\n")
        self.assertIsNone(gate.stop(self.root))

    def test_crlf_normalized_but_code_whitespace_not_ignored(self):
        self.write("app.py", "print(2)\n")
        self.approve()
        self.write("app.py", "print(2)\r\n")
        self.assertIsNone(gate.stop(self.root))
        self.write("app.py", "print(2) \r\n")
        self.blocked()

    def test_missing_and_external_reports_rejected(self):
        candidate = self.call("prepare")["candidateId"]
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "review.md"
            external.write_text("PASS", encoding="utf-8")
            for report in ("missing.md", str(external)):
                with self.subTest(report=report), self.assertRaises(Exception):
                    self.call("approve", candidateId=candidate, report=report,
                              stage1="PASS", stage2="PASS")

    def test_modified_approved_report_invalidates_approval(self):
        self.write("app.py", "print(2)\n")
        self.approve()
        self.write("review.md", "changed report\n")
        try:
            self.blocked()
        except (RuntimeError, ValueError):
            pass
        self.git("add", "app.py")
        try:
            self.assertIsNotNone(gate.check_commit(self.root))
        except (RuntimeError, ValueError):
            pass

    def test_failed_or_missing_stage_rejected(self):
        for stage in (dict(stage1="FAIL"), dict(stage2="FAIL"), dict(stage1=None)):
            with self.subTest(stage=stage), self.assertRaises(Exception):
                self.approve(**stage)

    def test_bad_state_schema_fails_closed(self):
        self.write("app.py", "print(2)\n")
        self.approve()
        for broken in ("{broken", "[]", '{"approved":true}', '{"baseline":{}}'):
            self.write(".codex/review-state.json", broken)
            with self.subTest(state=broken):
                try:
                    self.blocked()
                except (RuntimeError, ValueError, TypeError, KeyError):
                    pass
                try:
                    self.assertIsNotNone(gate.check_commit(self.root))
                except (RuntimeError, ValueError, TypeError, KeyError):
                    pass

    def test_index_old_version_worktree_reviewed_new_version_rejected(self):
        self.write("app.py", "print(2)\n")
        self.git("add", "app.py")
        self.write("app.py", "print(3)\n")
        self.approve()
        self.assertIsNotNone(gate.check_commit(self.root))
        self.git("add", "app.py")
        self.assertIsNone(gate.check_commit(self.root))

    def test_reviewed_index_commit_does_not_invalidate_stop(self):
        self.write("app.py", "print(2)\n")
        self.approve()
        self.git("add", "app.py")
        self.assertIsNone(gate.check_commit(self.root))
        self.git("commit", "-qm", "已审提交")
        self.assertIsNone(gate.stop(self.root))

    def test_unreviewed_index_rejected(self):
        self.write("app.py", "print(2)\n")
        self.git("add", "app.py")
        self.assertIsNotNone(gate.check_commit(self.root))

    def test_reviewed_partial_commit_allowed_but_other_dirty_blocks_stop(self):
        self.write("app.py", "print(2)\n")
        self.write("other.py", "print(2)\n")
        self.approve()
        self.git("add", "app.py")
        self.write("other.py", "print(3)\n")
        self.assertIsNone(gate.check_commit(self.root))
        self.git("commit", "-qm", "部分已审提交")
        self.blocked()

    def test_checkpoint_allows_exactly_one_stop_never_commit(self):
        self.write("app.py", "print(2)\n")
        self.git("add", "app.py")
        self.call("checkpoint", reason="等待用户补充信息")
        self.assertIsNotNone(gate.check_commit(self.root))
        self.assertIsNone(gate.stop(self.root))
        self.blocked()

    def test_checkpoint_invalidated_by_later_change(self):
        self.write("app.py", "print(2)\n")
        self.call("checkpoint", reason="暂停讨论")
        self.write("app.py", "print(3)\n")
        self.blocked()

    def test_reviewed_deletion_can_be_committed(self):
        (self.root / "app.py").unlink()
        self.approve()
        self.git("add", "-u")
        self.assertIsNone(gate.check_commit(self.root))
        self.git("commit", "-qm", "删除已审文件")
        self.assertIsNone(gate.stop(self.root))


if __name__ == "__main__":
    unittest.main()
