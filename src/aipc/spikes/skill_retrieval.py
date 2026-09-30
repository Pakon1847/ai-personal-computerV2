"""ลองค้นเฉพาะสกิลที่เกี่ยวข้อง (top-k) ก่อนส่งรายการเครื่องมือให้ AI (ข้อเสนอ 2026-10-01 หัวข้อ 3 · การ์ด 0018 ร่าง).

    python -m aipc.spikes.skill_retrieval

อ้างอิง: RAG-MCP (arXiv:2505.03275) ค้นเครื่องมือก่อน
· Tool2Vec (arXiv:2409.02141) แทนเครื่องมือด้วย "ตัวอย่างคำขอ"
ตัวค้นแบบไม่ต้องมีโมเดล: TF-IDF ของ n-gram ตัวอักษร (ภาษาไทยไม่เว้นวรรค)
· เทียบข้อความกับ ชื่อ + คำอธิบาย + ตัวอย่าง + คำสำคัญ
คลังสกิล 21 ตัว = ในตัว 6 + ที่ Claude สร้างในปลายทางจริง 5 + ที่ Claude เขียนในชุดวัดผู้เขียนสกิล 10
วัด: สกิลที่ถูกอยู่ใน k อันดับแรกไหม (Recall@k) · ประโยค = ชุดเลือกสกิล 58 ข้อ (ข้อที่คาดว่าเป็นสกิล) + ชุดสำนวนอื่น 15 ข้อ
**เป็นการดูความเป็นไปได้ (feasibility) ไม่ใช่ผลประเมิน** · ชุดข้อมูลเหล่านี้เคยใช้กับงานอื่นแล้ว
"""

from __future__ import annotations

import json
import math
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

from aipc.skills import manifest, userskills

REPO = Path(__file__).resolve().parents[3]


def grams(text: str, n=(2, 3)) -> Counter:
    t = re.sub(r"\s+", "", text.lower())
    return Counter(t[i : i + k] for k in n for i in range(len(t) - k + 1))


class Index:
    def __init__(self, skills: list[manifest.Manifest]):
        self.skills = skills
        docs = [grams(" ".join([s.name, s.description, *s.examples, *s.keywords])) for s in skills]
        df = Counter(g for d in docs for g in d)
        self.idf = {g: math.log((1 + len(docs)) / (1 + c)) + 1 for g, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, c: Counter) -> dict:
        v = {g: (1 + math.log(x)) * self.idf.get(g, 0) for g, x in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {g: x / norm for g, x in v.items()}

    def top(self, text: str, k: int) -> list[str]:
        q = self._vec(grams(text))
        scores = [
            (sum(w * v.get(g, 0) for g, w in q.items()), s.id)
            for s, v in zip(self.skills, self.vecs, strict=True)
        ]
        return [i for _, i in sorted(scores, reverse=True)[:k]]


def pool() -> list[manifest.Manifest]:
    skills = manifest.load_builtin()
    with tempfile.TemporaryDirectory() as d:
        store = userskills.UserSkills(Path(d))
        for r in json.loads(
            (REPO / "docs/benchmarks/2026-09-30-auto-skill/e2e-r2.json").read_text(encoding="utf-8")
        )["rows"]:
            store.install(r["skill_md"], skills + store.load(), request=r["text"])
        extra = store.load()
    for p in sorted((REPO / "docs/benchmarks/2026-09-30-skill-author/claude").glob("*.md")):
        m = manifest.load(p)
        if m.id not in {s.id for s in [*skills, *extra]}:
            extra.append(m)
    return skills + extra


def main() -> int:
    skills = pool()
    idx = Index([s for s in skills if s.id != "system-command"])
    sel = json.loads((REPO / "tests/data/skill_selection.json").read_text(encoding="utf-8"))[
        "items"
    ]
    para = json.loads((REPO / "tests/data/auto_skill_paraphrase.json").read_text(encoding="utf-8"))[
        "items"
    ]
    cases = [(i["text"], i["expect"]) for i in sel if i["expect"] not in ("none", "system-command")]
    cases += [(i["text"], i["expect"]) for i in para]
    print(f"คลัง {len(idx.skills)} สกิล · ประโยค {len(cases)}")
    t0 = time.perf_counter()
    for k in (1, 3, 5, 8):
        hit = sum(exp in idx.top(t, k) for t, exp in cases)
        print(f"Recall@{k}: {hit}/{len(cases)} = {hit / len(cases):.0%}")
    ms = (time.perf_counter() - t0) / (4 * len(cases)) * 1000
    print(f"เวลาต่อประโยค ~{ms:.1f} ms (วินโดวส์)")
    for t, exp in cases:
        got = idx.top(t, 5)
        if exp not in got:
            print(f"  พลาด@5: {t[:40]} → คาด {exp} · ได้ {got}")
    # แบบที่เสนอ: สกิลในตัวส่งทุกครั้ง (ส่วนต้นคงที่ แคชใช้ได้) · ค้นเฉพาะสกิลของผู้ใช้
    builtin = {s.id for s in manifest.load_builtin()}
    uidx = Index([s for s in skills if s.id not in builtin])
    ucases = [(t, e) for t, e in cases if e not in builtin]
    print(
        f"แบบเสนอ: สกิลในตัว {len(builtin)} ตัวส่งเสมอ · "
        f"ค้นในสกิลของผู้ใช้ {len(uidx.skills)} ตัว · ประโยค {len(ucases)}"
    )
    for k in (1, 3, 5):
        hit = sum(e in uidx.top(t, k) for t, e in ucases)
        print(f"  Recall@{k} (สกิลของผู้ใช้): {hit}/{len(ucases)} = {hit / len(ucases):.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
