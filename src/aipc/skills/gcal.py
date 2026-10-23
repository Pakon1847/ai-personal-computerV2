"""ปฏิทิน Google แบบอ่านอย่างเดียว ผ่าน "ที่อยู่ลับในรูปแบบ iCal" (การ์ด 0014 · Pakon อนุมัติ 2026-10-15).

ทำไมไม่ใช้ OAuth: แอปที่ Google ยังไม่ตรวจรับรองต้องเข้าสู่ระบบใหม่ทุก 7 วันและมีหน้าเตือน = คนทั่วไปตั้งค่าเองไม่ได้ ·
ลิงก์ iCal ลับได้จากหน้าตั้งค่าของ Google Calendar · อ่านอย่างเดียว · ผู้ใช้รีเซ็ตลิงก์เองได้ถ้ารั่ว

ไหลยังไง: ผู้ใช้วางลิงก์ → รับเฉพาะลิงก์ของ calendar.google.com → ดาวน์โหลด (ไม่เกิน 5 MB · 20 วิ) →
icalendar อ่านไฟล์ + recurring-ical-events กางนัดซ้ำ (รวมนัดที่แก้เฉพาะครั้ง และครั้งที่ถูกลบ) →
เก็บสำเนาช่วง −1 ถึง +60 วันไว้ในเครื่อง (atomic) → คำตอบนัด หน้าแรก และคำถามด้วยเสียง อ่านจากสำเนา (ไม่ต้องใช้เน็ต)

ลิงก์ลับ = กุญแจอ่านปฏิทิน (H7): ไฟล์ 0600 · หน้าจอแสดงแค่ 4 ตัวท้าย · ไม่ลง log และไม่ลงสมุดบันทึกสิ่งที่ส่งออก
ชื่อนัดจาก Google = ข้อมูลภายนอก (H8): ตัดอักขระควบคุม · ไม่เกิน 120 ตัวอักษร · แสดงเป็นข้อความเท่านั้น ไม่ส่งให้ AI
"""

from __future__ import annotations

import http.client
import json
import os
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from aipc import fsutil

HOST = "calendar.google.com"
# ลิงก์ส่วนตัว (private-…) หรือปฏิทินสาธารณะ (public) ของ Google เท่านั้น
# ลิงก์อื่นไม่รับ (กันการใส่ลิงก์ให้เครื่องไปดึงที่อื่น)
LINK = re.compile(
    r"https://calendar\.google\.com/calendar/ical/[^/?#\s]+/(?:private-[A-Za-z0-9]+|public)/basic\.ics"
)
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 20
PAST = timedelta(days=1)
FUTURE = timedelta(days=60)
# ดึงเองตามรอบระหว่างเข้าระบบอยู่ (การ์ด 0051) · ไม่ต้องเปิดเว็บ · ลิงก์ iCal ของ Google เองก็หน่วงอยู่แล้ว
AUTO_SYNC = timedelta(minutes=15)
STALE = timedelta(minutes=30)  # ถามเรื่องนัดแล้วสำเนาเก่ากว่านี้ = ดึงใหม่เบื้องหลัง (ตอบจากสำเนาไปก่อน)
OLD = timedelta(hours=24)  # สำเนาเก่ากว่านี้ = เตือนในคำตอบ
TITLE_MAX = 120
SENT = "ดาวน์โหลดปฏิทินจาก calendar.google.com (อ่านอย่างเดียว · ไม่ได้ส่งนัด แชท หรือไฟล์ของคุณ)"

# วันหยุดไทย (การ์ด 0033): ปฏิทินสาธารณะของ Google · ไม่มีความลับในลิงก์ ·
# ตรวจ 2026-10-15: HTTP 200 · 317 รายการ ·
# ปี 2021–2031 · คำอธิบายบรรทัดแรก "วันหยุดนักขัตฤกษ์" / "วันสำคัญ" · ชื่อบางวันมี U+200B
HOLIDAYS_TH = (
    "https://calendar.google.com/calendar/ical/"
    "th.th%23holiday%40group.v.calendar.google.com/public/basic.ics"
)
HOLIDAY_SENT = "ดาวน์โหลดปฏิทินวันหยุดไทยสาธารณะจาก calendar.google.com (ไม่มีข้อมูลของคุณ)"
HOLIDAY_FUTURE = timedelta(days=400)  # ถาม "อีกกี่วันถึงสงกรานต์" ได้ตลอดปี
HOLIDAY_STALE = timedelta(days=7)  # วันหยุดเปลี่ยนไม่บ่อย · ดึงตอนเข้าเครื่องเมื่อสำเนาเก่ากว่านี้
# อักขระล่องหนที่พบในชื่อวันหยุดของ Google (U+200B) · ไม่ตัด = ค้นชื่อไม่เจอ
# + ตัวกลับทิศทาง (bidi) ที่ทำให้ชื่อนัดแสดงสลับลำดับหลอกตาได้ (ตรวจทั้งระบบ 3.11)
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def link_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "aipc" / "gcal-link.json"


def cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "aipc" / "gcal-events.json"


def holiday_files() -> tuple[Path, Path]:
    """(ไฟล์เปิด/ปิด, สำเนา) ของปฏิทินวันหยุด · แยกจากปฏิทินส่วนตัว."""
    return link_path().with_name("holidays-link.json"), cache_path().with_name("holidays-th.json")


def alert_path() -> Path:
    """นัดที่เตือนไปแล้ว (การ์ด 0032) · เข้าเครื่องใหม่แล้วไม่เตือนซ้ำ."""
    return cache_path().with_name("gcal-alerted.json")


class SyncError(Exception):
    """ดึงหรืออ่านปฏิทินไม่ได้ · ข้อความเป็นภาษาไทยสำหรับแสดงให้ผู้ใช้."""


def valid_link(text: str) -> bool:
    return bool(LINK.fullmatch(text.strip()))


def hint(link: str) -> str:
    """4 ตัวท้ายของรหัสในลิงก์ (ให้ผู้ใช้รู้ว่าลิงก์ไหน โดยไม่เปิดเผยลิงก์)."""
    m = re.search(r"/(private-[A-Za-z0-9]+|public)/", link)
    if m is None:
        return ""
    return "สาธารณะ" if m[1] == "public" else "…" + m[1][-4:]


class _SameHost(urllib.request.HTTPRedirectHandler):
    """ตาม redirect เฉพาะภายใน calendar.google.com · ไปโดเมนอื่น = ไม่ไป."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).hostname != HOST:
            raise SyncError("Google ส่งต่อไปที่อื่นที่ไม่ใช่ปฏิทิน · ไม่ได้ดึง")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(link: str) -> bytes:
    """ดาวน์โหลดไฟล์ปฏิทิน · ผิดทุกแบบ = SyncError (ข้อความไทย)."""
    if not valid_link(link):
        raise SyncError("ลิงก์นี้ไม่ใช่ที่อยู่ปฏิทินของ Google (ต้องขึ้นต้นด้วย https://calendar.google.com/…)")
    opener = urllib.request.build_opener(_SameHost())
    req = urllib.request.Request(link.strip(), headers={"User-Agent": "aipc-calendar/1"})
    try:
        with opener.open(req, timeout=TIMEOUT_S) as r:
            data = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise SyncError("ลิงก์ใช้ไม่ได้แล้ว (อาจถูกรีเซ็ตใน Google) · รับลิงก์ใหม่ตามคู่มือ") from e
        raise SyncError(f"Google ตอบกลับผิดพลาด (รหัส {e.code}) · ลองใหม่ภายหลัง") from e
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        # HTTPException = ดาวน์โหลดขาดกลางทาง (IncompleteRead · ตรวจทั้งระบบ 3.10)
        raise SyncError("ดึงปฏิทินไม่ได้ (ไม่มีอินเทอร์เน็ต?) · ใช้ข้อมูลที่ดึงไว้ล่าสุด") from e
    if len(data) > MAX_BYTES:
        raise SyncError("ไฟล์ปฏิทินใหญ่เกิน 5 MB · ไม่ได้อ่าน")
    return data


@dataclass(frozen=True)
class Event:
    """นัด 1 ครั้งจากปฏิทิน Google · ชื่อช่องเหมือนนัดในเครื่อง (what · when) ให้โค้ดตอบนัดใช้ร่วมกันได้."""

    what: str
    when: datetime  # มีเขตเวลาเสมอ · นัดทั้งวัน = 00:00 ของวันนั้น
    end: datetime
    all_day: bool = False
    uid: str = ""
    fired: bool = False  # นัด Google ไม่ถูกเตือนโดยเครื่องนี้ (การ์ด 0014 หัวข้อ 9)
    repeat: str = ""  # กางนัดซ้ำแล้ว ทุกครั้งเป็นนัดเดี่ยว
    source: str = "google"  # google = ปฏิทินส่วนตัว · holidays = วันหยุดไทย (การ์ด 0033)
    kind: str = "event"  # event · holiday (วันหยุดนักขัตฤกษ์) · observance (วันสำคัญ ไม่หยุด)

    @property
    def id(self) -> str:
        return f"g:{self.uid}:{self.when.isoformat()}"

    def to_json(self) -> dict:
        return {"what": self.what, "when": self.when.isoformat(), "end": self.end.isoformat(),
                "all_day": self.all_day, "uid": self.uid, "source": self.source,
                "kind": self.kind}  # fmt: skip

    @staticmethod
    def from_json(d: dict) -> Event:
        return Event(
            str(d["what"]),
            datetime.fromisoformat(d["when"]),
            datetime.fromisoformat(d["end"]),
            bool(d.get("all_day")),
            str(d.get("uid", "")),
            source=str(d.get("source", "google")),
            kind=str(d.get("kind", "event")),
        )


def _parse_time(text) -> datetime | None:
    try:
        return datetime.fromisoformat(str(text))
    except ValueError:
        return None


def clean_title(text: str) -> str:
    t = ZERO_WIDTH.sub("", str(text or ""))
    t = re.sub(r"[\x00-\x1f\x7f]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > TITLE_MAX:
        t = t[: TITLE_MAX - 1] + "…"
    return t or "(ไม่มีชื่อนัด)"


def _local(tz):
    return tz or datetime.now().astimezone().tzinfo


def _as_dt(value, tz) -> tuple[datetime, bool]:
    """(เวลามีเขตเวลา, เป็นนัดทั้งวันไหม) · ไม่มีเขตเวลา (floating) = เวลาของเครื่อง."""
    if isinstance(value, datetime):
        return (value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)), False
    if isinstance(value, date):
        return datetime.combine(value, time(0), tzinfo=tz), True
    raise SyncError("ไฟล์ปฏิทินมีวันเวลาที่อ่านไม่ได้")


def _kind(component) -> str:
    """ปฏิทินวันหยุดของ Google: คำอธิบายบรรทัดแรกบอกว่าหยุดจริงหรือเป็นแค่วันสำคัญ (การ์ด 0033)."""
    first = str(component.get("DESCRIPTION", "")).strip().split("\n")[0].strip()
    if first.startswith("วันหยุดนักขัตฤกษ์"):
        return "holiday"
    if first.startswith("วันสำคัญ"):
        return "observance"
    return "event"


def _expand_each(cal, start: datetime, end: datetime, icalendar, rie) -> list:
    """กางทีละชุดนัด (UID เดียวกัน = ชุดเดียว รวมครั้งที่ถูกแก้) · ชุดที่กางไม่ได้ข้ามไป ชุดอื่นยังได้ ·
    ทุกชุดเสีย = อ่านไม่ได้ทั้งไฟล์."""
    zones = list(cal.walk("VTIMEZONE"))
    groups: dict[str, list] = {}
    for ev in cal.walk("VEVENT"):
        groups.setdefault(str(ev.get("UID", id(ev))), []).append(ev)
    out, bad = [], 0
    for events in groups.values():
        mini = icalendar.Calendar()
        for c in zones + events:
            mini.add_component(c)
        try:
            out += rie.of(mini).between(start, end)
        except Exception:  # noqa: BLE001
            bad += 1
    if groups and bad == len(groups):
        raise SyncError("ไฟล์ปฏิทินอ่านไม่ได้ (รูปแบบไม่ถูกต้อง)")
    return out


def expand(data: bytes, start: datetime, end: datetime, tz=None, classify: bool = False,
           source: str = "google") -> list[Event]:  # fmt: skip
    """นัดทุกครั้งในช่วง [start, end) · นัดซ้ำกางแล้ว · ข้ามนัดที่ถูกยกเลิก · เรียงตามเวลา.

    classify = อ่านชนิดวันจากคำอธิบาย (ใช้กับปฏิทินวันหยุดเท่านั้น · ปฏิทินส่วนตัวเป็น "event" เสมอ)
    """
    try:
        import icalendar
        import recurring_ical_events
    except ImportError as e:  # ยังไม่ได้ติดตั้ง dependency ของการ์ด 0014 (H5: บอกตามจริง)
        raise SyncError("เครื่องนี้ยังไม่ได้ติดตั้งตัวอ่านปฏิทิน") from e
    tz = _local(tz)
    try:
        cal = icalendar.Calendar.from_ical(data)
    except Exception as e:  # ไฟล์จากภายนอกผิดรูปได้ทุกแบบ · ไม่ให้แอปล่ม (H2)
        raise SyncError("ไฟล์ปฏิทินอ่านไม่ได้ (รูปแบบไม่ถูกต้อง)") from e
    try:
        comps = recurring_ical_events.of(cal).between(start, end)
    except Exception:  # noqa: BLE001 · นัดซ้ำชุดเดียวผิด (RRULE เสีย) เคยทำให้ทั้งปฏิทินพัง (3.11)
        comps = _expand_each(cal, start, end, icalendar, recurring_ical_events)
    out = []
    for c in comps:
        if c.name != "VEVENT" or str(c.get("STATUS", "")).upper() == "CANCELLED":
            continue
        try:
            when, all_day = _as_dt(c.decoded("DTSTART"), tz)
            stop = _as_dt(c.decoded("DTEND"), tz)[0] if "DTEND" in c else when
        except (KeyError, ValueError) as e:
            raise SyncError("ไฟล์ปฏิทินมีนัดที่ไม่มีเวลาเริ่ม") from e
        out.append(Event(clean_title(c.get("SUMMARY", "")), when, max(stop, when), all_day,
                         str(c.get("UID", "")), source=source,
                         kind=_kind(c) if classify else "event"))  # fmt: skip
    return sorted(out, key=lambda e: (e.when, e.what))


@dataclass(frozen=True)
class SyncResult:
    ok: bool
    count: int = 0
    message: str = ""
    at: datetime | None = None


class GoogleCalendar:
    """ลิงก์ + สำเนานัดของผู้ใช้หนึ่งคน · เรียก sync()/connect() จากเธรดแยกได้ (มี lock).

    record(ข้อความ, สำเร็จไหม) = บันทึกสิ่งที่ส่งออกนอกเครื่อง · ไม่มีลิงก์ลับในข้อความ
    """

    def __init__(self, link_file: Path | None = None, cache_file: Path | None = None,
                 fetcher=fetch, record=lambda sent, ok: None, clock=None, tz=None,
                 alert_file: Path | None = None, source: str = "google",
                 future: timedelta = FUTURE, stale_after: timedelta = STALE, sent: str = SENT,
                 classify: bool = False):  # fmt: skip
        self.source = source
        self._future, self._stale_after, self._sent, self._classify = (
            future,
            stale_after,
            sent,
            classify,
        )
        self._link_file = link_file or link_path()
        self._cache_file = cache_file or cache_path()
        # เก็บข้างไฟล์สำเนา (โฟลเดอร์เดียวกัน) · เทสต์ที่ให้ cache_file ชั่วคราวจึงไม่แตะไฟล์จริง
        self._alert_file = alert_file or self._cache_file.with_name("gcal-alerted.json")
        self._alerted_mem: set[str] = set()  # บันทึกไฟล์ไม่ได้ = ยังไม่เตือนซ้ำในรอบนี้
        self._fetch = fetcher
        self._record = record
        self._now = clock or (lambda: datetime.now().astimezone())
        self._tz = tz
        self._lock = threading.Lock()
        self.error = ""  # ดึงครั้งล่าสุดไม่สำเร็จเพราะอะไร ("" = สำเร็จหรือยังไม่เคยดึง)
        self._events: list[Event] = []
        self._at: datetime | None = None
        self._load_cache()

    # ---------- ลิงก์ ----------
    def _link(self) -> str:
        try:
            link = json.loads(self._link_file.read_text(encoding="utf-8")).get("link", "")
        except (OSError, ValueError, AttributeError):
            return ""
        return link if valid_link(link) else ""

    @property
    def connected(self) -> bool:
        return bool(self._link())

    @property
    def hint(self) -> str:
        return hint(self._link())

    @property
    def last_sync(self) -> datetime | None:
        return self._at

    # ---------- สำเนา ----------
    def _load_cache(self) -> None:
        try:
            d = json.loads(self._cache_file.read_text(encoding="utf-8"))
            self._events = [Event.from_json(e) for e in d.get("events", [])]
            self._at = datetime.fromisoformat(d["at"])
        except (OSError, ValueError, KeyError, TypeError):  # ไม่มี/เสีย = ยังไม่มีสำเนา · ดึงครั้งหน้าเขียนใหม่
            self._events, self._at = [], None

    def stale(self, now: datetime | None = None) -> bool:
        return self.connected and (
            self._at is None or (now or self._now()) - self._at > self._stale_after
        )

    def old(self, now: datetime | None = None) -> bool:
        return self._at is not None and (now or self._now()) - self._at > OLD

    def between(self, start: date, days: int) -> list[Event]:
        """นัดที่คาบเกี่ยวช่วงวัน [start, start+days) · นัดทั้งวันหลายวันขึ้นทุกวันที่ครอบ."""
        if not self.connected:
            return []
        tz = _local(self._tz)
        lo = datetime.combine(start, time(0), tzinfo=tz)
        hi = lo + timedelta(days=days)
        return [
            e
            for e in self._events
            if e.when < hi and max(e.end, e.when + timedelta(seconds=1)) > lo
        ]

    def upcoming(self, now: datetime | None = None) -> list[Event]:
        """นัดที่ยังไม่จบ (นัดทั้งวันของวันนี้ยังนับ) · เรียงตามเวลา."""
        if not self.connected:
            return []
        now = now or self._now()
        return [e for e in self._events if (e.end if e.all_day else e.when) >= now]

    # ---------- เตือน (การ์ด 0032) ----------
    def _alerted(self) -> dict:
        try:
            d = json.loads(self._alert_file.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def due_alerts(self, now: datetime, lead: timedelta) -> list[Event]:
        """นัดที่มีเวลา (ไม่ใช่ทั้งวัน) ซึ่ง เวลาเริ่ม − lead ≤ ตอนนี้ < เวลาเริ่ม และยังไม่เคยเตือน · เรียงตามเวลา."""
        if lead <= timedelta(0) or not self.connected:
            return []
        done = set(self._alerted()) | self._alerted_mem
        return [
            e
            for e in self._events
            if not e.all_day and e.when - lead <= now < e.when and e.id not in done
        ]

    def mark_alerted(self, events: list[Event], now: datetime) -> None:
        """จำว่าเตือนแล้ว · เก็บแค่นัดที่เริ่มไม่เกิน 2 วันก่อน (ไฟล์ไม่โตไปเรื่อย ๆ)."""
        keep_after = now - timedelta(days=2)
        data = {k: v for k, v in self._alerted().items()
                if _parse_time(v) is not None and _parse_time(v) >= keep_after}  # fmt: skip
        for e in events:
            data[e.id] = e.when.isoformat()
            self._alerted_mem.add(e.id)
        try:
            fsutil.write_json(self._alert_file, data)
        except OSError:
            pass  # พื้นที่เต็ม: ยังกันเตือนซ้ำในรอบนี้ด้วย _alerted_mem

    # ---------- ดึง ----------
    def _sync(self, link: str) -> SyncResult:
        now = self._now()
        try:
            data = self._fetch(link)
            events = expand(data, now - PAST, now + self._future, self._tz, self._classify,
                            self.source)  # fmt: skip
        except SyncError as e:
            self.error = str(e)
            self._record(self._sent, False)
            return SyncResult(False, 0, str(e), self._at)
        try:
            copy = {"version": 1, "at": now.isoformat(), "events": [e.to_json() for e in events]}
            fsutil.write_json(self._cache_file, copy)
        except OSError:
            self.error = "บันทึกสำเนาปฏิทินไม่ได้ (พื้นที่อาจเต็ม)"
            self._record(self._sent, True)
            return SyncResult(False, 0, self.error, self._at)
        self._record(self._sent, True)
        self._events, self._at, self.error = events, now, ""
        days = self._future.days
        return SyncResult(
            True, len(events), f"ดึงแล้ว {len(events)} รายการ (ช่วง {days} วันข้างหน้า)", now
        )

    def sync(self) -> SyncResult:
        with self._lock:
            link = self._link()
            if not link:
                return SyncResult(False, 0, "ยังไม่ได้เชื่อมต่อปฏิทิน Google")
            return self._sync(link)

    def connect(self, text: str) -> SyncResult:
        """ลองดึงจริงก่อน · สำเร็จแล้วจึงจำลิงก์ (ลิงก์ผิด = ไม่จำ)."""
        link = text.strip()
        if not valid_link(link):
            return SyncResult(
                False, 0, "ลิงก์นี้ไม่ใช่ที่อยู่ปฏิทินของ Google · คัดลอก “ที่อยู่ลับในรูปแบบ iCal” ตามคู่มือ"
            )
        with self._lock:
            result = self._sync(link)
            if result.ok:
                try:
                    fsutil.write_json(self._link_file, {"link": link}, mode=0o600)
                except OSError:
                    return SyncResult(False, 0, "บันทึกการเชื่อมต่อไม่ได้ (พื้นที่อาจเต็ม)", result.at)
            return result

    def disconnect(self) -> None:
        """ลืมลิงก์และลบสำเนา · ไม่แตะนัดที่ผู้ใช้จดในเครื่อง."""
        with self._lock:
            for p in (self._link_file, self._cache_file, self._alert_file):
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            self._events, self._at, self.error = [], None, ""
