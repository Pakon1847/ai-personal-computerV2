"""ที่เก็บนัดหมาย และตัวตัดสินว่าอันไหนถึงเวลาเตือน (การ์ดออกแบบ 0001 หัวข้อ 4–6).

ที่เก็บซ่อนอยู่หลังคลาส ReminderStore เพราะ ADR-004 (เก็บข้อมูลส่วนตัวที่ไหน) ยังไม่ตัดสิน
ตอนนี้เป็นไฟล์ JSON ใน home ของผู้ใช้ · เปลี่ยนที่เก็บภายหลังได้โดยไม่ต้องแก้ส่วนอื่น

การเขียน (H1): ไฟล์ชั่วคราว → fsync → rename ทับ และเก็บสำเนารุ่นก่อนไว้ที่ .bak
ไฟล์เสีย: ใช้ .bak · เสียทั้งคู่: อ่านไม่ได้ และ **ไม่เขียนทับ** จนกว่าผู้ใช้จะตัดสิน (H2)

Logout / ปิดเครื่อง: ไม่มีใครเตือน (Logout ปิดโปรเซสทั้งหมด) → เข้าใช้ครั้งถัดไปรายงาน "พลาดไป" (H2)
นาฬิกาถอยหลัง (ไฟดับแล้วไม่มีแบต RTC): จำเวลาล่าสุดที่เห็นไว้ ถ้าเวลาปัจจุบันน้อยกว่า → เตือนผู้ใช้ (H5)
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

VERSION = 1
CLOCK_SLACK = timedelta(minutes=1)
# บันทึก "เวลาล่าสุดที่เห็น" ห่างกันอย่างน้อยเท่านี้ · เดิมบันทึกทุกรอบ 30 วิ = เขียน microSD 2,880 ครั้ง/วัน (H4)
# ค่าที่หยาบลงทำให้ตรวจนาฬิกาถอยหลังไวน้อยลงเท่านั้น ไม่มีทางทำให้เตือนผิด
SEEN_EVERY = timedelta(minutes=10)


def default_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "aipc" / "reminders.json"


def aware(dt: datetime) -> datetime:
    """ใส่เขตเวลาของเครื่องให้เวลาที่ไม่มีเขตเวลา เพื่อเทียบกันได้ถูกต้องเสมอ."""
    return dt if dt.tzinfo else dt.astimezone()


def _fsync_dir(folder: Path) -> None:
    """ให้การเปลี่ยนชื่อไฟล์ลงดิสก์จริง (ไฟดับหลัง rename แล้วไฟล์ใหม่ไม่หาย) · วินโดวส์ไม่มี ข้ามได้."""
    if os.name != "posix":
        return
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass
class Reminder:
    what: str
    when: datetime
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: datetime = field(default_factory=lambda: datetime.now().astimezone())
    remind_before_min: int = 0
    fired: bool = False
    repeat: str = (
        ""  # นัดซ้ำ (when.repeat_rule): daily | weekdays | weekends | weekly:<0–6> · "" = ครั้งเดียว
    )

    @property
    def alert_at(self) -> datetime:
        return aware(self.when) - timedelta(minutes=self.remind_before_min)

    def to_json(self) -> dict:
        d = asdict(self)
        d["when"] = aware(self.when).isoformat()
        d["created"] = aware(self.created).isoformat()
        return d

    @staticmethod
    def from_json(d: dict) -> Reminder:
        return Reminder(
            what=str(d["what"]),
            when=datetime.fromisoformat(d["when"]),
            id=str(d["id"]),
            created=datetime.fromisoformat(d["created"]),
            remind_before_min=int(d.get("remind_before_min", 0)),
            fired=bool(d.get("fired", False)),
            repeat=str(d.get("repeat", "")),
        )

    def advance(self, now: datetime) -> None:
        """นัดซ้ำ: เลื่อนไปครั้งถัดไปที่ยังไม่ถึงเวลาเตือน.

        ปิดเครื่องไปหลายวันก็ข้ามไปครั้งถัดไปทีเดียว ไม่เตือนย้อนทุกรอบ
        """
        from aipc.skills.when import next_on

        when = aware(self.when)
        self.when = next_on(
            self.repeat,
            when.time(),
            max(when, aware(now) + timedelta(minutes=self.remind_before_min)),
        )


class Unreadable(Exception):
    """ไฟล์นัดหมายและสำเนาเสียทั้งคู่ · ห้ามเขียนทับจนกว่าผู้ใช้จะตัดสิน."""


class ReminderStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_path()
        self.bak = self.path.with_name(self.path.name + ".bak")
        self.recovered_from_backup = False
        self._broken = False
        self._main_ok = False  # ไฟล์หลักอ่านได้ไหม · ไม่ได้ = ห้ามคัดไฟล์หลักทับ .bak ที่ดี
        self.last_seen: datetime | None = None
        self.items: list[Reminder] = []
        self._load()

    def _read(self, p: Path) -> tuple[list[Reminder], datetime | None]:
        data = json.loads(p.read_text(encoding="utf-8"))
        items = [Reminder.from_json(r) for r in data["reminders"]]
        seen = data.get("last_seen")
        return items, (datetime.fromisoformat(seen) if seen else None)

    def _load(self) -> None:
        if not self.path.exists() and not self.bak.exists():
            return
        try:
            self.items, self.last_seen = self._read(self.path)
            self._main_ok = True
            return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            self.items, self.last_seen = self._read(self.bak)
            self.recovered_from_backup = True
        except (OSError, ValueError, KeyError, TypeError):
            self._broken = True

    @property
    def broken(self) -> bool:
        return self._broken

    def save(self, now: datetime | None = None) -> None:
        if self._broken:
            raise Unreadable(str(self.path))
        now = aware(now or datetime.now())
        if self.last_seen is None or now > self.last_seen:
            self.last_seen = now
        payload = {
            "version": VERSION,
            "last_seen": self.last_seen.isoformat(),
            "reminders": [r.to_json() for r in self.items],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # เก็บรุ่นก่อนไว้ กันไฟล์เสียจากสาเหตุอื่น · ไฟล์หลักที่อ่านไม่ได้ห้ามคัดทับ .bak ที่ดี
        # (พบ 2026-09-28: กู้จาก .bak แล้วบันทึกครั้งถัดไปล้ม = เสียทั้งคู่)
        if self.path.exists() and self._main_ok:
            shutil.copy2(self.path, self.bak)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        self._main_ok = True
        _fsync_dir(self.path.parent)

    def add(self, r: Reminder, now: datetime | None = None) -> Reminder:
        self.items.append(r)
        try:
            self.save(now)
        except Exception:
            self.items.remove(r)  # บันทึกไม่สำเร็จ = ไม่มีนัดนี้ (เดิมยังเตือนทั้งที่หน้าจอบอกว่าไม่สำเร็จ)
            raise
        return r

    def delete(self, rid: str, now: datetime | None = None) -> bool:
        before = list(self.items)
        self.items = [r for r in self.items if r.id != rid]
        if len(self.items) == len(before):
            return False
        try:
            self.save(now)
        except Exception:
            self.items = before  # ลบไม่สำเร็จ = นัดยังอยู่ ตรงกับไฟล์
            raise
        return True

    def upcoming(self, now: datetime) -> list[Reminder]:
        now = aware(now)
        return sorted((r for r in self.items if not r.fired and aware(r.when) >= now),
                      key=lambda r: aware(r.when))  # fmt: skip


@dataclass
class Tick:
    due: list[Reminder]
    clock_went_back: bool
    save_failed: bool = False  # เตือนแล้ว แต่บันทึกไม่ได้ → เข้าใช้ครั้งหน้าจะรายงานว่า "พลาดไป"


def clock_went_back(store: ReminderStore, now: datetime) -> bool:
    return store.last_seen is not None and aware(now) < store.last_seen - CLOCK_SLACK


def tick(store: ReminderStore, now: datetime) -> Tick:
    """เรียกทุก ~30 วินาทีระหว่างเซสชัน · คืนรายการที่ต้องเตือนตอนนี้ แล้วบันทึกว่าเตือนแล้ว."""
    now = aware(now)
    back = clock_went_back(store, now)
    hit = [r for r in store.items if not r.fired and r.alert_at <= now]
    due = []
    for r in hit:
        due.append(replace(r))  # สำเนา: หน้าจอแสดงเวลาของครั้งนี้ ไม่ใช่ครั้งถัดไป
        if r.repeat:
            r.advance(now)  # นัดซ้ำไม่ "เตือนแล้ว" · ตั้งครั้งถัดไปเอง
        else:
            r.fired = True
    stale = store.last_seen is None or now - store.last_seen >= SEEN_EVERY
    failed = False
    if due or (stale and not back):
        # บันทึกไม่ได้ (ดิสก์เต็ม, การ์ดอ่านอย่างเดียว) ต้องไม่ทำให้การเตือนหาย (พบ 2026-09-28)
        # ในเซสชันนี้ไม่เตือนซ้ำ (fired อยู่ในหน่วยความจำ) · บนดิสก์ยังไม่ fired → ครั้งหน้ารายงานว่าพลาด
        try:
            store.save(now)
        except (OSError, Unreadable):
            failed = True
    return Tick(due, back, failed)


def missed_since_last_session(store: ReminderStore, now: datetime) -> list[Reminder]:
    """ตอนเข้าใช้: นัดที่เลยเวลาไปแล้วโดยยังไม่ได้เตือน (เพราะปิดเครื่องหรือ Logout อยู่).

    รายงานครั้งเดียว: นัดครั้งเดียวตั้ง fired · นัดซ้ำเลื่อนไปครั้งถัดไป · ผู้เรียกบันทึก
    """
    now = aware(now)
    out = []
    for r in store.items:
        if r.fired or aware(r.when) >= now - CLOCK_SLACK:
            continue
        out.append(replace(r))
        if r.repeat:
            r.advance(now)
        else:
            r.fired = True  # ไม่เตือนซ้ำเมื่อถึงรอบตรวจ
    return out
