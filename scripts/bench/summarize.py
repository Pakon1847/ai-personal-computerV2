"""สรุปผลเทียบ LLM 2026-10-29 ตามกติกาที่ประกาศก่อนรัน (README หัวข้อ "เกณฑ์" + "กติกาจัดอันดับ").

    python scripts/bench/summarize.py [--speed speed.json]

อ่าน raw-laptop/<label>-heldout.json (ความแม่น) · --speed = ค่าจาก Pi 5 ต่อ label
({"<label>": {"tg": tok/s, "ttft": วิ, "vmhwm_mb": MB}}) · ไม่มีค่าจาก Pi = เกณฑ์ 4–6 "รอ Pi"
พิมพ์ตาราง markdown + McNemar exact (จับคู่รายข้อ) เทียบ gemma4-e2b
"""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / "docs" / "benchmarks" / "2026-10-29-llm-compare"
CURRENT = "gemma4-e2b"
TIE = 5  # ต่างกัน ≤ 5 ข้อ = เท่ากัน (README กติกาข้อ 1)


def ok(row: dict) -> bool:
    return row["auto"] in ("ok", "cloud-answered")


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """b01 = a ถูก b ผิด · b10 = a ผิด b ถูก · p สองทางแบบ exact (binomial 0.5)."""
    n01 = sum(x and not y for x, y in zip(a, b, strict=True))
    n10 = sum(y and not x for x, y in zip(a, b, strict=True))
    n, k = n01 + n10, min(n01, n10)
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)
    return n01, n10, p


def load() -> dict[str, dict]:
    res = {}
    for f in sorted((BENCH / "raw-laptop").glob("*-heldout.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("done"):
            res[d["label"]] = d
    return res


def criteria(d: dict, sp: dict | None) -> dict[str, bool | None]:
    s, rows = d["summary"], d["rows"]
    route, honest = s["route"], s["honest"]
    return {
        "1 แต่ง ≤5%": s["fabricated"] <= 0.05 * len(rows),
        "2 บอกตรง ≥90%": honest[1] == 0 or honest[0] / honest[1] >= 0.9,
        "3 สกิล ≥80%": route[1] == 0 or route[0] / route[1] >= 0.8,
        "4 เริ่มตอบ ≤15วิ": None if not sp else sp["ttft"] <= 15,
        "5 ≥4 tok/s": None if not sp else sp["tg"] >= 4,
        "6 RAM ≤3.5GB": None if not sp else sp["vmhwm_mb"] <= 3584,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=Path)
    a = ap.parse_args()
    speed = json.loads(a.speed.read_text(encoding="utf-8")) if a.speed else {}
    res = load()
    table = []
    for label, d in res.items():
        rows = d["rows"]
        crit = criteria(d, speed.get(label))
        llm = [r for r in rows if r["by"] == "local"]
        table.append({
            "label": label,
            "ok": sum(map(ok, rows)),
            "ok_llm": f"{sum(map(ok, llm))}/{len(llm)}",
            "check": sum(r["auto"] == "check" for r in rows),
            "fab": d["summary"]["fabricated"],
            "honest": "{}/{}".format(*d["summary"]["honest"]),
            "route": "{}/{}".format(*d["summary"]["route"]),
            "empty": sum(r["route"] == "chat" and not r["text"] for r in llm),
            "passed": sum(v is True for v in crit.values()),
            "unknown": sum(v is None for v in crit.values()),
            "crit": crit,
            "tg": (speed.get(label) or {}).get("tg"),
        })  # fmt: skip
    # กติกา 1–2: จำนวนเกณฑ์ที่ผ่าน → ok · ต่างกัน ≤ TIE = เท่ากัน (ตัดสินด้วย tok/s เมื่อมีค่าจาก Pi)
    table.sort(key=lambda t: (-t["passed"], -t["ok"]))
    head = ["#", "โมเดล", "ok /100", "ok (ข้อที่ AI ตอบ)", "ให้คนตรวจ", "แต่ง", "บอกตรง", "สกิลถูก",
            "ว่าง", *table[0]["crit"]] if table else []  # fmt: skip
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for i, t in enumerate(table, 1):
        marks = ["รอ Pi" if v is None else "✅" if v else "❌" for v in t["crit"].values()]
        name = f"**{t['label']}**" if t["label"] == CURRENT else t["label"]
        cells = [i, name, t["ok"], t["ok_llm"], t["check"], t["fab"], t["honest"], t["route"],
                 t["empty"], *marks]  # fmt: skip
        print("| " + " | ".join(map(str, cells)) + " |")
    if CURRENT in res:
        base = {r["id"]: ok(r) for r in res[CURRENT]["rows"]}
        print(f"\nMcNemar exact เทียบ {CURRENT} (จับคู่รายข้อ · n01 = ตัวนี้ถูก {CURRENT} ผิด):\n")
        for t in table:
            if t["label"] == CURRENT:
                continue
            mine = {r["id"]: ok(r) for r in res[t["label"]]["rows"]}
            ids = sorted(base.keys() & mine.keys())
            n01, n10, p = mcnemar([mine[i] for i in ids], [base[i] for i in ids])
            diff = t["ok"] - sum(base.values())
            tie = "เท่ากัน (≤5)" if abs(diff) <= TIE else ("ดีกว่า" if diff > 0 else "แย่กว่า")
            sig = "ต่างจริง" if p < 0.05 else "ไม่ต่างอย่างมีนัยสำคัญ"
            print(f"- {t['label']}: {diff:+d} ข้อ · {tie} · n01={n01} n10={n10} · p={p:.3f} · {sig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
