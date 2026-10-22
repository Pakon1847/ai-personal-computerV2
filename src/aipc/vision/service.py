"""แกนของ visiond: สแกนหน้าที่หน้า Login แล้วเข้าระบบได้เลย (การ์ด 0015 หัวข้อ 12 · Pakon ตัดสิน 2026-09-30).

ส่วนนี้เป็น Python ล้วน ไม่แตะกล้อง socket หรือ PAM เอง (ส่งเข้ามาทางพารามิเตอร์) → เทสต์บนวินโดวส์ได้

- **Gallery** แม่แบบของบัญชีที่ **เจ้าของเปิด** "เข้าเครื่องด้วยใบหน้า" เท่านั้น (ข้อ 2 = ก.) · ไฟล์ละบัญชีใน
  `/var/lib/aipc-vision/face-login/<ชื่อ>.json` รูปแบบเดียวกับ FaceStore (มีความยินยอม · ผูกโมเดล)
- **Tickets** สแกนผ่าน = ตั๋ว 1 ใบผูกกับบัญชีนั้น อายุ 30 วิ ใช้ได้ครั้งเดียว · อยู่ในหน่วยความจำเท่านั้น ·
  PAM ของหน้า Login (`aipc-face-pass`) ขอใช้ตั๋ว → มี = เข้าเลย · ไม่มี = ถามรหัสผ่านตามเดิม
- **Lockout** สแกนไม่ผ่านติดกัน 5 ครั้ง → ปิดการสแกนจนกว่าจะเข้าด้วยรหัสผ่านสำเร็จ 1 ครั้ง (BRIEF 5.1 ข้อ 9)
- **FaceLogin** รวมทั้งหมด: identify / enroll (ตอนสมัครหรือในหน้าตั้งค่า · ต้องรหัสผ่านถูก) / remove
"""

from __future__ import annotations

import os
import re
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from aipc.vision import matching, models, pipeline, store

LOGIN_DIR = Path("/var/lib/aipc-vision/face-login")
TICKET_TTL_S = 30.0
LOCK_AFTER = 5
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")  # ชื่อบัญชี Linux · กันชื่อไฟล์แปลก ("../")
# ตัวตรวจว่าเจ้าของยังอยู่ (การ์ด 0051 ทาง ก) · ค่าเดียวกับขั้น C (aipc.ui.presence.THRESHOLD) และสแกนเข้าเครื่อง
WATCH_THRESHOLD = 0.363
WATCH_EVERY_S = 2.0
PURPOSE = "เข้าเครื่องด้วยใบหน้าที่หน้า Login (เจ้าของบัญชีเปิดเอง · ปิดหรือลบได้ในหน้าตั้งค่า)"


class Tickets:
    """ตั๋วเข้าระบบ 1 ใบต่อบัญชี · ออกใหม่ = แทนใบเดิม · ใช้แล้ว/หมดอายุ = ใช้ไม่ได้."""

    def __init__(self, ttl: float = TICKET_TTL_S, clock: Callable[[], float] = time.monotonic):
        self.ttl, self._clock = ttl, clock
        self._by_user: dict[str, tuple[str, float]] = {}

    def issue(self, user: str) -> None:
        self._by_user[user] = (secrets.token_hex(32), self._clock() + self.ttl)

    def consume(self, user: str) -> bool:
        item = self._by_user.pop(user, None)
        return item is not None and self._clock() <= item[1]

    def clear(self) -> None:
        self._by_user.clear()


class Lockout:
    """นับการสแกนที่ไม่ผ่านติดกัน (ทั้งเครื่อง · หน้า Login ไม่รู้ว่าใครกำลังลอง)."""

    def __init__(self, limit: int = LOCK_AFTER):
        self.limit, self.failures = limit, 0

    @property
    def locked(self) -> bool:
        return self.failures >= self.limit

    def fail(self) -> None:
        self.failures += 1

    def reset(self) -> None:
        """สแกนผ่าน หรือเข้าด้วยรหัสผ่านสำเร็จ (PAM session ของ greetd เรียก)."""
        self.failures = 0


class Gallery:
    """แม่แบบของบัญชีที่เปิดใช้ · อ่านใหม่เมื่อโฟลเดอร์เปลี่ยน (เพิ่ม/ลบไฟล์) · ไฟล์เสีย = ข้ามบัญชีนั้น."""

    def __init__(self, folder: Path = LOGIN_DIR, model_sha256: str = models.SFACE.sha256):
        self.folder, self.model_sha256 = folder, model_sha256
        self._stamp: tuple | None = None
        self._templates: dict = {}

    def path(self, user: str) -> Path:
        if not USER_RE.fullmatch(user):
            raise ValueError("ชื่อบัญชีไม่ถูกต้อง")
        return self.folder / f"{user}.json"

    def store(self, user: str) -> store.FaceStore:
        return store.FaceStore(self.path(user), self.model_sha256)

    def _scan_stamp(self) -> tuple:
        try:
            entries = sorted(
                (e.name, e.stat().st_mtime_ns)
                for e in os.scandir(self.folder)
                if e.name.endswith(".json")
            )
        except FileNotFoundError:
            return ()
        return tuple(entries)

    def templates(self) -> dict:
        stamp = self._scan_stamp()
        if stamp != self._stamp:
            loaded = {}
            for name, _ in stamp:
                user = name.removesuffix(".json")
                if not USER_RE.fullmatch(user):
                    continue
                s = self.store(user).load()
                if s is not None:
                    loaded[user] = s.vector
            self._templates, self._stamp = loaded, stamp
        return dict(self._templates)


@dataclass
class Outcome:
    ok: bool
    state: str  # found unknown no-face spoof locked no-templates busy saved removed bad-password
    user: str = ""
    message: str = ""


MESSAGES = {
    "locked": "สแกนไม่ผ่านหลายครั้ง · ใช้รหัสผ่านเข้าก่อน 1 ครั้ง",
    "no-templates": "ยังไม่มีบัญชีที่เปิดเข้าด้วยใบหน้า",
    "spoof": "ภาพไม่เหมือนหน้าจริง · ใช้รหัสผ่านได้เลย",
    "unknown": "ยังไม่แน่ใจว่าเป็นใคร · ลองอีกครั้ง หรือใช้รหัสผ่าน",
    "no-face": "ไม่เห็นหน้าชัดพอ · มองกล้องตรง ๆ ในที่สว่าง",
    "bad-password": "รหัสผ่านไม่ถูกต้อง",
    "no-consent": "ต้องยินยอมก่อนเก็บข้อมูลใบหน้า",
}


class FaceLogin:
    """check_password(user, password) → bool มาจากตัวช่วย root (PAM) · visiond ไม่ตรวจรหัสเอง."""

    def __init__(
        self,
        scanner: pipeline.FaceScanner,
        gallery: Gallery,
        check_password: Callable[[str, str], bool],
        tickets: Tickets | None = None,
        lockout: Lockout | None = None,
        log: Callable[[str], None] = lambda _: None,
    ):
        self.scanner, self.gallery, self.check_password = scanner, gallery, check_password
        self.tickets = tickets or Tickets()
        self.lockout = lockout or Lockout()
        self.log = log

    def _out(self, state: str, user: str = "") -> Outcome:
        return Outcome(state in ("found", "saved", "removed"), state, user, MESSAGES.get(state, ""))

    def identify(self, frames: Iterable, progress=None) -> Outcome:
        if self.lockout.locked:
            return self._out("locked")
        templates = self.gallery.templates()
        if not templates:
            return self._out("no-templates")
        res = self.scanner.scan(frames, templates, progress)
        if res.account:
            self.lockout.reset()
            self.tickets.issue(res.account)
            self.log(f"สแกนหน้าผ่าน: {res.account}")  # ไม่มีคะแนน ภาพ หรือเวกเตอร์ใน log
            return self._out("found", res.account)
        state = {"spoof": "spoof", "not_enough_frames": "no-face"}.get(res.reason, "unknown")
        if state != "no-face":  # ไม่เห็นหน้า = ยังไม่ได้ลอง ไม่นับเป็นการสแกนผิด
            self.lockout.fail()
        self.log(f"สแกนหน้าไม่ผ่าน: {state}")
        return self._out(state)

    def consume(self, user: str) -> bool:
        ok = self.tickets.consume(user)
        self.log(f"ใช้ตั๋วใบหน้า {user}: {'สำเร็จ' if ok else 'ไม่มีตั๋ว'}")
        return ok

    def watch(self, user: str, frames: Iterable, send, every_s: float | None = None,
              clock=time.monotonic) -> Outcome:  # fmt: skip
        """ตัวตรวจว่าเจ้าของยังนั่งอยู่ (การ์ด 0051 ทาง ก) · ใช้แม่แบบที่ลงทะเบียนตอนสมัคร (ชุดเดียว) ·
        ส่งออกแค่ จำนวนหน้า · ใช่เจ้าของไหม · ความคล้ายสูงสุด — ไม่มีภาพหรือแม่แบบออกไป · ไม่ log ทุกภาพ."""
        try:
            stored = self.gallery.store(user).load()
        except ValueError:
            stored = None
        if stored is None:
            return self._out("no-templates")
        every_s = WATCH_EVERY_S if every_s is None else every_s
        last = float("-inf")
        for frame in frames:
            now = clock()
            if now - last < every_s:
                continue
            last = now
            sims = [matching.cosine(e, stored.vector) for e in self.scanner.embed_faces(frame)]
            best = max(sims) if sims else None
            send({"state": "seen", "faces": len(sims),
                  "owner": best is not None and best >= WATCH_THRESHOLD,
                  "best": None if best is None else round(float(best), 3)})  # fmt: skip
        return Outcome(True, "done", user)

    def password_login(self) -> None:
        """เข้าระบบสำเร็จ (ด้วยรหัสผ่านหรือใบหน้า) · ปลดล็อกการสแกน."""
        self.lockout.reset()

    def enroll(
        self, user: str, password: str, frames: Iterable, consent_at: str, progress=None
    ) -> Outcome:
        """ตรวจรหัสผ่านก่อนเปิดกล้อง · ลงทะเบียน 5 ท่าด้วยแกนเดิม (การ์ด 0010) · บันทึกลงรายการของหน้า Login."""
        if not consent_at:
            return self._out("no-consent")
        try:
            path_store = self.gallery.store(user)
        except ValueError:
            return self._out("bad-password")  # ชื่อแปลก = ข้อความเดียวกับรหัสผิด (ไม่บอกว่ามีบัญชีไหม)
        if not self.check_password(user, password):
            self.log(f"ลงทะเบียนใบหน้า {user}: รหัสผ่านไม่ถูก")
            return self._out("bad-password")
        res = self.scanner.enroll(frames, progress=progress)
        if isinstance(res, pipeline.Rejected):
            return Outcome(False, "spoof" if res.common == "spoof" else "no-face", user, res.advice)
        self.gallery.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path_store.save(
            res.vector, res.frames, res.created, store.Consent(consent_at, purpose=PURPOSE)
        )
        self.log(f"ลงทะเบียนใบหน้าเข้าเครื่อง: {user}")
        return self._out("saved", user)

    def remove(self, user: str, password: str) -> Outcome:
        try:
            s = self.gallery.store(user)
        except ValueError:
            return self._out("bad-password")
        if not self.check_password(user, password):
            return self._out("bad-password")
        s.delete()
        self.tickets.consume(user)
        self.log(f"ปิดเข้าเครื่องด้วยใบหน้า: {user}")
        return self._out("removed", user)
