"""สร้างข้อมูลสำหรับหน้าตรวจคำตอบ (artifact · db) จากผลชุดสอบจบ · ตรวจแบบปิดชื่อระบบ.

    python docs/benchmarks/2026-09-30-exam/rating_seed.py <ไฟล์ผล.json>... --out ops.json

- เฉพาะข้อที่มีคำตอบเป็นข้อความ (AI ในเครื่องหรือ Claude ตอบ) · ข้อที่ไปคำสั่งเครื่อง/สกิล ตัววัดตัดสินเองแล้ว
- ชื่อระบบ → ตัวอักษร (ก ข ค …) ตามลำดับไฟล์ที่ส่งมา · ตารางจับคู่อยู่ keys/map (เจ้าของหน้าอ่านได้คนเดียว)
- need = ตัวตรวจอัตโนมัติไม่ชัด (check / cloud-answered / cloud-failed / fabricated)
  + สุ่ม 20% ของข้อที่ผ่านอัตโนมัติ (seed คงที่ ได้ชุดเดิมทุกครั้ง)
- --out เป็นโฟลเดอร์: เอกสารละไฟล์ + batches.json (ArtifactData batch ครั้งละไม่เกิน 50 · อ้าง file_path)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

LETTERS = "กขคงจฉชซ"
DATASET = Path(__file__).resolve().parents[3] / "tests" / "data" / "exam_questions.json"
NEED = {"check", "cloud-answered", "cloud-failed", "fabricated"}


def main(argv: list[str]) -> int:
    i = argv.index("--out")
    out = Path(argv[i + 1])
    files = [Path(a) for a in argv[:i] + argv[i + 2 :]]
    items = {i["id"]: i for i in json.loads(DATASET.read_text(encoding="utf-8"))["items"]}
    rng = random.Random(20260930)
    ops, keys = [], {"note": "ตัวอักษร → ระบบ (เปิดหลังตรวจเสร็จ)"}
    for letter, f in zip(LETTERS, files, strict=False):
        res = json.loads(f.read_text(encoding="utf-8"))
        label = res["label"]
        keys[f"ระบบ {letter}"] = label
        for r in res["rows"]:
            if r["by"] == "rule" or r["route"] not in ("chat", "ask-cloud"):
                continue
            need = r["auto"] in NEED or rng.random() < 0.2
            doc = {
                "qid": r["id"],
                "cat": r["cat"],
                "q": r["q"],
                "ref": items[r["id"]].get("ref", ""),
                "text": (r.get("text") or "")[:4000],
                "blind": f"ระบบ {letter}",
                "order": rng.random(),
                "need": need,
            }
            ops.append({"op": "set", "path": f"answers/{label}__{r['id']}", "data": doc})
    ops.append({"op": "set", "path": "keys/map", "data": keys})
    out.mkdir(parents=True, exist_ok=True)
    writes = []
    for o in ops:
        coll, doc_id = o["path"].split("/")
        f = out / f"{coll}__{doc_id}.json"
        f.write_text(json.dumps(o["data"], ensure_ascii=False), encoding="utf-8")
        writes.append(
            {"op": "set", "collection": coll, "doc_id": doc_id, "file_path": f.as_posix()}
        )
    batches = [writes[i : i + 50] for i in range(0, len(writes), 50)]
    (out / "batches.json").write_text(json.dumps(batches, ensure_ascii=False), encoding="utf-8")
    need = sum(1 for o in ops if o["data"].get("need"))
    print(f"{len(ops)} เอกสาร · {len(batches)} ชุด · ต้องตรวจ {need}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
