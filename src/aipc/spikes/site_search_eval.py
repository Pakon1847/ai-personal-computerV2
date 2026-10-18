"""วัดเกณฑ์ข้อ 2 ของการ์ด 0036: ค้นในบริการด้วยเสียง 30 ประโยค (ค้นในบริการ 20 · ประโยคใกล้เคียง 10).

ชุดวัด tests/data/site_search_eval/set.json เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นโค้ด และ commit ก่อนรันครั้งแรก (H9) ·
ห้ามแก้ชุดวัดให้ผ่าน · แปลด้วยตัวเดียวกับคำสั่งเสียงของแอป (browse.parse) · ไม่เปิดเบราว์เซอร์ ไม่ออกเน็ต ·
เทียบคำค้นแบบไม่สนช่องว่างและตัวพิมพ์เล็ก/ใหญ่ (ตัวแปลรวมคำไทยที่ตัวถอดเสียงเว้นวรรคไว้)

    python -m aipc.spikes.site_search_eval [--set <ชุดวัด>] [--out ผล.json] [--strict]
    (ชุดวัดค่าเริ่มต้น tests/data/site_search_eval/set.json)

เกณฑ์ (การ์ด 0036 หัวข้อ 8 ข้อ 2): ค้นถูกบริการและคำค้นถูก ≥ 18/20 · ค้นผิดบริการ 0 · ประโยคใกล้เคียงไม่เข้า 10/10

--strict (รอบ 4 · ตรวจทั้งระบบ 2026-10-18 ข้อ 3.2): ประโยคใกล้เคียง "ไม่เข้า" = ไม่ได้คำสั่งเว็บเลย
(เดิมนับแค่ "ไม่ใช่ค้นในบริการ" → ประโยคที่ไหลไปค้น Google ก็นับผ่าน) · ยกเว้นข้อที่เฉลยเขียน {"kind": "search"}
(ตั้งใจค้น Google จริง เช่น "ค้นในกูเกิลว่า…") ต้องได้ค้นเว็บอย่างเดียว ไม่มีค้นในบริการ
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NEED_POSITIVE = 18


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def judge(item: dict, strict: bool = False) -> dict:
    from aipc.skills import browse

    cmds = browse.parse(item["text"])
    found = next((c for c in cmds if c.kind == "site_search"), None)
    want = item["expect"]
    positive = bool(want) and "site" in want  # รอบ 3: ประโยคใกล้เคียงเขียน expect เป็น null
    if positive:
        same = found is not None and norm(found.query) == norm(want["query"])
        ok = same and found.site == want["site"]
    elif strict and want:  # ตั้งใจค้น Google จริง
        ok = [c.kind for c in cmds] == [want["kind"]]
    elif strict:
        ok = not cmds
    else:
        ok = found is None
    return {"id": item["id"], "text": item["text"], "positive": positive, "ok": ok,
            "wrong_site": positive and found is not None and found.site != want["site"],
            "got": [c.as_dict() for c in cmds], "want": want}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="tests/data/site_search_eval/set.json")
    ap.add_argument("--out", default="")
    ap.add_argument("--strict", action="store_true", help="ประโยคใกล้เคียงต้องไม่ได้คำสั่งเว็บเลย (รอบ 4)")
    a = ap.parse_args(argv)
    data = json.loads(Path(a.set).read_text(encoding="utf-8"))
    rows = [judge(it, a.strict) for it in data["items"]]
    pos = [r for r in rows if r["positive"]]
    neg = [r for r in rows if not r["positive"]]
    for r in rows:
        print(f"{'✓' if r['ok'] else '✗'} {r['id']} {r['text']}")
        if not r["ok"]:
            print(f"    ได้: {r['got']}\n    เฉลย: {r['want']}")
    pos_ok, neg_ok = sum(r["ok"] for r in pos), sum(r["ok"] for r in neg)
    wrong = sum(r["wrong_site"] for r in pos)
    passed = pos_ok >= NEED_POSITIVE and wrong == 0 and neg_ok == len(neg)
    print(f"ค้นถูกบริการและคำค้นถูก {pos_ok}/{len(pos)} (เกณฑ์ ≥ {NEED_POSITIVE})")
    print(f"ค้นผิดบริการ {wrong} (เกณฑ์ 0) · ประโยคใกล้เคียงไม่เข้า {neg_ok}/{len(neg)}")
    print("ผ่าน" if passed else "ไม่ผ่าน")
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        summary = {"positive_ok": pos_ok, "positive": len(pos), "wrong_site": wrong,
                   "negative_ok": neg_ok, "negative": len(neg), "passed": passed,
                   "strict": a.strict}  # fmt: skip
        out.write_text(json.dumps({**summary, "rows": rows}, ensure_ascii=False, indent=1),
                       encoding="utf-8")  # fmt: skip
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
