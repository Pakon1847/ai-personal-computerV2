"""วัดคุณภาพภาษาไทยของ LLM แบบให้คนให้คะแนนโดยไม่รู้ว่าคำตอบมาจากโมเดลไหน (ADR-007 เกณฑ์ข้อ 1).

ใช้ standard library อย่างเดียว (รันบน Pi ที่เพิ่งลง OS ได้) · 3 ขั้น:

1. ask   — ส่งคำถาม 30 ข้อให้ llama-server ที่รันโมเดลหนึ่งตัวอยู่ แล้วเก็บคำตอบ + เวลา ลงไฟล์ JSON
           (รันทีละโมเดล: เปิด llama-server ด้วยโมเดล A → ask → ปิด → โมเดล B → ask ...)
2. sheet — รวมคำตอบทุกโมเดลเป็นแบบให้คะแนน (CSV) โดยสลับลำดับและใช้ชื่อ A/B/C แทนชื่อโมเดล
           ไฟล์เฉลยว่าตัวอักษรไหนคือโมเดลไหนแยกไว้อีกไฟล์ ผู้ให้คะแนนต้องไม่เปิดดู
3. score — อ่าน CSV ที่คน 2 คนให้คะแนนแล้ว (1–5) รวมคะแนนเฉลี่ยต่อโมเดล เทียบเกณฑ์ ≥ 3.5

ทำไมต้องปิดชื่อโมเดล: ถ้าผู้ให้คะแนนรู้ว่าตัวไหนคือโมเดลที่ปรับจูนภาษาไทย อาจให้คะแนนเอียงโดยไม่ตั้งใจ
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
QUESTIONS = REPO / "tests" / "data" / "llm_thai_questions.json"
# ค่าเดียวกันทุกโมเดลเพื่อให้เทียบกันได้ · temperature ต่ำ = คำตอบนิ่ง (ตามคำแนะนำของ Typhoon)
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 512}
SCORES = {"1", "2", "3", "4", "5"}


def chat(server: str, system: str, question: str, timeout: float = 600) -> dict:
    """ถาม llama-server 1 ข้อ (API แบบ OpenAI) · คืน answer, seconds, usage, timings."""
    body = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}],
        "stream": False,
        **SAMPLING,
        # Gemma 4 / Qwen3: ไม่ปิดโหมดคิด = คิดจนหมด max_tokens แล้วคำตอบว่าง (พบ 2026-09-30) ·
        # แอปส่งค่านี้ทุกครั้ง
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        server.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return {
        "answer": data["choices"][0]["message"]["content"],
        "seconds": round(time.monotonic() - t0, 2),
        "usage": data.get("usage", {}),
        "timings": data.get(
            "timings", {}
        ),  # llama-server ใส่ prompt_ms / predicted_per_second มาด้วย
    }


def ask(server: str, label: str, questions: Path, out: Path, ask_one=chat) -> dict:
    if out.exists():
        raise FileExistsError(f"{out} มีอยู่แล้ว · ผลเก่าห้ามเขียนทับ ตั้งชื่อใหม่")
    qs = json.loads(questions.read_text(encoding="utf-8"))
    rows = []
    for q in qs["questions"]:
        r = ask_one(server, qs["system_prompt"], q["text"])
        rows.append({"id": q["id"], **r})
        print(f"{q['id']} {r['seconds']} วิ", file=sys.stderr)
    result = {"label": label, "date": date.today().isoformat(), "sampling": SAMPLING,
              "questions_file": questions.name, "answers": rows}  # fmt: skip
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def sheet(answer_files: list[Path], questions: Path, out_dir: Path, seed: int = 20260928) -> None:
    """แบบให้คะแนน rate-me.csv (ไม่มีชื่อโมเดล) + key.json (เฉลย ห้ามให้ผู้ให้คะแนนเห็น)."""
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} มีอยู่แล้ว · ห้ามเขียนทับ")
    qs = {
        q["id"]: q["text"] for q in json.loads(questions.read_text(encoding="utf-8"))["questions"]
    }
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in answer_files]
    rng = random.Random(seed)
    letters = "ABCDEFGH"[: len(runs)]
    key, lines = {}, []
    for qid, text in qs.items():
        order = list(range(len(runs)))
        rng.shuffle(order)  # สลับลำดับทุกข้อ ผู้ให้คะแนนจะจำไม่ได้ว่า A คือโมเดลเดิม
        for letter, i in zip(letters, order, strict=True):
            answer = next(a["answer"] for a in runs[i]["answers"] if a["id"] == qid)
            key[f"{qid}:{letter}"] = runs[i]["label"]
            lines.append(
                {"id": qid, "question": text, "choice": letter, "answer": answer, "score": ""}
            )
    out_dir.mkdir(parents=True)
    with (out_dir / "rate-me.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "choice", "answer", "score"])
        w.writeheader()
        w.writerows(lines)
    (out_dir / "key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    rubric = json.loads(questions.read_text(encoding="utf-8")).get("rubric", {})
    (out_dir / "rate-me.html").write_text(rating_page(lines, rubric), encoding="utf-8")


def rating_page(lines: list[dict], rubric: dict) -> str:
    """หน้าให้คะแนนแบบออฟไลน์ (เปิดในเบราว์เซอร์) · ไม่มีชื่อโมเดล ·
    ส่งออก CSV รูปแบบเดียวกับ rate-me.csv ให้ score อ่าน.

    คะแนนที่กดเก็บใน localStorage ของเบราว์เซอร์นั้น (ปิดแล้วเปิดใหม่ทำต่อได้) · ไม่ส่งอะไรออกนอกเครื่อง
    """
    data = json.dumps({"rows": lines, "rubric": rubric}, ensure_ascii=False).replace(
        "</", "<" + chr(92) + "/"
    )
    page = (Path(__file__).with_name("rating_page.html")).read_text(encoding="utf-8")
    return page.replace("__DATA__", data)


def score(key_file: Path, rating_files: list[Path], minimum: float = 3.5) -> dict:
    """คะแนนเฉลี่ยต่อโมเดล (รวมทุกผู้ให้คะแนน) · ช่องว่างหรือค่านอก 1–5 = หยุด ไม่เดา."""
    key = json.loads(key_file.read_text(encoding="utf-8"))
    per_label: dict[str, list[int]] = {}
    per_rater: dict[str, dict[str, list[int]]] = {}
    for rf in rating_files:
        with rf.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                s = row["score"].strip()
                if s not in SCORES:
                    raise ValueError(
                        f"{rf.name} ข้อ {row['id']}{row['choice']}: คะแนน '{s}' ต้องเป็น 1–5"
                    )
                label = key[f"{row['id']}:{row['choice']}"]
                per_label.setdefault(label, []).append(int(s))
                per_rater.setdefault(rf.stem, {}).setdefault(label, []).append(int(s))
    out = {}
    for label, xs in sorted(per_label.items()):
        mean = statistics.mean(xs)
        out[label] = {"mean": round(mean, 2), "n": len(xs), "passes": mean >= minimum,
                      "by_rater": {r: round(statistics.mean(v[label]), 2)
                                   for r, v in per_rater.items() if label in v}}  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.llm_quality")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="ถามคำถาม 30 ข้อกับ llama-server ที่รันอยู่")
    a.add_argument("--server", default="http://127.0.0.1:8080")
    a.add_argument("--label", required=True, help="ชื่อสั้นของโมเดล เช่น typhoon25-4b-q4km")
    a.add_argument("--questions", type=Path, default=QUESTIONS)
    a.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sheet", help="รวมคำตอบเป็นแบบให้คะแนนที่ไม่มีชื่อโมเดล")
    s.add_argument("answers", type=Path, nargs="+")
    s.add_argument("--questions", type=Path, default=QUESTIONS)
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("score", help="รวมคะแนนจากผู้ให้คะแนน")
    c.add_argument("--key", type=Path, required=True)
    c.add_argument("ratings", type=Path, nargs="+")
    args = p.parse_args(argv)
    if args.cmd == "ask":
        ask(args.server, args.label, args.questions, args.out)
    elif args.cmd == "sheet":
        sheet(args.answers, args.questions, args.out)
    else:
        res = score(args.key, args.ratings)
        print("| โมเดล | เฉลี่ย | จำนวนคะแนน | แยกผู้ให้คะแนน | ผ่าน ≥ 3.5 |\n|---|---|---|---|---|")
        for label, r in res.items():
            raters = ", ".join(f"{k} {v}" for k, v in r["by_rater"].items())
            verdict = "ผ่าน" if r["passes"] else "ไม่ผ่าน"
            print(f"| {label} | {r['mean']} | {r['n']} | {raters} | {verdict} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
