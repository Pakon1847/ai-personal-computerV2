"""เลือกสกิลของผู้ใช้ที่เกี่ยวข้องกับข้อความ k ตัว ก่อนส่งรายการเครื่องมือให้ AI (การ์ด 0018).

ปัญหา (วัดบน Pi 5): สกิล 1 ตัว ≈ +94 token · ~30 สกิล prompt เกิน ctx 4,096
· สกิลอัตโนมัติ (0017) ทำให้สกิลโตไม่จำกัด
แนวทาง: RAG-MCP (arXiv:2505.03275) ค้นเครื่องมือก่อน
· Tool2Vec (arXiv:2409.02141) แทนเครื่องมือด้วยตัวอย่างคำขอ
ตัวค้นไม่ใช้โมเดล: TF-IDF ของ n-gram ตัวอักษร 2–3 ตัว (ภาษาไทยไม่เว้นวรรค) บน ชื่อ + คำอธิบาย + ตัวอย่าง + คำสำคัญ
"""

from __future__ import annotations

import math
import re
from collections import Counter

from aipc.skills.manifest import Manifest

TOP_K = 5


def grams(text: str, n=(2, 3)) -> Counter:
    t = re.sub(r"\s+", "", text.lower())
    return Counter(t[i : i + k] for k in n for i in range(len(t) - k + 1))


def skill_text(s: Manifest) -> str:
    return " ".join([s.name, s.description, *s.examples, *s.keywords])


class Index:
    def __init__(self, skills: list[Manifest]):
        self.skills = list(skills)
        docs = [grams(skill_text(s)) for s in self.skills]
        df = Counter(g for d in docs for g in d)
        self.idf = {g: math.log((1 + len(docs)) / (1 + c)) + 1 for g, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, c: Counter) -> dict:
        v = {g: (1 + math.log(x)) * self.idf.get(g, 0) for g, x in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {g: x / norm for g, x in v.items()}

    def top(self, text: str, k: int) -> list[Manifest]:
        """k สกิลที่ใกล้ข้อความที่สุด (คะแนนเท่ากัน = ลำดับเดิม)."""
        q = self._vec(grams(text))
        scored = [(-sum(w * v.get(g, 0) for g, w in q.items()), i) for i, v in enumerate(self.vecs)]
        return [self.skills[i] for _, i in sorted(scored)[:k]]


def pick(user_skills: list[Manifest], text: str, k: int = TOP_K) -> list[Manifest]:
    """สกิลของผู้ใช้ที่จะส่งให้ AI · ≤ k ตัว = ส่งทั้งหมด (เหมือนก่อนมีการ์ดนี้) · ไม่มีข้อความ = ไม่ส่ง."""
    if len(user_skills) <= k:
        return list(user_skills)
    if not text.strip():
        return []
    return Index(user_skills).top(text, k)
