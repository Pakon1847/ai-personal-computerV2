"""วัดกฎคำขอแปล/สรุป (langintent) กับชุดประโยค · กฎอย่างเดียว ไม่ใช้ AI.

    python -m aipc.spikes.lang_rule_eval tests/data/lang_rule_heldout2.json [--show]

รับได้ทั้งชุดแบบ translate/summarize/other และชุดเลือกสกิล (expect = id สกิล หรือ none)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aipc.skills.langintent import lang_intent

TO_LABEL = {"translate": "translate", "summarize-text": "summarize", "summarize": "summarize"}


def evaluate(items: list[dict]) -> dict:
    rows, hit, total, false, other = [], {}, {}, 0, 0
    for it in items:
        want = TO_LABEL.get(it["expect"], "other")
        got = lang_intent(it["text"]) or "other"
        rows.append(
            {
                **it,
                "want": want,
                "got": got,
                "ok": got == want or (want == "other" and got == "other"),
            }
        )
        if want == "other":
            other += 1
            false += got != "other"
        else:
            total[want] = total.get(want, 0) + 1
            hit[want] = hit.get(want, 0) + (got == want)
    return {"hit": hit, "total": total, "false": false, "other": other, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.lang_rule_eval")
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--show", action="store_true", help="แสดงข้อที่ผิด (ห้ามใช้กับชุดอิสระก่อนวัด)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(a.dataset.read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    res = evaluate(items)
    parts = [f"{k} {res['hit'][k]}/{n}" for k, n in res["total"].items()]
    print(
        f"{a.dataset.name}: " + " · ".join(parts) + f" · other ถูกส่งผิด {res['false']}/{res['other']}"
    )
    if a.show:
        for r in res["rows"]:
            if not r["ok"]:
                print(f"  {r['want']:9} → {r['got']:9} | {r['text'][:90]}")
    if a.out:
        a.out.write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
