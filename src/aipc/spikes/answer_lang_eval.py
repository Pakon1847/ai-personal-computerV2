"""วัดเกณฑ์ A3 ของการ์ด 0039: AI ในเครื่องตอบภาษาเดียวกับที่ผู้ใช้ถามไหม.

ชุดคำถาม (ภาษาอังกฤษ 30 · ไทย 30) เขียนโดยผู้ช่วยอีกตัวที่ไม่เห็นโค้ด และ commit ก่อนรัน (H9) ·
prompt เดียวกับแอป (catalog.system_prompt · ภาษาของคำถามตัดสินด้วย catalog.is_english) ·
ไม่ส่งเครื่องมือ (ดูแค่ภาษาของคำตอบ)

ภาษาของคำตอบตัดสินด้วยโค้ด (นับตัวอักษร ไม่ใช้ AI ตัดสิน):
    ไทย = ตัวอักษรไทยตั้งแต่ 50% ของตัวอักษรไทย+ละติน · อังกฤษ = ไทยน้อยกว่า 10% และมีตัวละติน · อื่น ๆ = ปน
เกณฑ์: ถามอังกฤษได้คำตอบอังกฤษ ≥ 28/30 · ถามไทยได้คำตอบไทย 30/30 · คำตอบว่าง = ไม่ผ่าน

    python -m aipc.spikes.answer_lang_eval --server http://127.0.0.1:8090 --set <ชุด> --out <ผล>
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

THAI = re.compile(r"[฀-๿]")
LATIN = re.compile(r"[A-Za-z]")
NEED_EN, NEED_TH = 28, 30


def answer_lang(text: str) -> str:
    th, en = len(THAI.findall(text)), len(LATIN.findall(text))
    if th + en == 0:
        return "empty"
    ratio = th / (th + en)
    if ratio >= 0.5:
        return "th"
    if ratio < 0.10 and en > 0:
        return "en"
    return "mixed"


def main(argv: list[str] | None = None) -> int:
    from aipc.skills import catalog
    from aipc.spikes.exam import ask_local

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--model-name", default="Gemma 4 E2B")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    items = json.loads(Path(a.set).read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        english = catalog.is_english(it["q"])
        system = catalog.system_prompt(date.today(), model=a.model_name, english=english)
        try:
            r = ask_local(a.server, system, it["q"], [])
            text, err = r["text"], ""
        except Exception as e:  # noqa: BLE001 · บันทึกตามจริง นับเป็นไม่ผ่าน
            text, err = "", f"{type(e).__name__}: {e}"
        got = answer_lang(text)
        ok = got == it["lang"]
        rows.append({"id": it["id"], "q": it["q"], "asked": it["lang"], "prompt_english": english,
                     "answer": text, "answer_lang": got, "ok": ok, "error": err})  # fmt: skip
        print(f"{'✓' if ok else '✗'} {it['id']} {it['lang']}→{got} {it['q'][:60]}", flush=True)
    en = [r for r in rows if r["asked"] == "en"]
    th = [r for r in rows if r["asked"] == "th"]
    en_ok, th_ok = sum(r["ok"] for r in en), sum(r["ok"] for r in th)
    passed = en_ok >= NEED_EN and th_ok == len(th) == NEED_TH
    print(
        f"ถามอังกฤษ ตอบอังกฤษ {en_ok}/{len(en)} (เกณฑ์ ≥ {NEED_EN}) · "
        f"ถามไทย ตอบไทย {th_ok}/{len(th)} (เกณฑ์ {NEED_TH})"
    )
    print("ผ่าน" if passed else "ไม่ผ่าน")
    summary = {"en_ok": en_ok, "th_ok": th_ok, "passed": passed, "rows": rows}
    Path(a.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
