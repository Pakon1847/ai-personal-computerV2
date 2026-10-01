"""ค้นไฟล์ในเครื่องด้วยเนื้อหา · ไม่ใช้โมเดล (ไม่แย่ง RAM/CPU กับ AI ในเครื่อง).

ผล docs/benchmarks/2026-10-01-file-search

TF-IDF ของ n-gram ตัวอักษร (ภาษาไทยไม่เว้นวรรค · แบบเดียวกับการ์ด 0018) บนชื่อไฟล์ + เนื้อหาแบ่งเป็นท่อน ·
คะแนนไฟล์ = ท่อนที่ตรงที่สุด · ได้ข้อความตัวอย่างจากท่อนนั้นไปแสดง
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CHUNK = 300  # ตัวอักษรต่อท่อน · ไฟล์ยาวแบ่งท่อนเพื่อไม่ให้ไฟล์ยาวได้เปรียบ
N = (2, 3)


def grams(text: str) -> Counter:
    t = re.sub(r"\s+", "", text.lower())
    return Counter(t[i : i + k] for k in N for i in range(len(t) - k + 1))


@dataclass
class Hit:
    name: str
    score: float
    snippet: str


def _chunks(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= CHUNK:
        return [text] if text else []
    step = CHUNK * 2 // 3  # ซ้อนกัน 1/3 ไม่ให้ประโยคขาดกลางท่อน
    return [text[i : i + CHUNK] for i in range(0, len(text) - CHUNK // 3, step)]


class Index:
    def __init__(self, files: list[tuple[str, str]]):
        """files = [(ชื่อ, ข้อความ)]."""
        self.items: list[tuple[str, str]] = []  # (ชื่อไฟล์, ข้อความท่อน)
        for name, text in files:
            stem = re.sub(r"\.[A-Za-z0-9]+$", "", name).replace("-", " ").replace("_", " ")
            for c in _chunks(text) or [""]:
                self.items.append((name, f"{stem} {c}"))
        docs = [grams(t) for _, t in self.items]
        df = Counter(g for d in docs for g in d)
        n = len(docs)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, c: Counter) -> dict:
        v = {g: (1 + math.log(x)) * self.idf.get(g, 0) for g, x in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {g: x / norm for g, x in v.items()}

    def search(self, query: str, k: int = 5) -> list[Hit]:
        q = self._vec(grams(query))
        best: dict[str, tuple[float, str]] = {}
        for (name, text), v in zip(self.items, self.vecs, strict=True):
            s = sum(w * v.get(g, 0) for g, w in q.items())
            if s > best.get(name, (-1, ""))[0]:
                best[name] = (s, text)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
        return [Hit(name, round(s, 4), text[:160]) for name, (s, text) in ranked[:k] if s > 0]


# ---------- ค้นใน home ของผู้ใช้ (หน้า "ไฟล์ของฉัน") ----------
SKIP_DIRS = {"node_modules", "__pycache__", "venv", "snap", "site-packages"}
MAX_FILES = 400  # อ่านไม่เกินนี้ต่อการค้น (ไฟล์ใหม่สุดก่อน) · บอกผู้ใช้ถ้าถึงเพดาน


def candidates(root: Path, max_files: int = MAX_FILES) -> tuple[list[Path], bool]:
    """ไฟล์ที่อ่านได้ (txt md csv pdf) ใน root · ข้ามโฟลเดอร์ซ่อน/โปรแกรม · คืน (ไฟล์, ถึงเพดานไหม)."""
    from aipc import files_qa

    found: list[tuple[float, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]
        for name in filenames:
            if name.startswith(".") or not files_qa.supported(name):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size <= files_qa.MAX_FILE_BYTES:
                found.append((st.st_mtime, p))
    found.sort(reverse=True)
    return [p for _, p in found[:max_files]], len(found) > max_files


class HomeSearch:
    """จำข้อความที่อ่านแล้วตาม (path, mtime, size) · ค้นครั้งต่อไปอ่านเฉพาะไฟล์ใหม่/ที่แก้."""

    def __init__(self, root: Path):
        self.root = root
        self._cache: dict[str, tuple[float, int, str]] = {}

    def search(self, query: str, k: int = 8) -> tuple[list[Hit], int, bool]:
        """(ผล · จำนวนไฟล์ที่ค้น · ถึงเพดานไหม) · Hit.name = path เทียบกับ root."""
        from aipc import files_qa

        paths, capped = candidates(self.root)
        files, keep = [], {}
        for p in paths:
            key = str(p)
            try:
                st = p.stat()
            except OSError:
                continue
            old = self._cache.get(key)
            if old and old[0] == st.st_mtime and old[1] == st.st_size:
                text = old[2]
            else:
                try:
                    text = files_qa.extract(p)
                except files_qa.Unsupported:
                    text = ""
            keep[key] = (st.st_mtime, st.st_size, text)
            files.append((str(p.relative_to(self.root)), text))
        self._cache = keep
        if not files or not query.strip():
            return [], len(files), capped
        return Index(files).search(query, k), len(files), capped
