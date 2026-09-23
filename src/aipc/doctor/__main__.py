"""python -m aipc.doctor [--save]

พิมพ์ผลตรวจฮาร์ดแวร์ (อ่านอย่างเดียว) · --save เขียนผลลง docs/benchmarks/ เป็นหลักฐาน
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from aipc.bench import machine
from aipc.doctor import hardware

REPO = Path(__file__).resolve().parents[3]


def render(checks: list[hardware.Check], info: machine.MachineInfo) -> str:
    lines = [
        f"# ตรวจฮาร์ดแวร์ {info.board_model or info.os}",
        "",
        f"ตรวจเมื่อ {info.collected_at} · commit {info.git_commit or '—'}",
        "",
        "| ข้อ | ผล | รายละเอียด | วิธีแก้ |",
        "|---|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c.title} | **{c.status}** | {c.detail} | {c.fix} |")
    lines += [
        "",
        '"ไม่รู้" แปลว่าเครื่องมืออ่านค่าไม่ได้ ไม่ได้แปลว่าผ่าน · เครื่องมือนี้ไม่แก้อะไรบนเครื่อง',
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m aipc.doctor")
    parser.add_argument("--save", action="store_true", help="เขียนผลลง docs/benchmarks/")
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "benchmarks")
    args = parser.parse_args(argv)

    info = machine.collect(repo=REPO)
    checks = hardware.run_all()
    text = render(checks, info)
    print(text)

    if args.save:
        name = f"{date.today().isoformat()}-{info.board_class}-hardware"
        md, js = args.out / f"{name}.md", args.out / f"{name}.json"
        if md.exists() or js.exists():
            parser.error(f"{md} มีอยู่แล้ว — ผลเก่าคือหลักฐาน ห้ามเขียนทับ")
        args.out.mkdir(parents=True, exist_ok=True)
        md.write_text(text, encoding="utf-8")
        payload = {"machine": info.to_dict(), "checks": [c.to_dict() for c in checks]}
        js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"บันทึกแล้ว: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
