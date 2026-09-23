"""คำสั่งของเครื่องมือวัด.

python -m aipc.bench machine
    พิมพ์สภาพเครื่องเป็น JSON (อ่านอย่างเดียว)

python -m aipc.bench run --topic llm-load --meta threads=4 --file models/x.gguf -- <คำสั่ง> ...
    จับเวลาคำสั่งหลัง "--" ตามกติกา BRIEF หัวข้อ 9 แล้วเขียนผลลง docs/benchmarks/
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from aipc.bench import machine, runner

REPO = Path(__file__).resolve().parents[3]
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_meta(items: list[str]) -> dict[str, str]:
    meta = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--meta ต้องเป็นรูป key=value แต่ได้ {item!r}")
        meta[key] = value
    return meta


def main(argv: list[str] | None = None) -> int:
    # console ของวินโดวส์ภาษาไทยใช้ cp874 เป็นค่าเริ่มต้น ทำให้พิมพ์บางตัวอักษรแล้ว crash
    # บังคับเป็น UTF-8 ให้ผลเหมือนกันทั้งบนวินโดวส์และบน Pi
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m aipc.bench")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("machine", help="พิมพ์สภาพเครื่อง")
    p = sub.add_parser("run", help="จับเวลาคำสั่งภายนอก")
    p.add_argument("--topic", required=True, help="ชื่อสั้นภาษาอังกฤษตัวเล็ก เช่น llm-load")
    p.add_argument("--runs", type=int, default=runner.MIN_RUNS)
    p.add_argument("--warmup", type=int, default=runner.MIN_WARMUP)
    p.add_argument("--meta", action="append", default=[], help="key=value เช่น threads=4")
    p.add_argument("--file", action="append", default=[], help="ไฟล์ที่ต้องเก็บ sha256 เช่นไฟล์โมเดล")
    p.add_argument("--out", type=Path, default=REPO / "docs" / "benchmarks")
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    if args.cmd == "machine":
        info = machine.collect(repo=REPO)
        print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
        return 0

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("ต้องมีคำสั่งที่จะวัดหลัง --")
    if not TOPIC_RE.match(args.topic):
        parser.error("--topic ใช้ได้เฉพาะ a-z 0-9 และ -")
    # ตรวจก่อนเริ่มว่าโปรแกรมที่จะวัดมีอยู่จริง จะได้ได้ข้อความที่อ่านรู้เรื่อง แทน traceback ยาว ๆ
    if shutil.which(command[0]) is None:
        parser.error(f"หาโปรแกรม {command[0]!r} ไม่เจอ — ใส่ path เต็ม หรือตรวจว่าติดตั้งแล้ว")

    files = {f: runner.sha256_file(Path(f)) for f in args.file}
    info = machine.collect(repo=REPO)
    before = info.throttled
    records = runner.measure(runner.command_task(command), warmup=args.warmup, runs=args.runs)
    name = f"{date.today().isoformat()}-{info.board_class}-{args.topic}"
    paths = runner.write_report(
        args.out, name, info, records, before, parse_meta(args.meta), files, command
    )
    print(paths["md"].read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
