"""Codex lifecycle handlers. Python standard library only; Windows/POSIX."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import socket
import subprocess
import sys

CORRECTIONS = re.compile("不是这样|不是这个意思|不应该|搞错|你错|又错|理解错|弄错|不合理|不通用|不对劲|这不对|完全不对|去掉|删掉|删除|改成|换成|改为|不需要|没必要|多余|你漏|漏掉|漏了|你忘|忘了|没提到|没有提到|你没提|少了|每次都|怎么又|怎么还|我说过|说过了|提醒过|强调过|不是让你|没复用|你没按|没生效|没有生效|没执行|不喜欢|不太喜欢|我的意思是|我是说|其实应该|应该是|应该写")
EXCLUDED = {".git", ".codex", ".agents", "node_modules", ".venv", ".next", "dist", "build", "coverage", "__pycache__"}
NON_CODE = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock", ".log", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf"}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)


def context(event, message):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def bootstrap(root):
    evo = root / ".codex/evolution"
    evo.mkdir(parents=True, exist_ok=True)
    (evo / "signals.jsonl").touch(exist_ok=True)
    proposals = evo / "proposals.md"
    if not proposals.exists():
        proposals.write_text("# 进化建议\n\n## 待审阅\n\n暂无。\n", encoding="utf-8")


def code_path(path):
    p = Path(path)
    return not (set(p.parts) & EXCLUDED) and p.suffix.lower() not in NON_CODE and not p.name.startswith(".")


def snapshot(root):
    result = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if result.returncode:
        raise RuntimeError(result.stderr)
    files = {}
    for name in result.stdout.split("\0"):
        if not name or not code_path(name):
            continue
        path = root / name
        # Do not follow repository symlinks to external files.
        if path.is_file() and not path.is_symlink():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def initial_snapshot(root, current):
    """A clean checkout starts reviewed; pre-existing dirty files do not."""
    changed = git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD", "--")
    if changed.returncode:
        return {}
    previous = dict(current)
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode:
        raise RuntimeError(untracked.stderr)
    for name in untracked.stdout.split("\0"):
        previous.pop(name, None)
    for name in changed.stdout.split("\0"):
        if name and code_path(name):
            previous[name] = "unreviewed-head-difference"
    return previous


def mark_review(root, data):
    state = root / ".codex/.needs-review"
    saved = root / ".codex/.review-snapshot.json"
    current = snapshot(root)
    previous = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else initial_snapshot(root, current)
    if current != previous:
        state.write_text("needs_review\n", encoding="utf-8")
    if current != previous or not saved.exists():
        saved.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    # Also cover deletions before the first snapshot and exact apply_patch payloads.
    tool_input = data.get("tool_input") or {}
    if isinstance(tool_input, str):
        tool_input = {"command": tool_input}
    paths = re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", command(data), re.M)
    if tool_input.get("file_path"):
        paths.append(tool_input["file_path"])
    for name in paths:
        path = Path(name)
        path = path if path.is_absolute() else Path(data.get("cwd") or root) / path
        try:
            relative = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if code_path(relative):
            state.write_text("needs_review\n", encoding="utf-8")


def command(data):
    value = data.get("tool_input") or {}
    if isinstance(value, str):
        return value
    value = value.get("command", value.get("cmd", data.get("command", "")))
    return " ".join(value) if isinstance(value, list) else str(value)


def commit_roots(root, data):
    """Find ordinary Git commits, including quoted and repeated -C options."""
    # Parse only the Git prefix, never arbitrary PowerShell/here-string bodies
    # or commit messages. shlex is not a parser for the user's whole shell.
    argument = r'''(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s;&|"']+)'''
    prefix = rf"\bgit(?:\.exe)?\s+(?:(?:-C|-c)\s+{argument}\s+|--(?:no-pager|no-optional-locks)\s+)*commit\b"
    for match in re.finditer(prefix, command(data)):
        lexer = shlex.shlex(match.group(), posix=False)
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = [token.strip("\"'") for token in lexer]
        cwd = Path(data.get("cwd") or root)
        args = data.get("tool_input") or {}
        if isinstance(args, dict) and args.get("workdir"):
            cwd = Path(args["workdir"])
        cursor = 1
        while cursor < len(tokens):
            option = tokens[cursor]
            if option in {"-C", "-c"} and cursor + 1 < len(tokens):
                if option == "-C":
                    cwd = (cwd / tokens[cursor + 1]).resolve()
                cursor += 2
            elif option in {"--no-pager", "--no-optional-locks"}:
                cursor += 1
            elif option == "commit":
                target = git(cwd, "rev-parse", "--show-toplevel")
                if target.returncode:
                    raise RuntimeError(target.stderr)
                yield Path(target.stdout.strip())
                break
            else:
                break


def typecheck(root):
    configs = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in EXCLUDED]
        if "tsconfig.json" in files:
            configs.append(Path(directory) / "tsconfig.json")
    for config in configs:
        compiler = None
        for parent in (config.parent, *config.parent.parents):
            candidate = parent / "node_modules/typescript/bin/tsc"
            if candidate.is_file():
                compiler = candidate
                break
            if parent == root:
                break
        if compiler is None or not shutil.which("node"):
            return f"提交被阻止：{config.relative_to(root)} 缺少本地 TypeScript 编译器或 Node，请先安装项目依赖。"
        result = subprocess.run(["node", str(compiler), "--noEmit", "-p", str(config)], cwd=config.parent, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=110)
        if result.returncode:
            return "提交被阻止：TypeScript 检查失败。\n" + result.stdout + result.stderr
    return None


def handle(action, data, root):
    bootstrap(root)
    if action == "check-evolution":
        mark_review(root, {})
        proposals = (root / ".codex/evolution/proposals.md").read_text(encoding="utf-8")
        section = re.search(r"^## 待审阅\s*\n(.*?)(?=^## |\Z)", proposals, re.M | re.S)
        count = len(re.findall(r"^- ", section.group(1), re.M)) if section else 0
        queued = bool((root / ".codex/evolution/signals.jsonl").read_text(encoding="utf-8").strip())
        if count or queued:
            return context("SessionStart", f"进化队列：待审阅建议 {count} 条；新信号：{queued}。按 AGENTS.md 处理。")
    elif action == "detect-feedback-signal":
        prompt = data.get("prompt", "")
        if CORRECTIONS.search(prompt):
            with (root / ".codex/evolution/signals.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"type": "correction", "prompt": prompt}, ensure_ascii=False) + "\n")
    elif action == "mark-review-needed":
        mark_review(root, data)
    elif action == "stop-gate":
        # Re-check disk even when no PostToolUse observed the latest write.
        mark_review(root, {})
        state = root / ".codex/.needs-review"
        if state.exists():
            if state.read_text(encoding="utf-8-sig").strip() == "clean":
                (root / ".codex/.review-snapshot.json").write_text(json.dumps(snapshot(root)), encoding="utf-8")
                state.unlink()
            else:
                return {"decision": "block", "reason": "代码已修改但未通过审查。派发 code-reviewer 两阶段审查，通过后将 .codex/.needs-review 写为 clean。"}
    elif action == "pre-tool-shell":
        cmd = command(data)
        for target in commit_roots(root, data):
            failure = typecheck(target)
            if failure:
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": failure}}
        if re.search(r"\b(?:pnpm dev|npm run dev|yarn dev)\b", cmd):
            busy = []
            for port in (3000, 3001, 4173, 5173, 8080):
                with socket.socket() as probe:
                    probe.settimeout(0.1)
                    if probe.connect_ex(("127.0.0.1", port)) == 0:
                        busy.append(port)
            if busy:
                return context("PreToolUse", f"端口已占用：{busy}。请检查所属进程或选择空闲端口。")
    elif action == "auto-push":
        cmd = command(data).strip()
        # Shell-wide success cannot prove a commit in a compound script succeeded.
        if not re.match(r"^git\s+commit(?:\s|$)", cmd) or re.search(r"[;&|\r\n`$<>]", cmd):
            return None
        if re.search(r"(?:^|\s)(?:--(?:dry-run|short|porcelain|long|help)|-h)(?:[=\s]|$)", cmd):
            return None
        if git(root, "config", "--local", "--bool", "harness.autoPush").stdout.strip() != "true":
            return None
        response = data.get("tool_response", {})
        # Only push after explicit structured success; never infer success from command text.
        if not isinstance(response, dict) or response.get("exit_code") != 0:
            return context("PostToolUse", "自动推送已跳过：未收到明确的成功退出状态，请检查提交结果。")
        branch = git(root, "branch", "--show-current").stdout.strip()
        if branch and branch not in {"main", "master"}:
            result = git(root, "push", "--set-upstream", "origin", branch)
            if result.returncode:
                return context("PostToolUse", "自动推送失败，请检查：" + result.stderr)
    else:
        raise ValueError(f"Unknown hook: {action}")
    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    root_result = git(data.get("cwd") or Path.cwd(), "rev-parse", "--show-toplevel")
    if root_result.returncode:
        raise RuntimeError("Harness requires a Git working tree")
    output = handle(sys.argv[1], data, Path(root_result.stdout.strip()))
    print(json.dumps(output or {}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Harness hook failed: {exc}", file=sys.stderr)
        sys.exit(2)
