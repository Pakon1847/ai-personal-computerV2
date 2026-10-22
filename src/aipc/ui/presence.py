"""ขั้น C: กล้องตรวจว่าเจ้าของยังอยู่ → ล็อก / ออกจากระบบ (Pakon 2026-10-06 · เปิดเองในหน้าตั้งค่า).

ออกแบบตามผลขั้น B (docs/benchmarks/2026-10-06-presence-b · ผ่าน 3/5) และกฎที่ประกาศก่อนวัด:
- เปิดกล้องเฉพาะตอน**ไม่ได้แตะคีย์บอร์ด/เมาส์** (swayidle แจ้งผ่านไฟล์ธง) → ไฟกล้องดับเมื่อใช้งาน · ภาระเฉลี่ยต่ำ (M4)
- ไม่เห็นหน้าเจ้าของ lock_after วิ → ล็อก (swaylock) ·
  ล็อกแล้วไม่เห็นหน้าใครเลยอีก logout_after วิ → ออกจากระบบ (M1/M2 ผ่าน)
- เห็น "คนอื่น" 3 ครั้งติดและไม่มีเจ้าของ → **ล็อกทันที แต่ไม่ออกจากระบบ** (M3 ไม่ผ่าน → ห้าม logout จากการจำหน้า)
- เทียบ**ทุกหน้า** ในภาพ: มีเจ้าของอยู่หน้าหนึ่ง = เจ้าของอยู่ (B: เจ้าของนั่งแต่หน้าคนอื่นใหญ่กว่า → ตัววัดเดิมนับผิด)
- ไม่บันทึกภาพ · แม่แบบเจ้าของมาจาก "ใบหน้าของฉัน" (ยินยอมแล้ว · ~/.local/share/aipc/face-template.json)
ปลดล็อกด้วยรหัสผ่านเสมอ (การ์ด 0015: หน้าจอล็อกใช้รหัสผ่าน)

    python -m aipc.ui.presence run --flag <ไฟล์ธง> --lock-after 30 --logout-after 30
        [--image lock.png]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

FPS = 2.0
ID_EVERY_S = 2.0
MAX_FACES = 3
STRANGER_RUN = 3
THRESHOLD = 0.363  # cosine · ค่าเดียวกับสแกนหน้าเข้าเครื่องและขั้น B
IDLE_AFTER_S = 10  # ไม่แตะคีย์บอร์ด/เมาส์กี่วิ ถึงเปิดกล้อง (swayidle timeout ของไฟล์ธง)
LOCK_GRACE_S = 3.0  # หลังสั่งล็อก รอ swaylock ขึ้นก่อนเชื่อว่า "ไม่ได้ล็อก"
STRANGER_GAP_S = (
    6.0  # "คนอื่น" ห่างกันเกินนี้ = เริ่มนับใหม่ (ภาพที่หาหน้าไม่เจอคั่นได้ · ทดสอบ 23:47 รูปบนมือถือหาเจอบ้างไม่เจอบ้าง)
)


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "aipc"


def idle_flag() -> Path:
    return runtime_dir() / "input-idle"


def busy_flag() -> Path:
    return runtime_dir() / "camera-busy"


def status_path() -> Path:
    return runtime_dir() / "presence.json"


@contextmanager
def camera_claim(wait_s: float = 1.5, flag: Path | None = None, sleep=time.sleep):
    """หน้า "ใบหน้าของฉัน" จะใช้กล้อง → ตั้งธงให้ตัวตรวจปล่อยกล้องก่อน (ตัวตรวจดูธงทุก 0.5 วิ)."""
    flag = flag or busy_flag()
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(str(os.getpid()), encoding="utf-8")
        sleep(wait_s)
    except OSError:
        pass
    try:
        yield
    finally:
        try:
            flag.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- ตัดสินใจ (ไม่มีกล้อง · เทสต์ได้ทุกเครื่อง)


@dataclass
class Seen:
    """ผลของภาพหนึ่ง · owner/stranger = None ถ้ารอบนี้ไม่ได้เทียบหน้า (เทียบทุก ID_EVERY_S วิ)."""

    faces: int
    owner: bool | None = None  # มีเจ้าของอยู่หน้าใดหน้าหนึ่ง
    stranger: bool | None = None  # มีหน้า แต่ไม่มีหน้าไหนเป็นเจ้าของ


@dataclass
class Decider:
    lock_after: float = 30.0
    logout_after: float = 30.0
    state: str = "active"  # active · watching · locked
    reason: str = ""  # absent · stranger
    owner_seen: float = 0.0
    last_face: float = 0.0  # ครั้งล่าสุดที่เห็นหน้าใครก็ได้หลังล็อก
    locked_at: float = 0.0
    run: int = 0
    last_stranger: float = -1e9
    log: list = field(default_factory=list)

    def tick(self, now: float, idle: bool, locked: bool, seen: Seen | None) -> str | None:
        """คืนคำสั่ง: "lock" · "logout" · None · locked = มี swaylock อยู่จริงตอนนี้ (ของขั้น A หรือ C)."""
        if self.state == "logout":  # สั่งออกแล้ว · ไม่สั่งซ้ำ
            return None
        # ปลดล็อกแล้ว (รหัสผ่านถูก) · 3 วิแรกหลังสั่งล็อก swaylock อาจยังไม่ขึ้นใน pgrep → ยังไม่นับ
        if self.state == "locked" and not locked and now - self.locked_at > LOCK_GRACE_S:
            self._to("active", now)
        if not idle and self.state != "locked":
            if self.state != "active":
                self._to("active", now)
            return None
        if self.state == "active":
            if locked:  # ขั้น A ล็อกไว้ หรือคนอื่นล็อก → ไม่ต้องทำอะไร
                return None
            self.owner_seen, self.run = now, 0  # เพิ่งแตะเครื่อง = เจ้าของเพิ่งอยู่
            self._to("watching", now)
        if seen is None:
            return None
        if self.state == "watching":
            if seen.owner:
                self.owner_seen, self.run = now, 0
            elif seen.stranger:
                if now - self.last_stranger > STRANGER_GAP_S:
                    self.run = 0
                self.run, self.last_stranger = self.run + 1, now
            # ไม่เห็นหน้า/ไม่ได้เทียบรอบนี้ = ไม่นับใหม่ (เดิมภาพที่หาหน้าไม่เจอ 1 ภาพทำให้นับใหม่ → ล็อกช้า)
            if self.run >= STRANGER_RUN:
                return self._lock(now, "stranger")
            if now - self.owner_seen >= self.lock_after:
                return self._lock(now, "absent")
            return None
        # locked โดยตัวนี้ · ออกเมื่อ "ไม่เห็นหน้าใครเลยต่อเนื่อง" logout_after วิ (เหตุผลคือไม่มีคน ไม่ใช่การจำหน้า)
        # ทดสอบที่หน้าจอ 2026-10-06 23:38: เดิมเห็นหน้าครั้งเดียวหลังล็อก (ตอนกำลังลุก) = ไม่ออกเลย
        # เห็นคนอื่นแล้วยังอยู่หน้าจอ = ไม่ออก (ขั้น B M3 ไม่ผ่าน) · คนอื่นเดินไปแล้วไม่มีใครอีก 30 วิ = ออก (M1/M2 ผ่าน)
        if seen.faces > 0:
            self.last_face = now
        # logout_after ≤ 0 = ล็อกอย่างเดียว ไม่ออก (การ์ด 0051 · ค่าเริ่มต้น)
        quiet = now - max(self.locked_at, self.last_face)
        if self.logout_after > 0 and idle and quiet >= self.logout_after:
            self._to("logout", now)
            return "logout"
        return None

    def _lock(self, now: float, reason: str) -> str:
        self.reason, self.locked_at, self.last_face, self.run = reason, now, now, 0
        self._to("locked", now)
        return "lock"

    def _to(self, state: str, now: float) -> None:
        self.state = state
        self.log.append((round(now, 1), state, self.reason if state == "locked" else ""))


# ---------------------------------------------------------------- กล้อง + เทียบหน้า


class Eyes:
    """กล้อง + YuNet + SFace · เปิด/ปิดตามสั่ง · โหลดโมเดลครั้งแรกที่เปิดกล้อง."""

    def __init__(self, owner_vec):
        self.owner = owner_vec
        self.cap = None
        self.det = self.emb = None
        self.last_id = -1e9
        # [เวลา, จำนวนหน้า, ความคล้ายสูงสุด] 12 รอบล่าสุด · ตัวเลขเท่านั้น ใช้ดูว่าทำไมล็อก
        self.recent: list = []

    def on(self) -> bool:
        if self.cap is not None:
            return True
        import cv2

        from aipc.vision import camera, models

        if self.det is None:
            self.det, self.emb = models.Detector(max_side=320), models.Embedder()
        cap = camera.open_camera()
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap = cap
        return True

    def off(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def look(self, now: float) -> Seen | None:
        from aipc.vision import align, matching

        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("กล้องส่งภาพไม่ได้")
        faces = self.det.detect(frame)[:MAX_FACES]
        if not faces or now - self.last_id < ID_EVERY_S:
            if not faces and now - self.last_id >= ID_EVERY_S:
                self._note(now, 0, None)
            return Seen(len(faces))
        self.last_id = now
        sims = [
            matching.cosine(
                matching.l2_normalize(self.emb.embed(align.crop(frame, f[4:14]))), self.owner
            )
            for f in faces
        ]
        owner = max(sims) >= THRESHOLD
        self._note(now, len(faces), round(float(max(sims)), 3))
        return Seen(len(faces), owner=owner, stranger=not owner)

    def _note(self, now: float, faces: int, sim) -> None:
        self.last_id = now if sim is None else self.last_id
        self.recent = (self.recent + [[round(now, 1), faces, sim]])[-12:]


def lock_now(image: str | None) -> subprocess.Popen:
    """swaylock แบบไม่ -f (ไม่แยกตัว) · ปลดล็อกแล้วโปรเซสจบเอง."""
    from aipc.ui import idle

    cmd = [a for a in idle.lock_command(Path(image) if image else None) if a != "-f"]
    return subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def any_lock(run=subprocess.run) -> bool:
    """มี swaylock ของผู้ใช้คนนี้อยู่ไหม (ของขั้น A หรือที่ตัวนี้สั่ง)."""
    r = run(["pgrep", "-u", str(os.getuid()), "-x", "swaylock"], capture_output=True, check=False)
    return r.returncode == 0


def write_status(
    state: str, detail: str = "", path: Path | None = None, recent: list | None = None
) -> None:
    path = path or status_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"state": state, "detail": detail, "threshold": THRESHOLD,
                                   "recent": recent or [],
                                   "at": datetime.now().isoformat(timespec="seconds")},
                                  ensure_ascii=False), encoding="utf-8")  # fmt: skip
        os.replace(tmp, path)
    except OSError:
        pass


def run(flag: Path, lock_after: float, logout_after: float, image: str | None) -> int:
    from aipc.vision import store

    stored = store.FaceStore().load()
    if stored is None:
        write_status("no-template", 'ลงทะเบียน "ใบหน้าของฉัน" ในหน้าตั้งค่าก่อน')
        return 3
    eyes, d = Eyes(stored.vector), Decider(lock_after, logout_after)
    write_status("active")
    last = None
    while True:
        now = time.monotonic()
        idle = flag.exists()
        locked = any_lock()
        busy = busy_flag().exists()
        want_camera = idle and not busy and d.state in ("active", "watching", "locked")
        seen = None
        try:
            if want_camera and eyes.on():
                seen = eyes.look(now)
            else:
                eyes.off()
        except Exception as e:  # noqa: BLE001 · กล้องหลุด/ถูกใช้อยู่ = ไม่ตัดสินจากกล้อง (ไม่ล็อกมั่ว) · ลองใหม่รอบหน้า
            eyes.off()
            write_status("camera-error", str(e)[:120])
            time.sleep(5)
            continue
        action = d.tick(now, idle, locked, seen)
        if action == "lock" and not locked:
            lock_now(image)
        elif action == "logout":
            write_status("logout", d.reason)
            subprocess.run(["labwc", "--exit"], check=False)
            return 0
        cur = (
            d.state,
            d.reason if d.state == "locked" else "",
            eyes.cap is not None,
            len(eyes.recent),
            eyes.recent[-1][0] if eyes.recent else 0,
        )
        if cur != last:
            write_status(
                d.state,
                ("ไม่เห็นเจ้าของ" if d.reason == "absent" else "เห็นคนอื่น")
                if d.state == "locked"
                else ("กล้องเปิด" if eyes.cap is not None else "กล้องปิด"),
                recent=eyes.recent,
            )
            last = cur
        time.sleep(max(0.0, 1 / FPS - (time.monotonic() - now)))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.ui.presence")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--flag", type=Path, default=None)
    r.add_argument("--lock-after", type=float, default=30)
    r.add_argument("--logout-after", type=float, default=30)
    r.add_argument("--image", default=None)
    a = p.parse_args(argv)
    return run(a.flag or idle_flag(), a.lock_after, a.logout_after, a.image)


if __name__ == "__main__":
    sys.exit(main())
