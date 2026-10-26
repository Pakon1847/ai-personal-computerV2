"""วัดตัวแปลคำสั่งเว็บ (การ์ด 0024 เกณฑ์ข้อ 1).

python -m aipc.spikes.browse_eval tests/data/browse_v2.json [ผล.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aipc.skills import browse


def as_recorded(cmds: list[dict]) -> list[dict]:
    """ผลแปลในรูปแบบที่ชุดวัดเดิมบันทึกไว้ · ไฟล์ชุดวัดไม่แก้ (Pakon เลือกทาง 1 · 2026-10-26).

    ช่องที่เพิ่มทีหลังตามการออกแบบ (ไม่ใช่โค้ดผิด) ตัดออกก่อนเทียบ:
    - "app" + query="workspace" (2026-10-26 · พูดชื่อหน้าผู้ช่วย/แชท = แอปไปหน้านั้นด้วย) ·
      ชนิดคำสั่งยังเป็น app เหมือนเดิม · ตรวจ 2026-10-26: ต่างจากไฟล์ 8 ประโยคใน 5 ชุด เฉพาะช่องนี้
    """
    return [
        {k: v for k, v in c.items() if not (c.get("kind") == "app" and k == "query")} for c in cmds
    ]


def run(path: Path) -> dict:
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        got = as_recorded([c.as_dict() for c in browse.parse(it["text"])])
        rows.append(
            {"text": it["text"], "expect": it["expect"], "got": got, "ok": got == it["expect"]}
        )
    cmd = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    return {
        "file": str(path),
        "commands": f"{sum(r['ok'] for r in cmd)}/{len(cmd)}",
        "commands_pct": round(100 * sum(r["ok"] for r in cmd) / max(1, len(cmd)), 1),
        "non_commands_caught": sum(bool(r["got"]) for r in neg),
        "non_commands": len(neg),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    res = run(Path(argv[0]))
    for r in res["rows"]:
        if not r["ok"]:
            print("✗", r["text"], "→", r["got"], "· ต้องเป็น", r["expect"])
    print(f"คำสั่งเว็บถูก {res['commands']} ({res['commands_pct']}%) · "
          f"ประโยคอื่นถูกจับเป็นคำสั่งเว็บ {res['non_commands_caught']}/{res['non_commands']}")  # fmt: skip
    if len(argv) > 1:
        Path(argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
