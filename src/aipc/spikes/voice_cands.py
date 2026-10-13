"""การ์ด 0026 (spike): สร้างประโยคตัวเลือกจากข้อความที่ถอดอิสระ แล้วตัดสินว่า ทำเลย / ถามกลับ / ไม่ใช่คำสั่ง.

ทำไมต้องสร้างจากข้อความที่ถอดได้: whisper มักได้ยินคำค้นถูกแต่ได้ยินต้นคำสั่งผิด ("คนหาราคาทองหน่อย") ·
ถ้าให้คะแนนแค่ "ค้นหาราคาทองวันนี้" ที่เดาเอง คะแนนจะแย่เพราะท้ายประโยคไม่ตรงเสียง ·
จึงเอา "ต้นคำสั่งที่ถูก + ส่วนที่เหลือของข้อความที่ได้ยิน" ไปให้ whisper ให้คะแนน
(FIX ถอดรวดเดียว ~30 ms/ประโยค บน Pi 5)

ทั้งไฟล์เป็นโค้ดล้วน (ไม่มี LLM · H6) · ตัวเลขเกณฑ์ (ts tc m) ตั้งจากชุดพัฒนาเท่านั้น (H9)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache

from aipc.skills import browse
from aipc.voice import stt

# ต้นคำค้นหา: ส่วนที่เหลือของประโยค = คำค้น
SEARCH_STEMS = ["ค้นหา", "หา", "ช่วยค้นหา", "ช่วยหา", "เสิร์ช", "ค้น", "กูเกิล"]
# คำสั่งตายตัว (ประโยคเต็ม · ส่วนที่เหลือควรเป็นคำลงท้าย เช่น "หน่อย")
FIXED = [
    "ย้อนกลับ",
    "กลับไปหน้าก่อน",
    "ถอยกลับ",
    "ไปข้างหน้า",
    "เดินหน้า",
    "โหลดใหม่",
    "รีเฟรช",
    "โหลดหน้าใหม่",
    "เลื่อนลง",
    "เลื่อนขึ้น",
    "เลื่อนหน้าลง",
    "เลื่อนหน้าขึ้น",
    "ปิดแท็บ",
    "ปิดหน้านี้",
    "กลับไปแอป",
    "ไปที่แอป",
    "เปิดกูเกิล",
    "เปิดยูทูบ",
    "เปิดวิกิพีเดีย",
    "เปิดจีเมล",
    "เปิดกูเกิลแมพ",
    "รีโหลด",
    "กลับไปหน้าแชท",
    "กลับไปหน้าผู้ช่วย",
    *(f"{v}ลิงก์{n}" for v in ("เข้า", "เปิด", "กด", "คลิก", "กดเข้า") for n in ("แรก", "ที่สอง", "ที่สาม")),
    *(f"เข้าลิงก์ที่{n}" for n in ("หนึ่ง", "สี่", "ห้า")),
    *(f"เข้า{w}{n}" for w in ("เว็บ", "ผลลัพธ์") for n in ("แรก", "ที่สอง", "ที่สาม", "ที่สี่", "ที่ห้า")),
]
OPEN_TAILS = ["แล้วเข้าลิงก์แรก", "แล้วเข้าลิงก์ที่สอง", "แล้วเข้าลิงก์ที่สาม"]

_MARKS = re.compile(r"[ัิ-ฺ็-๎]")  # สระบน/ล่าง วรรณยุกต์ ไม้ไต่คู้ การันต์ (ได้ยินเพี้ยนบ่อย)
_LOOP = re.compile(r"(.{2,}?)(?:\s*\1){2,}")  # ข้อความเดิมซ้ำติดกัน 3 ครั้งขึ้นไป = whisper วนซ้ำ


def skeleton(s: str) -> str:
    return _MARKS.sub("", re.sub(r"\s+", "", s))


@lru_cache(maxsize=65536)
def _meaning(text: str) -> str:
    return json.dumps([c.as_dict() for c in browse.parse(stt.clean(text))], ensure_ascii=False)


def meaning(text: str) -> list[dict]:
    """ความหมายตามกฎเดิม (aipc.skills.browse) · จำผลไว้ (ตัววิเคราะห์ลองเกณฑ์หลายร้อยชุดบนข้อความเดิม)."""
    return json.loads(_meaning(text))


def looped(text: str) -> bool:
    return bool(_LOOP.search(text))


def drops_words(heard: str, cand: str) -> bool:
    """ตัวเลือกสั้นกว่าสิ่งที่ได้ยินมาก = ตัดคำที่พูดทิ้ง ("ย้อนกลับเมื่อกี้ที่ปรับเสียง" ≠ "ย้อนกลับ") ·
    ยกเว้น whisper วนซ้ำ (ข้อความที่ได้ยินยาวเพราะซ้ำ ไม่ใช่เพราะพูดยาว)."""
    return not looped(heard) and len(skeleton(heard)) - len(skeleton(cand)) > 4


def stem_fit(stem: str, heard: str) -> tuple[float, list[int]]:
    """ตอนต้นของ heard คล้าย stem แค่ไหน (0–1) + จุดตัด (ตำแหน่งตัวอักษรใน heard) ที่เข้ากันที่สุด ≤ 2 จุด."""
    a = skeleton(stem)
    fits: list[tuple[float, int]] = []
    for k in range(1, len(heard) + 1):
        h = skeleton(heard[:k])
        if abs(len(h) - len(a)) > 2 or (k < len(heard) and _MARKS.match(heard[k])):
            continue  # ไม่ตัดหน้าสระบน/วรรณยุกต์ (ตัดกลางพยางค์)
        fits.append((SequenceMatcher(None, a, h).ratio(), k))
    fits.sort(key=lambda x: -x[0])
    cuts: list[int] = []
    for r, k in fits[:2]:
        if r >= fits[0][0] - 0.1:  # จุดตัดที่สองเฉพาะเมื่อเข้ากันพอ ๆ กับจุดแรก
            cuts.append(k)
    return (fits[0][0] if fits else 0.0), cuts


def candidates(heard: str, keep: int = 8) -> list[str]:
    """ประโยคตัวเลือกที่จะให้ whisper ให้คะแนน (ไม่รวมข้อความที่ถอดอิสระเอง).

    keep = จำนวนต้นคำที่คล้ายตอนต้นของสิ่งที่ได้ยินที่สุดที่เก็บไว้ (คุมเวลา: ~3 ประโยคต่อต้นคำ)."""
    heard = re.sub(r"\s+", " ", heard.strip())
    fits = sorted(((stem_fit(s, heard), s) for s in SEARCH_STEMS + FIXED), key=lambda x: -x[0][0])[
        :keep
    ]
    out: list[str] = []

    def add(s: str) -> None:
        s = s.strip()
        # กฎแปลไม่ได้ = ต่อให้คะแนนดีก็ทำอะไรไม่ได้ → ไม่เสียเวลาให้คะแนน
        if s and s != heard and s not in out and meaning(s) and not drops_words(heard, s):
            out.append(s)

    for (_, cuts), stem in fits:
        if stem in FIXED:
            add(stem)  # พูดคำสั่งเปล่า ๆ
        for k in cuts:
            rest = heard[k:].strip()
            add(f"{stem}{rest}")
            # ค้นหาแล้วเข้าลิงก์: ท่อนหลัง "แล้ว…" ได้ยินเพี้ยนบ่อย → ลองแทนด้วยคำสั่งเปิดลิงก์ที่ถูก
            if stem in SEARCH_STEMS and (j := rest.rfind("แล้ว")) > 0:
                for tail in OPEN_TAILS:
                    add(f"{stem}{rest[:j]}{tail}")
    return out


@dataclass
class Decision:
    what: str  # "do" ทำเลย · "ask" ถามกลับ · "chat" ไม่ใช่คำสั่ง (ไปทางเดิมของแอป)
    commands: list[dict]
    gap: float | None = None  # คะแนนข้อความที่ถอดอิสระ − คะแนนคำสั่งที่เลือก (ยิ่งน้อยยิ่งตรงเสียง)


def decide(
    heard: str, free_lp: float, scored: list[tuple[str, float]], ts: float, tc: float, m: float
) -> Decision:
    """เลือกจากคะแนน.

    - ข้อความที่ถอดอิสระก็เป็นตัวเลือกหนึ่ง (ถ้ากฎแปลเป็นคำสั่งได้) — ไม่งั้นคำสั่งที่ได้ยินชัดอยู่แล้วจะแพ้ตัวเลือกที่เพี้ยน
    - คำสั่งที่ดีที่สุดห่างจากข้อความที่ถอดอิสระเกินเกณฑ์ = ไม่ใช่คำสั่ง · เกณฑ์แยก:
      ค้นหา ts (เติมต้นคำ "ค้นหา" ให้ประโยคไหนก็ได้ จึงต้องเข้มกว่า) · อื่น ๆ tc
    - คำสั่งอันดับ 2 ที่ความหมายต่างกัน ห่างไม่ถึง m = ไม่แน่ใจ → ถามกลับ
    - whisper วนซ้ำ = ข้อความที่ถอดอิสระเชื่อไม่ได้ → ทำเลยเฉพาะเมื่อคำสั่งได้คะแนนดีกว่าข้อความที่วนซ้ำ · ไม่งั้นถามกลับ
    - ตัวเลือกที่ตัดคำที่พูดทิ้ง (drops_words) ไม่นับ
    """
    best: dict[str, tuple[float, list[dict]]] = {}
    for text, lp in [(heard, free_lp), *scored]:
        if lp is None or drops_words(heard, text):
            continue
        mean = meaning(text)
        if not mean:
            continue
        key = json.dumps(mean, ensure_ascii=False, sort_keys=True)
        if key not in best or lp > best[key][0]:
            best[key] = (lp, mean)
    ranked = sorted(best.values(), key=lambda x: -x[0])
    if not ranked:
        return Decision("chat", [])
    lp, mean = ranked[0]
    gap = round(free_lp - lp, 2)
    limit = ts if any(c["kind"] == "search" for c in mean) else tc
    if gap > limit:
        return Decision("chat", [], gap)
    if (looped(heard) and gap >= 0) or (len(ranked) > 1 and lp - ranked[1][0] < m):
        return Decision("ask", mean, gap)
    return Decision("do", mean, gap)
