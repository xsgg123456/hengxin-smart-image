"""Behavior regressions, entirely in temporary repositories; no remote writes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("harness", Path(__file__).with_name("harness.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        h.bootstrap(self.root)

    def call(self, action, data=None):
        return h.handle(action, data or {}, self.root)

    def committed_code(self):
        code = self.root / "app.py"
        code.write_text("print(1)")
        subprocess.run(["git", "-C", str(self.root), "add", "app.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=测试", "-c", "user.email=test@example.invalid", "commit", "-qm", "初始化测试"], check=True)
        return code

    def test_clean_checkout_readonly_does_not_require_review(self):
        self.committed_code()
        self.call("check-evolution")
        self.call("mark-review-needed", {"tool_input": {"command": "git status"}})
        self.assertIsNone(self.call("stop-gate"))

    def test_first_start_preserves_existing_dirty_changes(self):
        code = self.committed_code()
        code.write_text("print(2)")
        self.call("check-evolution")
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_first_start_preserves_existing_deletion(self):
        self.committed_code().unlink()
        self.call("check-evolution")
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_first_start_preserves_existing_untracked_code(self):
        self.committed_code()
        (self.root / "new.py").write_text("print(2)")
        self.call("check-evolution")
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_array_command_input_is_supported(self):
        self.committed_code()
        self.call("mark-review-needed", {"tool_input": {"command": ["powershell", "-Command", "git status"]}})
        self.assertIsNone(self.call("stop-gate"))

    def test_unobserved_change_after_clean_is_blocked(self):
        code = self.committed_code()
        self.call("mark-review-needed")
        (self.root / ".codex/.needs-review").write_text("clean")
        code.write_text("print('unreviewed')")
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_quoted_git_directory_checks_actual_target(self):
        target = self.root / "my project"
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        (target / "tsconfig.json").write_text("{}")
        for cmd in ('git -C "my project" commit -m "测试"', "git -C 'my project' -c user.name=测试 commit -m 测试"):
            result = self.call("pre-tool-shell", {"tool_input": {"command": cmd}})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_powershell_here_strings_do_not_break_commit_parser(self):
        for cmd in ('Write-Output @"\nhello\n"@', "@'\n脚本内容\n'@ | python -", 'git status; Write-Output @"\nhello\n"@'):
            self.assertIsNone(self.call("pre-tool-shell", {"tool_input": {"command": cmd}}))

    def test_git_commit_after_here_string_still_checked(self):
        (self.root / "tsconfig.json").write_text("{}")
        cmd = 'Write-Output @"\nhello\n"@\ngit commit -m "中文提交"'
        result = self.call("pre-tool-shell", {"tool_input": {"command": cmd}})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_fresh_session_and_stop(self):
        self.assertIsNone(self.call("check-evolution"))
        self.assertIsNone(self.call("stop-gate"))

    def test_registered_commands_from_nested_directory(self):
        hook_dir = self.root / ".codex/hooks"
        hook_dir.mkdir()
        shutil.copyfile(Path(__file__).with_name("harness.py"), hook_dir / "harness.py")
        nested = self.root / "nested directory"
        nested.mkdir()
        config = json.loads(Path(__file__).parents[1].joinpath("hooks.json").read_text(encoding="utf-8"))
        for event, groups in config["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    if os.name == "nt":
                        shell = shutil.which("pwsh") or shutil.which("powershell")
                        args = [shell, "-NoProfile", "-NonInteractive", "-Command", hook["commandWindows"]]
                    else:
                        args = ["/bin/sh", "-c", hook["command"]]
                    result = subprocess.run(args, cwd=nested, input=json.dumps({"cwd": str(nested), "hook_event_name": event}), capture_output=True, text=True, encoding="utf-8", timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {})

    def test_feedback_roundtrip_and_proposal_sections(self):
        prompt = '不是这样，改成 "中文"\n下一行'
        self.call("detect-feedback-signal", {"prompt": prompt})
        queue = self.root / ".codex/evolution/signals.jsonl"
        self.assertEqual(json.loads(queue.read_text(encoding="utf-8"))["prompt"], prompt)
        self.assertIn("新信号：True", str(self.call("check-evolution")))
        queue.write_text("", encoding="utf-8")
        (queue.parent / "proposals.md").write_text("## 待审阅\n- 待定\n## 已消化日志\n- 旧建议\n", encoding="utf-8")
        self.assertIn("建议 1 条", str(self.call("check-evolution")))

    def test_docs_do_not_require_review(self):
        (self.root / "README.md").write_text("docs")
        self.call("mark-review-needed")
        self.assertIsNone(self.call("stop-gate"))

    def test_shell_changes_review_then_reedit(self):
        code = self.root / "app.py"
        code.write_text("print(1)")
        self.call("mark-review-needed")
        self.assertEqual(self.call("stop-gate")["decision"], "block")
        (self.root / ".codex/.needs-review").write_text("clean\n")
        self.assertIsNone(self.call("stop-gate"))
        self.call("mark-review-needed")
        self.assertIsNone(self.call("stop-gate"))
        code.write_text("print(2)")
        self.call("mark-review-needed")
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_patch_deletion_and_external_exclusion(self):
        self.call("mark-review-needed", {"tool_input": {"command": "*** Delete File: src/old.ts\n"}})
        self.assertEqual(self.call("stop-gate")["decision"], "block")
        (self.root / ".codex/.needs-review").unlink()
        self.call("mark-review-needed", {"tool_input": {"file_path": str(self.root.parent / "outside.py")}})
        self.assertIsNone(self.call("stop-gate"))

    def test_empty_review_state_fails_closed(self):
        (self.root / ".codex/.needs-review").touch()
        self.assertEqual(self.call("stop-gate")["decision"], "block")

    def test_commit_without_typescript(self):
        self.assertIsNone(self.call("pre-tool-shell", {"tool_input": {"command": "git commit -m init"}}))

    def test_missing_typescript_blocks_commit(self):
        (self.root / "tsconfig.json").write_text("{}")
        result = self.call("pre-tool-shell", {"tool_input": {"cmd": "git commit -m test"}})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_local_compiler_success_and_failure(self):
        compiler = self.root / "node_modules/typescript/bin/tsc"
        compiler.parent.mkdir(parents=True)
        (self.root / "tsconfig.json").write_text("{}")
        compiler.write_text("process.exit(0)")
        self.assertIsNone(h.typecheck(self.root))
        compiler.write_text("console.error('compile failed'); process.exit(1)")
        self.assertIn("compile failed", h.typecheck(self.root))

    def test_autopush_disabled_by_default(self):
        self.assertIsNone(self.call("auto-push", {"tool_input": {"command": "git commit -m test"}, "tool_response": {"exit_code": 0}}))

    def test_autopush_rejects_compound_commands(self):
        for cmd in ('git commit -m test; Write-Output done', 'git commit -m test || true', 'echo git commit', 'git commit -m test\ntrue'):
            with patch.object(h, "git") as mocked:
                self.call("auto-push", {"tool_input": {"command": cmd}, "tool_response": {"exit_code": 0}})
                mocked.assert_not_called()

    def test_autopush_rejects_non_committing_modes(self):
        for flag in ("--dry-run", "--short", "--porcelain", "--long", "--help", "-h"):
            with patch.object(h, "git") as mocked:
                self.call("auto-push", {"tool_input": {"command": "git commit " + flag}, "tool_response": {"exit_code": 0}})
                mocked.assert_not_called()

    def test_autopush_protected_failure_and_feature_branch(self):
        calls = []
        branch = "main"
        def fake_git(root, *args):
            calls.append(args)
            output = "true" if args[0] == "config" else branch if args[0] == "branch" else ""
            return subprocess.CompletedProcess(args, 0, output, "")
        with patch.object(h, "git", fake_git):
            data = {"tool_input": {"command": "git commit -m test"}, "tool_response": {"exit_code": 0}}
            self.call("auto-push", data)
            self.assertIn(("config", "--local", "--bool", "harness.autoPush"), calls)
            self.assertFalse(any(c[0] == "push" for c in calls))
            branch = "feature/test"
            data["tool_response"]["exit_code"] = 1
            self.call("auto-push", data)
            self.assertFalse(any(c[0] == "push" for c in calls))
            data["tool_response"]["exit_code"] = 0
            self.call("auto-push", data)
            self.assertIn(("push", "--set-upstream", "origin", branch), calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
