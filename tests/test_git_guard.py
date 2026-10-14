"""ตัวกันคำสั่ง git อันตรายของ Claude Code (.claude/hooks/git_guard.py) · Pakon อนุมัติ 2026-10-14."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "git_guard.py"
_spec = importlib.util.spec_from_file_location("git_guard", HOOK)
git_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_guard)


class GitGuardTest(unittest.TestCase):
    def test_dangerous_commands_ask(self):
        for cmd in [
            "git push",
            "git push --force origin main",
            "cd /d/x && git -C repo push",
            "cat <<EOF && git push\nข้อความ\nEOF",
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git clean -xdf",
            "git branch -D feature/old",
            "git checkout .",
            "git checkout -- src/app.py",
            "git restore src/app.py",
            "git rebase -i HEAD~3",
            "git commit --amend -m x",
            "git filter-branch --tree-filter x",
            "git stash drop",
            "git reflog expire --expire=now --all",
            "ssh pi 'cd ~/repo && git reset --hard origin/master'",
            "/usr/bin/git push",
        ]:
            with self.subTest(cmd=cmd):
                self.assertNotEqual(git_guard.danger(cmd), "", cmd)

    def test_everyday_commands_pass(self):
        for cmd in [
            "git status --short",
            "git log --oneline -10",
            "git log --grep push",
            "git diff --stat",
            "git add -A src tests",
            "git commit -q -F - <<'EOF'\nfix: ห้าม git push โดยไม่ถาม\nEOF\ngit log --oneline -1",
            "git bundle create x.bundle bb7a50e..feature/x",
            "git fetch -q /tmp/x.bundle feature/x && git merge -q --ff-only FETCH_HEAD",
            "git checkout feature/0024-voice-browser",
            "git restore --staged src/app.py",
            "git branch -a",
            "git stash list",
            "echo 'git push' > notes.txt",
            "python -m unittest",
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(git_guard.danger(cmd), "", cmd)

    def run_hook(self, payload: bytes):
        return subprocess.run(
            [sys.executable, str(HOOK)], input=payload, capture_output=True, timeout=30
        )

    def test_hook_answers_ask_as_json_even_with_thai_in_command(self):
        """ข้อความ commit ภาษาไทย + push ในคำสั่งเดียว → ต้องถาม (อ่าน stdin เป็น UTF-8)."""
        cmd = 'git commit -m "แก้ตัวแปลรอบ 3" && git push origin master'
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        p = self.run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "ask"))
        self.assertIn("push", out["permissionDecisionReason"])
        self.assertTrue(p.stdout.isascii())

    def test_hook_silent_for_safe_or_unreadable_input(self):
        safe = json.dumps({"tool_name": "PowerShell", "tool_input": {"command": "git status"}})
        for payload in [safe.encode(), b"not json", b""]:
            with self.subTest(payload=payload[:20]):
                p = self.run_hook(payload)
                self.assertEqual((p.returncode, p.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
