"""กันคำสั่ง git ที่ลบงาน / แก้ประวัติ / ส่งออก ก่อน Claude Code รัน (hook PreToolUse ของ Bash และ PowerShell).

ที่มา: แนวคิดจาก mattpocock/skills git-guardrails-claude-code (MIT) · เขียนใหม่เป็น Python
เพราะของเดิมต้องใช้ jq (เครื่องวินโดวส์นี้ไม่มี → ของเดิมจะปล่อยผ่านเงียบ ๆ) · Pakon อนุมัติ 2026-10-14

ไม่ห้ามเด็ดขาด แต่ **ถาม Pakon ก่อน** ("ask") ให้ตรงกับ CLAUDE.md หัวข้อ git:
"ห้าม push reset --hard clean หรือแก้ประวัติ โดยไม่ถาม"

รับ JSON ของ hook ทาง stdin · ตอบ JSON ทาง stdout เฉพาะเมื่อต้องถาม · อ่านไม่ออก = ไม่ยุ่ง (exit 0)
ใช้แค่ไลบรารีมาตรฐาน (ไม่มี dependency)
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# เนื้อหา heredoc (เช่นข้อความ commit) ไม่ใช่คำสั่ง → ตัดทิ้ง
# แต่เก็บส่วนท้ายบรรทัดเปิดไว้ตรวจ ("cat <<EOF && git push" ยังต้องถาม)
_HEREDOC = re.compile(
    r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
    re.S,
)
# แยกท่อนคำสั่ง: ; && || | ขึ้นบรรทัดใหม่ (ท่อนใน ssh '...' ก็ถูกแยกด้วย = ตรวจคำสั่งที่ส่งไปรันบน Pi ด้วย)
_SEGMENTS = re.compile(r"&&|\|\||[;|\n]")
# ตัวเลือกของ git ที่ตามด้วยค่า 1 ตัว (ต้องข้ามไปหาคำสั่งย่อย)
_OPT_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:  # quote ไม่ครบ (ท่อนที่ถูกตัดกลาง ssh '...') → แยกด้วยช่องว่างพอ
        return segment.replace("'", " ").replace('"', " ").split()


def _git_calls(command: str):
    """(คำสั่งย่อย, อาร์กิวเมนต์) ของทุก git ในคำสั่ง."""
    for seg in _SEGMENTS.split(_HEREDOC.sub(r" \3", command)):
        toks = _tokens(seg)
        for i, tok in enumerate(toks):
            name = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
            if name not in ("git", "git.exe"):
                continue
            j = i + 1
            while j < len(toks) and toks[j].startswith("-"):
                j += 2 if toks[j] in _OPT_WITH_VALUE else 1
            if j < len(toks):
                yield toks[j], toks[j + 1 :]
            break


def _short_flags(args: list[str]) -> str:
    """ตัวอักษรของตัวเลือกสั้นทั้งหมด (-fdx → fdx)."""
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def danger(command: str) -> str:
    """เหตุผลที่ต้องถาม · "" = ไม่อันตราย."""
    for sub, args in _git_calls(command):
        flags = _short_flags(args)
        if sub == "push":
            return "git push = ส่งโค้ดออกนอกเครื่อง"
        if sub == "reset" and "--hard" in args:
            return "git reset --hard = ทิ้งงานที่ยังไม่ commit"
        if sub == "clean" and ("f" in flags or "--force" in args):
            return "git clean -f = ลบไฟล์ที่ยังไม่อยู่ใน git"
        if sub == "branch" and ("D" in flags or {"--delete", "--force"} <= set(args)):
            return "git branch -D = ลบสาขาที่อาจยังไม่ได้รวม"
        if sub == "checkout" and ({".", "--", "--force"} & set(args) or "f" in flags):
            return "git checkout ./-- = เขียนทับไฟล์ที่แก้ค้างอยู่"
        if sub == "restore" and not ("--staged" in args and "--worktree" not in args):
            return "git restore = เขียนทับไฟล์ที่แก้ค้างอยู่"
        if sub == "rebase":
            return "git rebase = แก้ประวัติ"
        if sub == "commit" and "--amend" in args:
            return "git commit --amend = แก้ประวัติ"
        if sub in ("filter-branch", "filter-repo"):
            return f"git {sub} = แก้ประวัติทั้ง repo"
        if sub == "stash" and args[:1] in (["drop"], ["clear"]):
            return f"git stash {args[0]} = ลบงานที่พักไว้"
        if sub == "reflog" and args[:1] == ["expire"]:
            return "git reflog expire = ลบทางย้อนกลับ"
        if sub == "update-ref" and "-d" in args:
            return "git update-ref -d = ลบ ref"
    return ""


def main() -> int:
    try:
        # อ่านเป็นไบต์แล้วถอด UTF-8 เอง: Python บนวินโดวส์อ่าน stdin เป็น cp874
        # → ข้อความ commit ภาษาไทยทำให้อ่านพัง แล้วตัวกันจะปล่อยผ่าน (git commit -m "…" && git push)
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        command = str((data.get("tool_input") or {}).get("command") or "")
    except (ValueError, AttributeError):
        return 0
    reason = danger(command)
    if reason:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"{reason} · CLAUDE.md: ทำได้เมื่อ Pakon อนุมัติเท่านั้น",
            }
        }
        sys.stdout.write(json.dumps(out))  # ASCII ล้วน (\uXXXX) · พิมพ์ภาษาไทยลง cp874 ไม่ได้
    return 0


if __name__ == "__main__":
    sys.exit(main())
