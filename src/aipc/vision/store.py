"""ที่เก็บแม่แบบใบหน้าของผู้ใช้ (การ์ด 0005 ข้อ 5) · ชั่วคราวจนกว่า ADR-003/004 ตัดสิน.

แม่แบบ = embedding เฉลี่ยจากการลงทะเบียน (ตัวเลข 128 ตัว) · **ไม่มีภาพ** · แต่ยังเป็นข้อมูลชีวภาพ
ตาม PDPA มาตรา 26 จึง:
- เก็บได้เฉพาะเมื่อมีบันทึกความยินยอม (เวลา + ฉบับของข้อความที่ผู้ใช้เห็น)
- ไฟล์อ่านได้เฉพาะเจ้าของ (0600) ใน home ของผู้ใช้ (ปลายทาง: home ที่เข้ารหัสด้วย fscrypt · ADR-003)
- ลบ = ลบไฟล์หลัก สำรอง และไฟล์ชั่วคราวทั้งหมด → ใช้ใบหน้าไม่ได้ทันที

**ข้อจำกัดที่ต้องบอก:** microSD กระจายการเขียน (wear leveling) การลบไฟล์จึงไม่รับประกันว่าข้อมูลเก่า
หายจากชิปจริง · ทางแก้คือเข้ารหัส home (ADR-003) แล้วลบกุญแจ · ยังไม่มีในรอบนี้

แม่แบบผูกกับโมเดล (sha256 ของ SFace): embedding จากโมเดลต่างรุ่นเทียบกันไม่ได้ →
โมเดลเปลี่ยน = แม่แบบใช้ไม่ได้ ต้องลงทะเบียนใหม่ (ไม่เดาว่ายังใช้ได้ · H5)

เขียนแบบเดียวกับนัดหมาย (H1): ไฟล์ชั่วคราว → fsync → rename · เก็บรุ่นก่อนที่ .bak
"""

from __future__ import annotations

import base64
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aipc.vision import matching, models

VERSION = 1
# ฉบับของข้อความขอความยินยอม · เปลี่ยนข้อความ = เปลี่ยนเลข (แม่แบบเก่ายังอ้างฉบับที่ผู้ใช้เห็นจริง)
CONSENT_VERSION = "face-consent-1"
DIM = 128


def default_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "aipc" / "face-template.json"


@dataclass(frozen=True)
class Consent:
    given_at: str  # ISO 8601 พร้อมเขตเวลา
    version: str = CONSENT_VERSION
    purpose: str = "ระบุบัญชีที่หน้า Login (ใบหน้าเป็นความสะดวก รหัสผ่านยังเป็นกุญแจ)"


@dataclass(frozen=True)
class Stored:
    vector: np.ndarray
    frames: int
    created: str
    consent: Consent
    model_sha256: str


class FaceStore:
    def __init__(self, path: Path | None = None, model_sha256: str = models.SFACE.sha256):
        self.path = path or default_path()
        self.bak = self.path.with_name(self.path.name + ".bak")
        self.tmp = self.path.with_name(self.path.name + ".tmp")
        self.model_sha256 = model_sha256
        self.problem = ""  # เหตุผลที่ load() คืน None ทั้งที่มีไฟล์ (ให้หน้าจอบอกผู้ใช้)

    # ---------- เขียน ----------
    def save(self, vector, frames: int, created: str, consent: Consent | None) -> None:
        if consent is None or not consent.given_at:
            raise PermissionError("ไม่มีบันทึกความยินยอม · เก็บแม่แบบใบหน้าไม่ได้ (PDPA ม.26)")
        v = matching.l2_normalize(vector)
        if v.shape != (DIM,):
            raise ValueError(f"แม่แบบต้องมี {DIM} ค่า")
        payload = {
            "version": VERSION,
            "model_sha256": self.model_sha256,
            "vector_f32_b64": base64.b64encode(v.astype("<f4").tobytes()).decode("ascii"),
            "frames": int(frames),
            "created": created,
            "consent": {"given_at": consent.given_at, "version": consent.version,
                        "purpose": consent.purpose},
        }  # fmt: skip
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            shutil.copy2(self.path, self.bak)
        fd = os.open(self.tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tmp, self.path)
        for p in (self.path, self.bak):
            if p.exists():
                os.chmod(p, 0o600)

    # ---------- อ่าน ----------
    def _read(self, p: Path) -> Stored:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("version") != VERSION:
            raise ValueError("รุ่นไฟล์ไม่รู้จัก")
        vec = np.frombuffer(base64.b64decode(d["vector_f32_b64"]), dtype="<f4").astype(np.float32)
        if vec.shape != (DIM,):
            raise ValueError("ขนาดแม่แบบผิด")
        c = d["consent"]
        consent = Consent(c["given_at"], c["version"], c["purpose"])
        vec = matching.l2_normalize(vec)
        return Stored(vec, int(d["frames"]), str(d["created"]), consent, str(d["model_sha256"]))

    def load(self) -> Stored | None:
        """None = ยังไม่ลงทะเบียน หรือใช้ไม่ได้ (ดูเหตุผลที่ self.problem)."""
        self.problem = ""
        if not self.path.exists() and not self.bak.exists():
            return None
        stored = None
        for p in (self.path, self.bak):
            try:
                stored = self._read(p)
                break
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if stored is None:
            self.problem = "ไฟล์แม่แบบใบหน้าเสีย · ลงทะเบียนใหม่ได้ (ใช้รหัสผ่านเข้าเครื่องได้ตามปกติ)"
            return None
        if stored.model_sha256 != self.model_sha256:
            self.problem = "โมเดลจดจำใบหน้าเปลี่ยนรุ่น · แม่แบบเดิมใช้ไม่ได้ ต้องลงทะเบียนใหม่"
            return None
        return stored

    # ---------- ลบ (PDPA) ----------
    def delete(self) -> bool:
        """ลบทุกไฟล์ที่เกี่ยวกับแม่แบบ · คืน True ถ้ามีอะไรถูกลบ."""
        removed = False
        for p in (self.path, self.bak, self.tmp):
            try:
                p.unlink()
                removed = True
            except FileNotFoundError:
                pass
        return removed
