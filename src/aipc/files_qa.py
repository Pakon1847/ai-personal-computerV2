"""ถาม AI ในเครื่องเกี่ยวกับไฟล์ของฉัน (ฟีเจอร์ข้อ 4 ที่ Pakon อนุมัติ 2026-10-01).

- อ่านได้: .txt .md .csv .log (ข้อความ) และ .pdf (ผ่าน pdftotext ของ poppler-utils ที่มากับ
Raspberry Pi OS)
- เนื้อหาไฟล์ไม่ออกนอกเครื่อง: ระหว่างแนบไฟล์ แชทไม่ส่งต่อ Claude (ChatController ตรวจ)
- Pi 5 อ่าน prompt ~22 token/วิ → ส่งให้ AI เฉพาะส่วนที่เกี่ยวกับคำถาม ไม่เกิน EXCERPT_CHARS ตัวอักษร
  (แบ่งเป็นท่อน แล้วเลือกท่อนด้วย TF-IDF n-gram ตัวเดียวกับการ์ด 0018 · ไฟล์สั้น = ส่งทั้งไฟล์)
"""

from __future__ import annotations

import codecs
import math
import subprocess
from pathlib import Path

from aipc.skills.retrieval import grams

TEXT_TYPES = {".txt", ".md", ".csv", ".log"}
PDF_TYPES = {".pdf"}
MAX_FILE_BYTES = 5_000_000
EXCERPT_CHARS = 2400  # ~1,200–1,600 token ภาษาไทย → อ่านราว 1 นาทีบน Pi 5 (ไม่มีแคช)
CHUNK_CHARS = 600


class Unsupported(ValueError):
    pass


def supported(name: str) -> bool:
    return Path(name).suffix.lower() in TEXT_TYPES | PDF_TYPES


def extract(path: Path, runner=subprocess.run) -> str:
    """ข้อความในไฟล์ · ไฟล์ไม่รองรับ/ใหญ่เกิน/อ่านไม่ได้ = Unsupported พร้อมเหตุผลภาษาไทย."""
    ext = path.suffix.lower()
    if not supported(path.name):
        raise Unsupported("ยังอ่านได้แค่ไฟล์ข้อความ (.txt .md .csv) และ PDF")
    try:
        size = path.stat().st_size
    except OSError as e:
        raise Unsupported(f"เปิดไฟล์ไม่ได้: {e.strerror or e}") from e
    if size > MAX_FILE_BYTES:
        raise Unsupported("ไฟล์ใหญ่เกิน 5 MB")
    if ext in TEXT_TYPES:
        try:
            raw = path.read_bytes()
        except OSError as e:  # ไม่มีสิทธิ์อ่าน/ไฟล์ถูกล็อก (พบ 2026-10-12: ค้นไฟล์ตามเวลาล่มทั้งการ์ด)
            raise Unsupported(f"เปิดไฟล์ไม่ได้: {e.strerror or e}") from e
        # utf-16 ถอดได้แทบทุกไบต์ (ได้ขยะ) → ใช้เฉพาะไฟล์ที่มี BOM
        # ไม่มี BOM = utf-8 แล้วค่อย cp874 (ไฟล์ไทยจาก Windows เก่า)
        bom16 = raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
        encs = ("utf-16",) if bom16 else ("utf-8-sig", "cp874")
        for enc in encs:
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        raise Unsupported("อ่านตัวอักษรในไฟล์ไม่ออก")
    try:
        r = runner(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True,
                   timeout=30, check=False)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unsupported("อ่าน PDF ไม่ได้ (ไม่มี pdftotext หรือไฟล์ใหญ่เกิน)") from e
    text = (r.stdout or b"").decode("utf-8", "replace")
    if r.returncode != 0 or not text.strip():
        raise Unsupported("PDF นี้ไม่มีตัวอักษรให้อ่าน (อาจเป็นภาพสแกน)")
    return text


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """แบ่งตามย่อหน้า แล้วรวมให้ท่อนละไม่เกิน size ตัวอักษร (ย่อหน้ายาวตัดตรงขนาด)."""
    out, cur = [], ""
    for para in (p.strip() for p in text.replace("\r", "").split("\n\n")):
        if not para:
            continue
        while len(para) > size:
            out.append(para[:size])
            para = para[size:]
        if len(cur) + len(para) + 2 > size and cur:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


def excerpt(text: str, question: str, limit: int = EXCERPT_CHARS) -> tuple[str, bool]:
    """ส่วนของไฟล์ที่จะส่งให้ AI · (ข้อความ, ตัดมาบางส่วนไหม) · ท่อนที่เลือกเรียงตามลำดับในไฟล์."""
    text = text.strip()
    if len(text) <= limit:
        return text, False
    parts = chunks(text)
    docs = [grams(p) for p in parts]
    df: dict[str, int] = {}
    for d in docs:
        for g in d:
            df[g] = df.get(g, 0) + 1
    q = grams(question)

    def score(i: int) -> float:
        d = docs[i]
        return sum(
            math.log((1 + len(docs)) / (1 + df[g])) * min(c, d[g]) for g, c in q.items() if g in d
        )

    # คำถามกว้าง ๆ (สรุป) ให้ท่อนแรกได้เปรียบเล็กน้อย: ย่อหน้าแรกมักบอกว่าเอกสารเรื่องอะไร
    ranked = sorted(range(len(parts)), key=lambda i: (-(score(i) + (0.5 if i == 0 else 0)), i))
    picked, used = [], 0
    for i in ranked:
        if used + len(parts[i]) > limit:
            continue
        picked.append(i)
        used += len(parts[i]) + 2
    return "\n\n".join(parts[i] for i in sorted(picked)), True


def build_message(name: str, text: str, question: str) -> str:
    """ข้อความที่ส่งให้ AI ในเครื่อง: ส่วนของไฟล์ + คำถาม · บอก AI ให้ตอบจากไฟล์เท่านั้น."""
    part, cut = excerpt(text, question)
    note = " (บางส่วนที่เกี่ยวกับคำถาม)" if cut else ""
    return (f"เนื้อหาจากไฟล์ “{name}”{note}:\n---\n{part}\n---\n"
            f"ตอบจากเนื้อหาข้างบนเท่านั้น ถ้าในไฟล์ไม่มีคำตอบให้บอกตรง ๆ\nคำถาม: {question}")  # fmt: skip
