"""Offline install checks. Run from any working directory with Python 3.11+."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable, str(ROOT / ".codex/hooks/harness.py"), "check-evolution"], cwd=ROOT, input="{}", text=True, capture_output=True, check=True)
    expected = {"product-spec-builder", "design-brief-builder", "design-maker", "dev-planner", "dev-builder", "bug-fixer", "code-review", "release-builder", "goal-creator", "skill-builder", "evolution-engine"}
    found = set()
    for file in (ROOT / ".agents/skills").glob("*/SKILL.md"):
        text = file.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"Missing frontmatter: {file}"
        header = text.split("---", 2)[1]
        name = re.search(r"^name:\s*(.+)$", header, re.M)
        assert name and re.search(r"^description:\s*\S", header, re.M), file
        found.add(name.group(1).strip())
    assert found == expected, f"Skill mismatch: {found ^ expected}"
    for name in ("code-reviewer", "evolution-runner"):
        agent = tomllib.loads((ROOT / f".codex/agents/{name}.toml").read_text(encoding="utf-8"))
        assert agent["name"] == name and agent["description"] and agent["developer_instructions"]
    config = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    assert config["features"]["hooks"] and config["agents"]["enabled"]
    hooks = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    assert sum(len(group["hooks"]) for groups in hooks.values() for group in groups) == 6
    for groups in hooks.values():
        for group in groups:
            if "matcher" in group:
                re.compile(group["matcher"])
            for hook in group["hooks"]:
                assert hook["type"] == "command" and hook["commandWindows"] and hook["timeout"] > 0
    manifest = json.loads((ROOT / ".codex/upstream-manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert (ROOT / item["installed_path"]).is_file(), f"Missing upstream file: {item}"
    subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"], check=True)
    print(f"PASS: {len(found)} skills, 2 agents, 6 hooks, {len(manifest['files'])} upstream files present", flush=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / ".codex/hooks"), "-p", "test_*.py", "-v"], check=True)
    print("PASS: offline harness checks. Runtime discovery/trust: inspect Codex /hooks and /skills.")


if __name__ == "__main__":
    main()
