"""AI เป็นผู้ให้คะแนนคำตอบภาษาไทยแบบปิดชื่อ (ADR-007 เกณฑ์ข้อ 1 · เพิ่ม 2026-10-07 เพราะไม่มีผู้ให้คะแนนคนที่สอง).

    python -m aipc.spikes.llm_judge rate <rate-me.csv> --out <rate-claude-judge.csv>
    python -m aipc.spikes.llm_judge agree <คนให้คะแนน.csv> <AI.csv>

- ตัวให้คะแนน = `claude -p` (sonnet · ไม่มีเครื่องมือ · โฟลเดอร์ว่าง · ไม่เก็บบทสนทนา)
  **เห็นแค่แบบให้คะแนน** (คำถาม + คำตอบ A/B/C ที่สลับลำดับแล้ว)
  ไม่เห็นไฟล์เฉลย ไม่เห็นชื่อโมเดล · ถามทีละคำถาม
- **ไม่ใช่ผู้ให้คะแนนคนที่สอง** ตามที่ ADR-007 ประกาศ → รายงานเป็นหลักฐานเสริม + ความตรงกับคะแนนของคน
- ความลำเอียงที่รู้: ชอบคำตอบยาว · ชอบตำแหน่ง (Zheng et al. 2023 · arXiv:2306.05685) →
  สั่งไม่ให้ดูความยาว · ลำดับสลับอยู่แล้ว
ข้อความสั่ง (JUDGE_PROMPT) commit ก่อนรัน · ห้ามแก้หลังเห็นผล
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from aipc.skills import forge


def load_rubric() -> dict[str, str]:
    """เกณฑ์ 1–5 ชุดเดียวกับที่คนใช้ (tests/data/llm_thai_questions.json · commit 2026-09-28) ·
    ไม่พิมพ์ซ้ำในโค้ด."""
    from aipc.spikes import llm_quality

    return json.loads(llm_quality.QUESTIONS.read_text(encoding="utf-8"))["rubric"]


JUDGE_PROMPT = """คุณเป็นผู้ให้คะแนนคำตอบภาษาไทยของผู้ช่วย AI ในงานวิจัย · ให้คะแนนแต่ละคำตอบแยกกัน 1–5 ตามเกณฑ์นี้เท่านั้น:
{rubric}

กติกา:
- ให้คะแนนจากความถูกต้อง ความครบตามที่ถาม การทำตามคำสั่งในคำถาม และความเป็นธรรมชาติของภาษาไทย
- ความยาวไม่ใช่เกณฑ์ คำตอบสั้นที่ถูกและครบได้ 5 ได้ · คำตอบยาวที่มีข้อผิดต้องได้น้อยลง
- ลำดับ A/B/C สุ่มมา ไม่มีความหมาย · คำตอบมาจากคนละระบบ ไม่ต้องเดาว่าเป็นระบบไหน
- ถ้าคำถามต้องใช้ข้อมูลสดที่ระบบตอบไม่ได้ คำตอบที่บอกตรง ๆ ว่าไม่รู้ ดีกว่าคำตอบที่แต่งตัวเลข

คำถาม:
{question}

{answers}

ตอบเป็น JSON อย่างเดียว เช่น {{"A": 4, "B": 2, "C": 5}} ไม่ต้องอธิบาย"""  # noqa: E501


def load_sheet(path: Path) -> dict[str, list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["id"], []).append(r)
    return out


def build_prompt(rows: list[dict]) -> str:
    rub = load_rubric()
    rubric = "\n".join(f"{k} = {rub[k]}" for k in sorted(rub, reverse=True))
    answers = "\n\n".join(f"คำตอบ {r['choice']}:\n{r['answer']}" for r in rows)
    return JUDGE_PROMPT.format(rubric=rubric, question=rows[0]["question"], answers=answers)


def parse_scores(text: str, choices: list[str]) -> dict[str, str] | None:
    data = forge.extract_json(text or "")
    if not isinstance(data, dict):
        return None
    out = {}
    for c in choices:
        v = data.get(c)
        if isinstance(v, (int, float)) and int(v) == v and 1 <= v <= 5:
            out[c] = str(int(v))
        else:
            return None
    return out


def rate(sheet: Path, out: Path, ask=None, claude: str = "claude", model: str = "sonnet") -> dict:
    if out.exists():
        raise FileExistsError(f"{out} มีอยู่แล้ว · ห้ามเขียนทับ")
    ask = ask or (
        lambda prompt: forge.ask_claude(
            prompt, claude=claude, model=model, runner=forge.run_process
        )
    )
    qs = load_sheet(sheet)
    log, lines = {"model": model, "cost_usd": 0.0, "failed": [], "replies": {}}, []
    for qid, rows in qs.items():
        choices = [r["choice"] for r in rows]
        scores = None
        for _ in range(2):  # ตอบผิดรูปแบบ = ถามซ้ำ 1 ครั้ง
            reply = ask(build_prompt(rows))
            log["cost_usd"] += reply.cost_usd
            log["model"] = reply.model or log["model"]
            scores = parse_scores(reply.text, choices) if reply.ok else None
            if scores:
                break
        log["replies"][qid] = scores or {}
        if not scores:
            log["failed"].append(qid)
        for r in rows:
            lines.append({**r, "score": (scores or {}).get(r["choice"], "")})
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "choice", "answer", "score"])
        w.writeheader()
        w.writerows(lines)
    log["cost_usd"] = round(log["cost_usd"], 4)
    out.with_suffix(".log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return log


def _scores(path: Path) -> dict[tuple[str, str], int]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {
            (r["id"], r["choice"]): int(r["score"]) for r in csv.DictReader(f) if r["score"].strip()
        }


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # คะแนนเท่ากัน = อันดับเฉลี่ย
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(cov / (va * vb), 3) if va and vb else 0.0


def agree(human: Path, judge: Path) -> dict:
    """ความตรงกันของคะแนนคนกับ AI (เฉพาะคำตอบที่ทั้งสองให้คะแนน) · ตรงเป๊ะ · ห่างไม่เกิน 1 · Spearman."""
    h, j = _scores(human), _scores(judge)
    keys = sorted(set(h) & set(j))
    if not keys:
        return {"n": 0}
    a, b = [h[k] for k in keys], [j[k] for k in keys]
    return {
        "n": len(keys),
        "exact": round(sum(x == y for x, y in zip(a, b, strict=True)) / len(keys), 3),
        "within_1": round(sum(abs(x - y) <= 1 for x, y in zip(a, b, strict=True)) / len(keys), 3),
        "spearman": spearman(a, b),
        "mean_human": round(sum(a) / len(a), 2),
        "mean_judge": round(sum(b) / len(b), 2),
    }


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.llm_judge")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rate")
    r.add_argument("sheet", type=Path)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--claude", default="claude")
    r.add_argument("--model", default="sonnet")
    a = sub.add_parser("agree")
    a.add_argument("human", type=Path)
    a.add_argument("judge", type=Path)
    x = p.parse_args(argv)
    if x.cmd == "rate":
        print(
            json.dumps(
                {
                    k: v
                    for k, v in rate(x.sheet, x.out, claude=x.claude, model=x.model).items()
                    if k != "replies"
                },
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps(agree(x.human, x.judge), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
