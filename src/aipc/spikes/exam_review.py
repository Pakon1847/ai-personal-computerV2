"""ให้คนตรวจคำตอบที่ Claude ตอบในชุดสอบไฮบริด (ตัวตรวจอัตโนมัติไม่ตรวจข้อมูลจากเว็บ · exam.py).

    python -m aipc.spikes.exam_review sheet <ผลไฮบริด.json> --out <โฟลเดอร์>     → review.html (เปิดในเบราว์เซอร์)
    python -m aipc.spikes.exam_review score <ผลไฮบริด.json> review-*.csv          → คะแนนไฮบริดหลังคนตรวจ

ผลตัดสินต่อข้อ (ประกาศก่อนตรวจ · docs/benchmarks/2026-10-06-exam-hybrid-gemma/README.md):
  correct  ตอบถูกตามข้อเท็จจริง ณ เวลาที่ถาม
  partial  ถูกบางส่วน / มีส่วนผิด
  wrong    ผิด หรือแต่งข้อมูล
  honest   ไม่ได้ตอบ แต่บอกตรง ๆ ว่าไม่รู้/หาไม่ได้
ผ่าน = correct · หรือ honest ในข้อที่เฉลยคือ "บอกตรง ๆ" (เหมือนที่ AI ในเครื่องได้คะแนน) · partial/wrong = ไม่ผ่าน ·
ผู้ตรวจ 2 คนเห็นไม่ตรงกัน = ไม่ผ่าน (ระวังไว้ก่อน) และขึ้นรายการให้คุยกัน
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

VERDICTS = ("correct", "partial", "wrong", "honest")


def cloud_rows(result: dict) -> list[dict]:
    return [r for r in result["rows"] if r.get("by") == "cloud"]


def sheet(result_file: Path, out_dir: Path) -> Path:
    res = json.loads(result_file.read_text(encoding="utf-8"))
    rows = [{"id": r["id"], "q": r["q"], "expect": r["expect"], "why": r.get("escalated_by", ""),
             "local": r.get("local_text", ""), "claude": r.get("text", "")} for r in cloud_rows(res)]  # fmt: skip
    data = json.dumps({"asked": res.get("date", ""), "rows": rows}, ensure_ascii=False)
    data = data.replace("</", "<" + chr(92) + "/")
    page = Path(__file__).with_name("exam_review_page.html").read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "review.html"
    out.write_text(page.replace("__DATA__", data), encoding="utf-8")
    return out


def passes(verdict: str, expect: str) -> bool:
    return verdict == "correct" or (verdict == "honest" and expect == "honest")


def score(result_file: Path, review_files: list[Path]) -> dict:
    res = json.loads(result_file.read_text(encoding="utf-8"))
    cl = {r["id"]: r for r in cloud_rows(res)}
    votes: dict[str, list[str]] = {i: [] for i in cl}
    for f in review_files:
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                v = row["verdict"].strip()
                if v not in VERDICTS:
                    raise ValueError(f"{f.name} ข้อ {row['id']}: '{v}' ต้องเป็น {', '.join(VERDICTS)}")
                if row["id"] in votes:
                    votes[row["id"]].append(v)
    missing = [i for i, v in votes.items() if len(v) != len(review_files)]
    if missing:
        raise ValueError(f"ยังตรวจไม่ครบ: {', '.join(missing)}")
    passed, disagree, live_data = [], [], 0
    for i, vs in votes.items():
        ok = [passes(v, cl[i]["expect"]) for v in vs]
        if all(ok):
            passed.append(i)
        elif any(ok):
            disagree.append(i)
        if i.startswith("B") and all(v == "correct" for v in vs):
            live_data += 1
    auto_ok = res["summary"]["auto_ok"]
    verified = auto_ok - len(cl) + len(passed)  # auto_ok นับคำตอบ Claude ทุกข้อเป็นผ่าน → แทนด้วยผลคนตรวจ
    return {"cloud_items": len(cl), "cloud_passed": len(passed), "disagree": disagree,
            "live_data_answered": live_data, "hybrid_auto_ok_before_review": auto_ok,
            "hybrid_after_review": verified, "votes": votes}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.exam_review")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("sheet")
    a.add_argument("result", type=Path)
    a.add_argument("--out", type=Path, required=True)
    b = sub.add_parser("score")
    b.add_argument("result", type=Path)
    b.add_argument("reviews", type=Path, nargs="+")
    x = p.parse_args(argv)
    if x.cmd == "sheet":
        print(sheet(x.result, x.out))
    else:
        print(json.dumps(score(x.result, x.reviews), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
