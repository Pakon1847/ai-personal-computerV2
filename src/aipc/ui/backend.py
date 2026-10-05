"""วัตถุ Python ที่หน้าจอ QML เรียกใช้.

หลักการ: QML มีหน้าที่วาดเท่านั้น ส่วนการตัดสินใจ ตัวเลข และการตรวจข้อมูลอยู่ใน Python
ซึ่งเทสต์ได้ · QML เห็นวัตถุเหล่านี้เป็นชื่อ เช่น uiSettings.theme หรือ signup.checkUsername(...)

แต่ละ @Property คือค่าที่ QML อ่านได้ และเมื่อ Python ปล่อย signal `changed`
ทุกจุดบนจอที่ใช้ค่านั้นจะวาดใหม่เอง (นี่คือ binding ของ QML)
"""

from __future__ import annotations

import getpass
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from aipc.accounts import validation
from aipc.bench import machine
from aipc.doctor import hardware
from aipc.skills import machine as skill_machine
from aipc.ui import files, settings, thaidate


class UiSettings(QObject):
    changed = Signal()

    def __init__(self, path: Path | None = None, override_theme: str | None = None):
        super().__init__()
        self._path = path
        self._prefs = settings.load(path)
        if override_theme in settings.THEMES:
            self._prefs.theme = override_theme

    @Property(str, notify=changed)
    def theme(self) -> str:
        return self._prefs.theme

    @Property(float, notify=changed)
    def fontScale(self) -> float:  # noqa: N802 — ชื่อแบบ camelCase เพราะ QML เรียกใช้
        return self._prefs.font_scale

    @Slot(str)
    def setTheme(self, theme: str) -> None:  # noqa: N802
        if theme in settings.THEMES and theme != self._prefs.theme:
            self._prefs.theme = theme
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Property(bool, notify=changed)
    def onboarded(self) -> bool:
        return self._prefs.onboarded

    @Property(bool, notify=changed)
    def speakAnswers(self) -> bool:  # noqa: N802
        return self._prefs.speak_answers

    @Slot(bool)
    def setSpeakAnswers(self, on: bool) -> None:  # noqa: N802
        if bool(on) != self._prefs.speak_answers:
            self._prefs.speak_answers = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Property(bool, notify=changed)
    def speakReminders(self) -> bool:  # noqa: N802
        return self._prefs.speak_reminders

    @Slot(bool)
    def setSpeakReminders(self, on: bool) -> None:  # noqa: N802
        if bool(on) != self._prefs.speak_reminders:
            self._prefs.speak_reminders = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Property(bool, notify=changed)
    def useClaude(self) -> bool:  # noqa: N802
        return self._prefs.use_claude

    @Slot(bool)
    def setUseClaude(self, on: bool) -> None:  # noqa: N802
        """สวิตช์ส่งต่อ Claude (การ์ด 0016 หัวข้อ 1) · ปิด = ไม่ถาม Claude และไม่สร้างสกิล ข้อมูลไม่ออกไป Anthropic."""
        if bool(on) != self._prefs.use_claude:
            self._prefs.use_claude = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Slot()
    def finishOnboarding(self) -> None:  # noqa: N802
        """ปิดหน้าแนะนำการใช้งานครั้งแรก · จำไว้ในไฟล์ตั้งค่าของผู้ใช้ (ไม่ขึ้นอีก)."""
        if not self._prefs.onboarded:
            self._prefs.onboarded = True
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Slot(float)
    def setFontScale(self, scale: float) -> None:  # noqa: N802
        if scale in settings.FONT_SCALES and scale != self._prefs.font_scale:
            self._prefs.font_scale = scale
            settings.save(self._prefs, self._path)
            self.changed.emit()


class BackupController(QObject):
    """สำรอง/กู้ข้อมูลลงไดรฟ์ USB (ฟีเจอร์ข้อ 7 · ADR-012) · ทำในเธรดแยก หน้าจอไม่ค้าง."""

    changed = Signal()
    _done = Signal(object)

    def __init__(self, home: Path | None = None, user: str | None = None, drives=None):
        super().__init__()
        import getpass

        self._home = home or Path.home()
        self._user = user or getpass.getuser()
        self._drives_fn = drives  # เทสต์ใส่รายการไดรฟ์ปลอม
        self._busy, self._message = False, ""
        self._drives: list[Path] = []
        self._done.connect(self._on_done)
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        from aipc import backup

        if self._drives_fn:
            self._drives = self._drives_fn()
        else:
            errors = backup.mount_usb()  # เสียบแล้วยังไม่ถูกต่อ = ต่อให้ก่อน
            self._drives = backup.drives()
            if errors and not self._drives:
                self._message = errors[0]
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def drives(self) -> list:
        from aipc import backup

        out = []
        for d in self._drives:
            sets = backup.backups(d, self._user)
            out.append({"name": d.name, "latest": sets[0].name if sets else "", "count": len(sets)})
        return out

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    def _run(self, work, start_msg: str) -> None:
        import threading

        if self._busy:
            return
        self._busy, self._message = True, start_msg
        self.changed.emit()

        def go():
            try:
                r = work()
            except Exception as e:  # noqa: BLE001 · ไดรฟ์ถูกถอด ฯลฯ = บอกผู้ใช้ ไม่ค้าง
                from aipc.backup import Result

                r = Result(False, f"ทำไม่สำเร็จ: {e}")
            self._done.emit(r)

        threading.Thread(target=go, daemon=True).start()

    @Slot(object)
    def _on_done(self, r) -> None:
        self._busy = False
        extra = f" · ข้ามไฟล์ที่เปิดไม่ได้ {len(r.skipped)} ไฟล์" if r.skipped else ""
        self._message = r.message + extra
        self.refresh()

    @Slot(int)
    def backupTo(self, index: int) -> None:  # noqa: N802
        from aipc import backup

        if 0 <= index < len(self._drives):
            d = self._drives[index]
            self._run(
                lambda: backup.backup(self._home, d, self._user),
                f"กำลังสำรองลง {d.name}… อย่าเพิ่งถอดไดรฟ์",
            )

    @Slot(int)
    def restoreLatest(self, index: int) -> None:  # noqa: N802
        from aipc import backup

        if 0 <= index < len(self._drives):
            sets = backup.backups(self._drives[index], self._user)
            if not sets:
                self._message = "ไดรฟ์นี้ไม่มีชุดสำรองของบัญชีนี้"
                self.changed.emit()
                return
            self._run(
                lambda: backup.restore(sets[0], self._home), f"กำลังตรวจและกู้จากชุด {sets[0].name}…"
            )


class VoiceController(QObject):
    """ปุ่ม "อ่านออกเสียง" ที่คำตอบ AI (การ์ด 0019 · Pakon เลือกทำแค่อ่านออกเสียง 2026-10-01).

    available=False (ยังไม่ได้ติดตั้ง /opt/aipc-voice หรือไม่มีตัวเล่นเสียง) = ซ่อนปุ่ม · หน้า Login ไม่มีปุ่มนี้
    key = แถวของคำตอบที่กดอ่าน (หน้าจอใช้เปลี่ยนปุ่มเป็น "หยุดอ่าน")
    """

    # เมธอดที่ต่อกับ signal ต้องมี @Slot: ไม่มี = PySide เพิ่ม slot ให้ตอนรัน ทำให้ QML อ่าน backend ผิดตัวแบบสุ่ม
    # (เทสต์หน้าจอล้มสลับข้อ 2026-10-01 · ใส่ @Slot แล้วผ่าน 4/4 รอบ)
    changed = Signal()
    micChanged = Signal()  # noqa: N815
    transcribed = Signal(str)  # ข้อความที่ถอดได้ · หน้าจอใส่ช่องพิมพ์ (ไม่ส่งเอง · การ์ด 0019 ข้อ 9)
    _state = Signal(int, bool, str)
    _heard = Signal(str, str, float)

    def __init__(
        self, speaker=None, active: bool = True, idle_poll_ms: int = 60_000, listener=None
    ):
        super().__init__()
        from aipc.voice import stt, tts

        self._speaker = (speaker or tts.Speaker(self._weak("_state"))) if active else None
        # กดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) · None = หน้า Login
        self._listener = (listener or stt.Listener(self._weak("_heard"))) if active else None
        self._key, self._job, self._message = -1, -1, ""
        self._transcribing, self._mic_message, self._last_stt_s = False, "", 0.0
        # ตัวอัดหยุดเองเมื่อพูดจบ (การ์ด 0019 ข้อ 10) จากเธรดของมัน → ดูสถานะทุก 0.15 วิระหว่างฟัง
        self._awaiting = False
        self._mic_poll = QTimer(self, interval=150, timeout=self._poll_mic)
        self._state.connect(self._on_state)
        self._heard.connect(self._on_heard)
        self._idle = QTimer(self, interval=idle_poll_ms, timeout=self._idle_check)
        if self._speaker is not None:
            self._idle.start()

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._speaker is not None and self._speaker.available

    @Property(int, notify=changed)
    def speakingKey(self) -> int:  # noqa: N802
        return self._key

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Slot(int, str)
    def speak(self, key: int, text: str) -> None:
        if not self.available:
            return
        self._message = ""
        job = self._speaker.say(text)
        if job < 0:
            self._key, self._message = -1, "ไม่มีข้อความที่อ่านออกเสียงได้"
        elif self._speaker.current == job:  # เปิดตัวอ่านไม่ได้ = _on_state แจ้งข้อผิดพลาดไปแล้ว
            self._key, self._job = key, job
        self.changed.emit()

    @Slot()
    def stop(self) -> None:
        if self._speaker is not None:
            self._speaker.stop()
        self._key = -1
        self.changed.emit()

    @Slot(int, bool, str)
    def _on_state(self, job: int, speaking: bool, error: str) -> None:
        if error:
            self._message = error
        if not speaking and job == self._job:
            self._key = -1
        self.changed.emit()

    def _weak(self, name: str):
        """callback ให้เธรดของตัวอ่าน/ตัวอัด ส่ง signal กลับ โดยไม่ถือ VoiceController ไว้ (ไม่สร้างวงอ้างอิง
        Python ↔ QObject ที่ GC เก็บในจังหวะสุ่มระหว่างหน้าจออื่นกำลังใช้)."""
        import weakref

        ref = weakref.ref(self)

        def emit(*args) -> None:
            me = ref()
            if me is not None:
                getattr(me, name).emit(*args)

        return emit

    @Slot()
    def _idle_check(self) -> None:
        self._speaker.idle_check()

    # ---------- กดค้างเพื่อพูด ----------
    @Property(bool, notify=micChanged)
    def micAvailable(self) -> bool:  # noqa: N802
        return self._listener is not None and self._listener.available

    @Property(bool, notify=micChanged)
    def listening(self) -> bool:
        return self._listener is not None and self._listener.listening

    @Property(bool, notify=micChanged)
    def transcribing(self) -> bool:
        return self._transcribing

    @Property(str, notify=micChanged)
    def micMessage(self) -> str:  # noqa: N802
        return self._mic_message

    @Slot()
    def startListening(self) -> None:  # noqa: N802
        if self._listener is None or self._transcribing:
            return
        if self._key != -1:  # กำลังอ่านออกเสียงอยู่ = หยุดก่อน ไม่ให้ไมค์ได้ยินลำโพง
            self.stop()
        err = self._listener.start()
        self._mic_message = err
        self._awaiting = err == ""
        if self._awaiting:
            self._mic_poll.start()
        self.micChanged.emit()

    @Slot()
    def _poll_mic(self) -> None:
        if self._listener is None or self._listener.listening:
            return
        self._mic_poll.stop()
        if self._awaiting:  # หยุดเองแล้ว กำลังถอด (ผลยังไม่มา)
            self._transcribing, self._mic_message = True, "กำลังถอดเสียง…"
        self.micChanged.emit()

    @Slot()
    def stopListening(self) -> None:  # noqa: N802
        if self._listener is None or not self._listener.listening:
            return
        self._mic_poll.stop()
        self._transcribing, self._mic_message = True, "กำลังถอดเสียง…"
        self.micChanged.emit()
        self._listener.stop()

    @Slot(str, str, float)
    def _on_heard(self, text: str, err: str, secs: float) -> None:
        self._awaiting = False
        self._mic_poll.stop()
        self._transcribing, self._last_stt_s = False, secs
        self._mic_message = err or f"ถอดเสียงใน {secs:.1f} วิ · ตรวจข้อความแล้วกดส่ง"
        self.micChanged.emit()
        if text:
            self.transcribed.emit(text)

    def close(self) -> None:
        if self._speaker is not None:
            self._speaker.close()
        if self._listener is not None:
            self._listener.cancel()


class CloudUsage(QObject):
    """ค่าใช้จ่าย Claude วันนี้ + เพดานต่อวัน (หน้าตั้งค่า) · ข้อมูลจาก aipc.cloud.budget
    · ไม่มี Claude = available False."""

    changed = Signal()

    def __init__(self, budget=None, available: bool = False, poll_ms: int = 15000, ledger=None):
        super().__init__()
        self._b = budget
        self._ledger = ledger  # aipc.cloud.ledger.Ledger · ไม่มี = ไม่แสดงรายการ
        self._available = available and budget is not None
        self._timer = QTimer(
            self, interval=poll_ms, timeout=self.changed.emit
        )  # อ่านซ้ำ: บันทึกจากเธรดอื่น
        if self._available:
            self._timer.start()

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._available

    @Property(float, notify=changed)
    def spentToday(self) -> float:  # noqa: N802
        return self._b.spent() if self._b else 0.0

    @Property(int, notify=changed)
    def callsToday(self) -> int:  # noqa: N802
        return self._b.calls() if self._b else 0

    @Property(float, notify=changed)
    def limit(self) -> float:
        return self._b.limit if self._b else 0.0

    @Property("QVariantList", constant=True)
    def limits(self) -> list:
        from aipc.cloud.budget import LIMITS

        return list(LIMITS)

    @Slot(float)
    def setLimit(self, usd: float) -> None:  # noqa: N802
        if self._b is not None:
            self._b.set_limit(usd)
            self.changed.emit()

    # ---------- สิ่งที่ส่งออกนอกเครื่อง (ledger) ----------
    @Property("QVariantList", notify=changed)
    def outbound(self) -> list:
        """รายการล่าสุด 20 รายการ (ใหม่สุดก่อน) สำหรับการ์ดในหน้าตั้งค่า."""
        from aipc.cloud.ledger import KINDS

        if self._ledger is None:
            return []
        out = []
        for e in self._ledger.entries()[:20]:
            when = str(e.get("time", ""))
            try:
                t = datetime.fromisoformat(when)
                when = f"{thaidate.short_date(t)} {t:%H:%M}"
            except ValueError:
                pass
            sent = str(e.get("sent", ""))
            out.append({"when": when, "kind": KINDS.get(e.get("kind"), str(e.get("kind", ""))),
                        "sent": sent, "preview": sent.replace("\n", " ")[:120],
                        "chars": int(e.get("chars", len(sent))),
                        "cost": float(e.get("cost_usd", 0)), "ok": bool(e.get("ok", True)),
                        "note": str(e.get("note", ""))})  # fmt: skip
        return out

    @Property(int, notify=changed)
    def outboundTotal(self) -> int:  # noqa: N802
        return len(self._ledger.entries()) if self._ledger is not None else 0

    @Slot()
    def clearOutbound(self) -> None:  # noqa: N802
        if self._ledger is not None:
            self._ledger.clear()
            self.changed.emit()


class SystemStatus(QObject):
    """ค่าจริงจากเครื่องสำหรับแถบสถานะและหน้าสุขภาพเครื่อง.

    อ่านจาก aipc.doctor ตัวเดียวกับที่ใช้ตรวจฮาร์ดแวร์ ค่าที่อ่านไม่ได้แสดงว่า "—" ไม่เดา
    อัปเดตนาฬิกาทุก 1 วิ และตรวจเครื่องทุก 10 วิ (การตรวจเรียก vcgencmd จึงไม่ถี่กว่านี้)
    """

    changed = Signal()
    healthChanged = Signal()  # noqa: N815
    readyChanged = Signal()  # noqa: N815
    _readyDone = Signal(object)  # noqa: N815

    def __init__(self, root: Path = Path("/")):
        super().__init__()
        self._root = root
        # ตรวจความพร้อมก่อนสาธิต (aipc.doctor.ready) · app ใส่ ready_inputs ให้
        # (AI พร้อม · เสียง · ไมค์ · Claude)
        self.ready_inputs = lambda: {
            "ai_ready": False, "voice_available": False, "mic_available": False, "claude": None
        }  # fmt: skip
        self._ready: list[dict] = []
        self._ready_busy = False
        self._readyDone.connect(self._on_ready)
        self._now = datetime.now()
        self._checks: list[dict] = []
        self._temp: float | None = None
        self._free_gb: float | None = None
        self._camera = False
        self._network: bool | None = None
        self._clock = QTimer(self, interval=1000, timeout=self._tick)
        self._clock.start()
        self._probe = QTimer(self, interval=10_000, timeout=self.refresh)
        self._probe.start()
        self.refresh()

    @Slot()
    def _tick(self) -> None:
        self._now = datetime.now()
        self.changed.emit()

    # ---------- ตรวจความพร้อมก่อนสาธิต ----------
    @Property("QVariantList", notify=readyChanged)
    def readyChecks(self) -> list:  # noqa: N802
        return self._ready

    @Property(bool, notify=readyChanged)
    def readyBusy(self) -> bool:  # noqa: N802
        return self._ready_busy

    @Property(str, notify=readyChanged)
    def readySummary(self) -> str:  # noqa: N802
        if not self._ready:
            return ""
        bad = sum(c["level"] == "danger" for c in self._ready)
        warn = sum(c["level"] in ("warn", "neutral") for c in self._ready)
        ok = len(self._ready) - bad - warn
        if bad:
            return f"ยังไม่พร้อม · ต้องแก้ {bad} ข้อ · ผ่าน {ok}/{len(self._ready)}"
        if warn:
            return f"พร้อมสาธิต แต่ควรดู {warn} ข้อ · ผ่าน {ok}/{len(self._ready)}"
        return f"พร้อมสาธิต · ผ่านครบ {ok}/{len(self._ready)}"

    @Slot()
    def checkReady(self) -> None:  # noqa: N802
        import threading

        from aipc.doctor import ready

        if self._ready_busy:
            return
        self._ready_busy = True
        self.readyChanged.emit()
        inputs, root = self.ready_inputs(), self._root

        def work():
            try:
                checks = ready.run_all(home=Path.home(), root=root, **inputs)
            except Exception as e:  # noqa: BLE001 · บอกผู้ใช้แทนการค้าง
                checks = [
                    hardware.Check("ready", "ตรวจความพร้อม", hardware.UNKNOWN, f"ตรวจไม่สำเร็จ: {e}")
                ]
            self._readyDone.emit(checks)

        threading.Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_ready(self, checks) -> None:
        level = {hardware.PASS: "ok", hardware.WARN: "warn", hardware.FAIL: "danger"}
        self._ready = [{"title": c.title, "status": c.status, "detail": c.detail, "fix": c.fix,
                        "level": level.get(c.status, "neutral")} for c in checks]  # fmt: skip
        self._ready_busy = False
        self.readyChanged.emit()

    @Slot()
    def refresh(self) -> None:
        self._temp = machine.cpu_temp_c(self._root)
        self._network = skill_machine.has_default_route(self._root)
        try:
            self._free_gb = shutil.disk_usage(Path.home()).free / 1e9
        except OSError:
            self._free_gb = None
        checks = hardware.run_all(self._root)
        self._camera = any(c.id == "camera" and c.status == hardware.PASS for c in checks)
        level = {hardware.PASS: "ok", hardware.WARN: "warn", hardware.FAIL: "danger"}
        self._checks = [
            {"title": c.title, "status": c.status, "detail": c.detail, "fix": c.fix,
             "level": level.get(c.status, "neutral")}
            for c in checks
        ]  # fmt: skip
        self.changed.emit()
        self.healthChanged.emit()

    @Property(str, notify=changed)
    def clock(self) -> str:
        return thaidate.clock(self._now)

    @Property(str, notify=changed)
    def shortDate(self) -> str:  # noqa: N802
        return thaidate.short_date(self._now)

    @Property(str, notify=changed)
    def longDate(self) -> str:  # noqa: N802
        return thaidate.long_date(self._now)

    @Property(str, notify=changed)
    def greeting(self) -> str:
        return thaidate.greeting(self._now)

    @Property(str, notify=changed)
    def networkState(self) -> str:  # noqa: N802
        """on = มีเส้นทางออกนอกเครื่อง · off = ไม่ได้ต่อ · unknown = อ่านไม่ได้ (ไม่เดา)."""
        return {True: "on", False: "off"}.get(self._network, "unknown")

    @Property(int, notify=healthChanged)
    def healthIssues(self) -> int:  # noqa: N802
        return sum(1 for c in self._checks if c["level"] in ("warn", "danger"))

    @Property(str, notify=changed)
    def tempText(self) -> str:  # noqa: N802
        return f"{self._temp:.0f}°C" if self._temp is not None else "—"

    @Property(str, notify=changed)
    def storageText(self) -> str:  # noqa: N802
        return f"ว่าง {self._free_gb:.0f} GB" if self._free_gb is not None else "—"

    @Property(bool, notify=changed)
    def cameraPresent(self) -> bool:  # noqa: N802
        return self._camera

    @Property("QVariantList", notify=healthChanged)
    def checks(self) -> list:
        return self._checks

    @Property(str, constant=True)
    def userName(self) -> str:  # noqa: N802
        """ชื่อ Linux user ที่รันหน้าจออยู่จริง (ยังไม่ใช่บัญชีจาก greetd ซึ่งอยู่ในเฟส 1)."""
        return getpass.getuser()


class FilesBrowser(QObject):
    """หน้า "ไฟล์ของฉัน" · อ่านไฟล์จริงใน home แบบอ่านอย่างเดียว ออกนอก home ไม่ได้."""

    changed = Signal()
    searchChanged = Signal()  # noqa: N815
    _found = Signal(object)

    def __init__(self, root: Path | None = None):
        super().__init__()
        self._root = root or Path.home()
        self._rel = ""
        self._entries: list[dict] = []
        self._error = ""
        # ค้นในเนื้อหาไฟล์ (aipc.files_search) · ทำในเธรดแยก (อ่าน PDF ครั้งแรกอาจนาน)
        self._search = None
        self._results: list[dict] = []
        self._searching, self._search_note, self._search_round = False, "", 0
        self._found.connect(self._on_found)
        self._load()

    def _load(self) -> None:
        try:
            from aipc import files_qa

            self._entries = [
                {**e.to_dict(), "askable": not e.is_dir and files_qa.supported(e.name)}
                for e in files.list_dir(self._root, self._rel)
            ]
            self._error = ""
        except (OSError, files.OutsideHome) as e:
            self._entries, self._error = [], f"เปิดโฟลเดอร์นี้ไม่ได้: {e}"
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def entries(self) -> list:
        return self._entries

    @Property(str, notify=changed)
    def location(self) -> str:
        return "ไฟล์ของฉัน" + ("".join(" / " + p for p in Path(self._rel).parts) if self._rel else "")

    @Property(bool, notify=changed)
    def canGoUp(self) -> bool:  # noqa: N802
        return self._rel != ""

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Property(str, notify=changed)
    def quotaText(self) -> str:  # noqa: N802
        try:
            du = shutil.disk_usage(self._root)
        except OSError:
            return "—"
        return f"ว่าง {du.free / 1e9:.0f} จาก {du.total / 1e9:.0f} GB"

    @Slot(str)
    def open(self, name: str) -> None:
        self._rel = str(Path(self._rel) / name) if self._rel else name
        self._load()

    @Slot(str, result=str)
    def pathOf(self, name: str) -> str:  # noqa: N802
        """path จริงของไฟล์ในโฟลเดอร์ที่เปิดอยู่ (ต้องอยู่ใน home · ไม่งั้น "")."""
        try:
            return str(files.inside(self._root, self._root / self._rel / name))
        except (OSError, files.OutsideHome):
            return ""

    @Slot()
    def up(self) -> None:
        parent = str(Path(self._rel).parent)
        self._rel = "" if parent == "." else parent
        self._load()

    # ---------- ค้นในเนื้อหาไฟล์ ----------
    @Property("QVariantList", notify=searchChanged)
    def searchResults(self) -> list:  # noqa: N802
        return self._results

    @Property(bool, notify=searchChanged)
    def searching(self) -> bool:
        return self._searching

    @Property(str, notify=searchChanged)
    def searchNote(self) -> str:  # noqa: N802
        return self._search_note

    @Slot(str)
    def search(self, query: str) -> None:
        import threading
        import time

        from aipc.files_search import HomeSearch

        query = query.strip()
        self._search_round += 1
        if not query:
            self._results, self._searching, self._search_note = [], False, ""
            self.searchChanged.emit()
            return
        if self._search is None:
            self._search = HomeSearch(self._root)
        self._searching, self._search_note = True, "กำลังค้นในไฟล์…"
        self.searchChanged.emit()
        rnd, engine = self._search_round, self._search

        def work():
            t0 = time.monotonic()
            try:
                hits, n, capped = engine.search(query)
                self._found.emit((rnd, hits, n, capped, time.monotonic() - t0, ""))
            except Exception as e:  # noqa: BLE001 · บอกผู้ใช้แทนการค้างเงียบ
                self._found.emit((rnd, [], 0, False, 0.0, str(e)))

        threading.Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_found(self, res) -> None:
        rnd, hits, n, capped, secs, err = res
        if rnd != self._search_round:  # มีการค้นใหม่แล้ว
            return
        self._searching = False
        self._results = []
        for h in hits:
            parent = Path(h.name).parent.as_posix()
            folder = "ไฟล์ของฉัน" + ("" if parent == "." else " / " + parent.replace("/", " / "))
            self._results.append({"path": h.name, "name": Path(h.name).name, "folder": folder,
                                  "snippet": h.snippet})  # fmt: skip
        if err:
            self._search_note = f"ค้นไม่สำเร็จ: {err}"
        elif not hits:
            self._search_note = f"ไม่พบไฟล์ที่ตรง (ค้นใน {n} ไฟล์)"
        else:
            more = f" · อ่านแค่ {n} ไฟล์ล่าสุด" if capped else ""
            self._search_note = (
                f"พบ {len(hits)} ไฟล์ · ค้นใน {n} ไฟล์ {secs:.1f} วิ{more} · ไม่ออกนอกเครื่อง"
            )
        self.searchChanged.emit()

    @Slot(str, result=str)
    def resultPath(self, rel: str) -> str:  # noqa: N802
        """path จริงของผลค้น (ต้องอยู่ใน home)."""
        try:
            return str(files.inside(self._root, self._root / rel))
        except (OSError, files.OutsideHome):
            return ""

    @Slot(str)
    def openFolderOf(self, rel: str) -> None:  # noqa: N802
        parent = str(Path(rel).parent)
        self._rel = "" if parent == "." else parent
        self._load()


class LoginController(QObject):
    """สถานะหน้า Login.

    โหมด greeter + มี visiond (การ์ด 0015): เปิดหน้ามาก็สแกนเลย · จำได้ = ขึ้นชื่อ แล้วเข้าระบบเองใน 1.5 วิ
    (กด "ไม่ใช่ฉัน" ยกเลิกได้) · เข้าด้วยตั๋วใบหน้าผ่าน greetd/PAM ไม่มีรหัสผ่าน · ไม่มี visiond = "unavailable"
    ใช้รหัสผ่านตามเดิม · โหมดสาธิต (--demo-scan) ไว้ดูหน้าตาแต่ละสถานะ และขึ้นแถบเตือนเสมอ
    """

    changed = Signal()
    _scanned = Signal(int, object)  # (รอบที่สแกน, ผลจาก visiond) · ส่งจากเธรดสแกนกลับเธรดหลัก
    _progress = Signal(int, object)
    STATES = ("unavailable", "scanning", "found", "unknown", "manual")
    AUTO_LOGIN_MS = 1500

    def __init__(self, dev_mode: bool, demo_scan: str | None = None,
                 greeter_session: list[str] | None = None, connect=None, face=None):  # fmt: skip
        super().__init__()
        self._dev = dev_mode
        # โหมด greeter (การ์ด 0003): greetd รันหน้านี้ก่อนมีใครเข้าเครื่อง · PAM ของ OS ตรวจรหัสผ่าน
        self._session = greeter_session
        self._connect = connect
        self._demo = demo_scan in self.STATES
        # face(req, on_progress) → dict · ตัวจริง = aipc.vision.client.request (เฉพาะโหมด greeter)
        self._face = face
        self._round = 0
        self._found_user = self._found_name = self._message = ""
        self._scanned.connect(self._on_scanned)
        self._progress.connect(self._on_progress)
        from aipc.ui.enrollview import EnrollView

        # ภาพสดในวงกล้องระหว่างสแกน (QML: loginScan · image://loginscan) · Pakon ขอ 2026-09-30
        self.scan_view = EnrollView()
        self._timer = None
        if self._demo:
            self._state = demo_scan
        elif self._session is not None and self._face is not None:
            self._state = "scanning"
            self._start_scan()
        else:
            self._state = "unavailable"

    @Property(str, notify=changed)
    def scanState(self) -> str:  # noqa: N802
        return self._state

    @Property(bool, notify=changed)
    def demo(self) -> bool:
        return self._demo

    @Property(bool, constant=True)
    def greeterMode(self) -> bool:  # noqa: N802
        return self._session is not None

    @Property(str, notify=changed)
    def foundName(self) -> str:  # noqa: N802
        return "Pakon" if self._demo else self._found_name

    @Property(str, notify=changed)
    def scanMessage(self) -> str:  # noqa: N802
        """คำแนะนำสดระหว่างสแกน หรือเหตุผลที่สแกนไม่ผ่าน (จาก visiond)."""
        return self._message

    @Property(bool, constant=True)
    def faceReady(self) -> bool:  # noqa: N802
        """มี visiond ให้สแกน (หน้า Login จริง) · ใช้แสดงปุ่ม "สแกนหน้า"."""
        return self._session is not None and self._face is not None

    @Slot()
    def wake(self) -> None:
        """หน้า Login เปิดขึ้นมา (ครั้งแรก หรือกลับจากหน้าสมัคร) → สแกนใหม่ถ้ายังไม่ได้สแกนอยู่.

        เดิมสแกนแค่ตอนเริ่มโปรแกรม: สมัคร + ลงทะเบียนหน้าแล้วกลับมา หน้า Login ไม่สแกนอีก (พบบน Pi 5 2026-09-30)
        """
        if self.faceReady and not self._demo and self._state in ("unavailable", "unknown"):
            self.setScanState("scanning")

    @Slot(str)
    def setScanState(self, state: str) -> None:  # noqa: N802
        if state not in self.STATES:
            return
        self._round += 1  # ผลของการสแกนรอบเก่าที่ตามมาทีหลัง = ทิ้ง
        if self._timer is not None:
            self._timer.stop()
        self._state, self._message = state, ""
        self.scan_view.clear()
        if state == "scanning" and not self._demo:
            if self._face is None:
                self._state = "unavailable"
            else:
                self._start_scan()
        self.changed.emit()

    # ---------- สแกนผ่าน visiond ----------
    def _start_scan(self) -> None:
        import threading

        self._round += 1
        n = self._round

        def work():
            res = self._face({"op": "identify", "timeout_s": 8},
                             lambda m: self._progress.emit(n, m))  # fmt: skip
            self._scanned.emit(n, res)

        threading.Thread(target=work, daemon=True).start()

    @Slot(int, object)
    def _on_progress(self, n: int, m: dict) -> None:
        if n != self._round or self._state != "scanning":
            return
        self.scan_view.update(m)
        hint = str(m.get("hint", ""))
        if hint != self._message:
            self._message = hint
            self.changed.emit()

    @Slot(int, object)
    def _on_scanned(self, n: int, res: dict) -> None:
        if n != self._round or self._state != "scanning":
            return
        self.scan_view.clear()  # จบสแกน = ไม่เก็บภาพหน้าไว้
        state = res.get("state")
        self._message = str(res.get("message", ""))
        if res.get("ok") and state == "found":
            self._found_user = str(res.get("user", ""))
            self._found_name = _display_name(self._found_user)
            self._state = "found"
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(lambda: self._face_sign_in(n))
            self._timer.start(self.AUTO_LOGIN_MS)
        elif state in ("unavailable", "no-templates", "no-camera"):
            self._state = "unavailable"
        elif state == "locked":
            self._state = "manual"
        else:
            self._state = "unknown"
        self.changed.emit()

    def _face_sign_in(self, n: int) -> None:
        from PySide6.QtCore import QCoreApplication

        from aipc.login import greetd

        if n != self._round or self._state != "found":
            return
        try:
            g = (self._connect or greetd.Greetd.connect)()
            try:
                r = greetd.face_login(g, self._found_user, self._session)
            finally:
                g.close()
        except (OSError, greetd.ProtocolError):
            r = greetd.LoginResult(False, greetd.FACE_FAIL)
        if r.ok:
            QTimer.singleShot(0, QCoreApplication.quit)
            return
        self._state, self._message = "manual", r.message
        self.changed.emit()

    @Slot(str, str, result=str)
    def signIn(self, username: str, password: str) -> str:  # noqa: N802
        """คืน "" เมื่อเข้าได้ หรือข้อความบอกเหตุผลที่เข้าไม่ได้.

        ยังไม่มีการตรวจรหัสผ่านจริง: โหมดพัฒนาให้ผ่านเพื่อเดินหน้าจอต่อ (มีแถบเตือน)
        นอกโหมดพัฒนาต้องปฏิเสธเสมอ ห้ามให้ผ่านโดยไม่ได้ตรวจ
        """
        if self._session is not None:
            return self._greetd_sign_in(username, password)
        if self._dev:
            return ""
        return "ยังเข้าสู่ระบบจริงไม่ได้ในหน้าต่างนี้ · หน้า Login จริงคือโหมด greeter (การ์ด 0003)"

    def _greetd_sign_in(self, username: str, password: str) -> str:
        from PySide6.QtCore import QCoreApplication, QTimer

        from aipc.login import greetd

        try:
            g = (self._connect or greetd.Greetd.connect)()
        except (OSError, greetd.ProtocolError) as e:
            return f"ติดต่อ greetd ไม่ได้ ({e}) · เข้าเครื่องทางสำรองด้วย Ctrl+Alt+F2"
        try:
            r = greetd.login(g, username.strip(), password, self._session)
        except (OSError, greetd.ProtocolError) as e:
            return f"greetd ตอบผิดปกติ ({e}) · ลองอีกครั้ง หรือใช้ Ctrl+Alt+F2"
        finally:
            g.close()
        if not r.ok:
            return "\n".join([*r.notes, r.message])
        # greetd จะเริ่มเซสชันของผู้ใช้หลัง greeter ปิดตัวเอง
        QTimer.singleShot(0, QCoreApplication.quit)
        return ""


def _display_name(user: str) -> str:
    """ชื่อที่แสดงจากช่อง comment ของบัญชี (ตั้งตอนสมัคร) · อ่านไม่ได้ = ชื่อผู้ใช้."""
    try:
        import pwd

        return pwd.getpwnam(user).pw_gecos.split(",")[0] or user
    except (ImportError, KeyError):
        return user


class SessionController(QObject):
    """เซสชันจริงของผู้ใช้ (การ์ด 0004): หน้าจอ V2 คือทั้งเซสชัน ไม่มีเดสก์ท็อปของ Pi.

    active = รันจาก aipc-session หลัง login ผ่าน greetd แล้ว · ไม่ active = หน้าต่างพัฒนาตามเดิม
    "ออก" ในเซสชันจริงต้องจบเซสชันทั้งหมด (H3) ไม่ใช่แค่สลับไปหน้า Login ในแอป
    ซึ่งจะทิ้งโปรเซสของผู้ใช้ค้างไว้ · จบด้วย `labwc --exit` แล้ว greetd กลับหน้า Login เอง
    """

    changed = Signal()
    EXIT_CMD = ["labwc", "--exit"]

    def __init__(self, active: bool, runner=None):
        super().__init__()
        self._active = active
        self._run = runner or _run_quiet
        self._error = ""

    @Property(bool, constant=True)
    def active(self) -> bool:
        return self._active

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Slot(result=bool)
    def logout(self) -> bool:
        """คืน True เมื่อสั่งจบเซสชันแล้ว · False = ไม่ได้อยู่ในเซสชันจริง หรือสั่งไม่สำเร็จ (ดู error)."""
        if not self._active:
            return False
        code = self._run(self.EXIT_CMD)
        if code != 0:
            # ไม่ปิดเงียบ ๆ (H2): ผู้ใช้ต้องรู้ว่ายังไม่ได้ออก
            self._error = f"ออกจากระบบไม่สำเร็จ (labwc --exit ตอบ {code}) · ลองอีกครั้ง"
            self.changed.emit()
            return False
        return True


def _run_quiet(args: list[str]) -> int:
    import subprocess

    try:
        return subprocess.run(args, check=False, capture_output=True, timeout=10).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


HELPER = "/usr/local/sbin/aipc-accounts"  # ตัวช่วย root ของการ์ด 0012 (ติดตั้งโดย install-greeter.sh)


def run_accounts_helper(request: dict, timeout: float = 30) -> dict:
    """เรียกตัวช่วยผ่าน sudo (-n = ห้ามถามรหัส ถ้ากฎ sudo ไม่ตรงให้ล้มทันที ไม่ค้าง).

    คำขอส่งทาง stdin เป็น JSON · ตัวช่วยตรวจทุกอย่างซ้ำเอง (H7) หน้าจอแค่ส่งและแสดงผล
    """
    import json
    import subprocess

    try:
        r = subprocess.run(["sudo", "-n", HELPER], input=json.dumps(request).encode(),
                           capture_output=True, timeout=timeout, check=False)  # fmt: skip
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "ตัวจัดการบัญชีไม่ตอบ · ลองอีกครั้ง"}
    except OSError as e:
        return {"ok": False, "message": f"เรียกตัวจัดการบัญชีไม่ได้ ({e.strerror or e})"}
    try:
        out = json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "message": "ตัวจัดการบัญชียังไม่ได้ติดตั้งในเครื่องนี้ (install-greeter.sh)"}
    return out if isinstance(out, dict) and "ok" in out else {"ok": False, "message": "ตอบผิดรูปแบบ"}


class SignupController(QObject):
    """ฟอร์มสมัครและลืมรหัสผ่าน (การ์ด 0012) · กฎตรวจชุดเดียวกับตัวช่วยสร้างบัญชีจริง.

    real = หน้า Login จริง (greeter) → ส่งคำขอให้ตัวช่วย root ผ่าน sudo
    dev  = หน้าต่างพัฒนา → ผลเป็นแบบจำลองที่เขียนว่า "จำลอง" ชัดเจน (H5)
    นอกจากสองแบบนี้ = บอกว่าสมัครได้เฉพาะหน้า Login จริง
    งานเรียกตัวช่วยทำในเธรดแยก (useradd + scrypt ใช้เวลาราววินาที) แล้วส่งผลกลับด้วย signal
    """

    changed = Signal()
    finished = Signal("QVariantMap")
    _result = Signal("QVariantMap")
    # ขั้นใบหน้า (การ์ด 0015 หัวข้อ 11): ลงทะเบียนผ่าน visiond หลังสร้างบัญชีแล้ว
    faceProgress = Signal(str, "QVariantMap")  # noqa: N815 · คำแนะนำ, จำนวนเฟรมต่อท่า
    faceFinished = Signal("QVariantMap")  # noqa: N815
    _face_progress = Signal(object)
    _face_result = Signal(object)

    def __init__(self, real: bool = False, dev: bool = False, runner=None, face=None):
        super().__init__()
        self._real, self._dev = real, dev
        self._run = runner or run_accounts_helper
        self._face = face  # face(req, on_progress) → dict · ตัวจริง = aipc.vision.client.request
        self._busy = False
        self._result.connect(self._on_result)
        self._face_progress.connect(self._on_face_progress)
        from aipc.ui.enrollview import EnrollView

        self.enroll_view = EnrollView()  # ภาพสดตอนลงทะเบียน (QML: signupEnroll · image://signupface)
        self._face_result.connect(self._on_face_result)

    @Property(bool, constant=True)
    def faceAvailable(self) -> bool:  # noqa: N802
        """ลงทะเบียนใบหน้าตอนสมัครได้ไหม · หน้าต่างพัฒนา = ได้แบบจำลอง."""
        return self._face is not None or (self._dev and not self._real)

    @Slot(str, str, result=bool)
    def enrollFace(self, username: str, password: str) -> bool:  # noqa: N802
        """ผู้ใช้ติ๊กยินยอมแล้วกดเริ่ม · visiond ตรวจรหัสผ่านก่อนเปิดกล้องเสมอ (ไม่เชื่อหน้าจอนี้)."""
        if self._busy:
            return False
        if self._face is None:
            if self._dev and not self._real:
                msg = "จำลอง (โหมดพัฒนา) · ไม่ได้เปิดกล้องหรือเก็บใบหน้าจริง"
                done = {"ok": True, "simulated": True, "state": "saved", "message": msg}
                self.faceFinished.emit(done)
                return True
            self.faceFinished.emit({"ok": False, "state": "unavailable",
                                    "message": "ระบบใบหน้าไม่พร้อม · ข้ามขั้นนี้ได้"})  # fmt: skip
            return True
        import threading

        consent = datetime.now().astimezone().isoformat(timespec="seconds")
        req = {"op": "enroll", "username": username.strip(), "password": password,
               "consent_at": consent}  # fmt: skip
        self._busy = True
        self.changed.emit()

        def progress(m: dict) -> None:
            self._face_progress.emit(m)

        def work():
            self._face_result.emit(self._face(req, progress))

        threading.Thread(target=work, daemon=True).start()
        return True

    @Slot(object)
    def _on_face_progress(self, m: dict) -> None:
        self.enroll_view.update(m)
        self.faceProgress.emit(str(m.get("hint", "")), dict(m.get("poses") or {}))

    @Slot(object)
    def _on_face_result(self, res: dict) -> None:
        self.enroll_view.clear()  # ไม่เก็บภาพหน้าไว้หลังจบงาน
        self._busy = False
        self.changed.emit()
        self.faceFinished.emit(dict(res))

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    def _submit(self, request: dict) -> bool:
        if self._busy:
            return False
        if not self._real:
            if self._dev:
                msg = "จำลอง (โหมดพัฒนา) · ไม่ได้สร้างหรือเปลี่ยนบัญชีจริง"
                done = {"ok": True, "simulated": True, "message": msg}
                if request.get("op") == "delete":  # ให้เห็นหน้าใบยืนยัน แต่ทุกบรรทัดเขียนว่าจำลอง
                    done["checks"] = [{"what": "จำลอง: ไม่ได้ลบอะไรจริง", "gone": False}]
                self.finished.emit(done)
            else:
                self.finished.emit(
                    {"ok": False, "message": "สมัคร กู้คืน และลบบัญชีได้เฉพาะหน้า Login จริงของเครื่อง"}
                )
            return True
        import threading

        self._busy = True
        self.changed.emit()
        threading.Thread(target=lambda: self._result.emit(self._run(request)), daemon=True).start()
        return True

    @Slot("QVariantMap")
    def _on_result(self, result: dict) -> None:
        self._busy = False
        self.changed.emit()
        self.finished.emit(result)

    @Slot(str, str, str, str, result=bool)
    def create(self, display: str, username: str, password: str, pin: str) -> bool:
        return self._submit({"op": "create", "display_name": display.strip(), "username": username,
                             "password": password, "pin": pin})  # fmt: skip

    @Slot(str, str, str, result=bool)
    def recover(self, username: str, pin: str, new_password: str) -> bool:
        return self._submit({"op": "recover", "username": username.strip(), "pin": pin,
                             "new_password": new_password})  # fmt: skip

    @Slot(str, str, str, result=bool)
    def deleteAccount(self, username: str, password: str, confirm: str) -> bool:  # noqa: N802
        """ลบบัญชีถาวร (ข้อเสนอ 2026-10-03) · ตัวช่วย root ตรวจทุกข้อเองและตอบใบยืนยันกลับมา."""
        return self._submit({"op": "delete", "username": username.strip(), "password": password,
                             "confirm": confirm.strip()})  # fmt: skip

    @Slot(str, str, result="QVariantMap")
    def checkPin(self, pin: str, confirm: str) -> dict:  # noqa: N802
        r = validation.check_pin(pin, confirm)
        return {"ok": r.ok, "message": r.message}

    @Slot(str, result="QVariantMap")
    def checkDisplayName(self, name: str) -> dict:  # noqa: N802
        r = validation.check_display_name(name)
        return {"ok": r.ok, "message": r.message}

    @Slot(str, result="QVariantMap")
    def checkUsername(self, name: str) -> dict:  # noqa: N802
        r = validation.check_username(name)
        return {"ok": r.ok, "message": r.message}

    @Slot(str, str, result="QVariantMap")
    def checkPassword(self, password: str, confirm: str) -> dict:  # noqa: N802
        r = validation.check_password(password, confirm)
        return {"ok": r.ok, "message": r.message}

    @Slot(str, result=int)
    def strength(self, password: str) -> int:
        return validation.password_strength(password)

    @Slot(int, result=str)
    def strengthLabel(self, score: int) -> str:  # noqa: N802
        return validation.STRENGTH_LABELS[max(0, min(score, 4))]


class SkillsController(QObject):
    """ต่อสกิลเข้ากับหน้าแชท · handle(ข้อความ) คืน "การ์ดคำตอบ" ที่ QML วาดได้ทันที.

    การ์ดมีรูปเดียวกันทุกชนิด: badge (ใช้สกิลอะไร เพราะอะไร ใครทำงาน), title, chips, lines
    และ confirmToken เมื่อต้องถามก่อนทำ · Plan ที่รอยืนยันเก็บไว้ที่ Python ไม่ส่งไปให้ QML
    หน้าจอส่งกลับมาได้แค่ token จึงแก้คำสั่งระหว่างทางไม่ได้
    """

    # สิ่งที่ระบบมีตอนนี้ (llm stt vlm camera ยังไม่มี) · เพิ่มเมื่อต่อ backend จริงแล้วเท่านั้น
    AVAILABLE: frozenset[str] = frozenset()
    WORKER_LABEL = {"code": "โค้ด", "llm": "LLM", "code+llm": "LLM + โค้ด",
                    "stt+llm": "เสียง → LLM", "camera+vlm": "กล้อง → โมเดลดูภาพ"}  # fmt: skip
    NEED_LABEL = {
        "llm": "โมเดลภาษาในเครื่องพร้อมตอบ (ตอนนี้กำลังเริ่มหรือยังไม่ได้ติดตั้ง)",
        "stt": "ระบบถอดเสียงภาษาไทย (ADR-005)",
        "vlm": "โมเดลดูภาพ (ROADMAP 0.11)",
        "camera": "สิทธิ์ใช้กล้องสำหรับสกิล (ADR-015)",
    }
    LEVEL = {"ok": "ok", "warn": "warn", "danger": "danger", "neutral": "neutral"}
    RISK_LABEL = {"low": "ความเสี่ยงต่ำ", "medium": "ความเสี่ยงกลาง", "high": "ความเสี่ยงสูง"}
    RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
    TICK_MS = 30_000  # การ์ด 0001 หัวข้อ 7: ตรวจนัดทุก 30 วินาที

    reminderDue = Signal("QVariantMap")  # noqa: N815
    remindersChanged = Signal()  # noqa: N815

    skillsChanged = Signal()  # noqa: N815
    forgeDone = Signal("QVariantMap", str)  # noqa: N815 · สกิลอัตโนมัติ (การ์ด 0017): การ์ดผลลัพธ์, ข้อความเดิมของผู้ใช้
    _forged = Signal(object)

    def __init__(self, executor=None, root: Path = Path("/"), reminders_path=None, clock=None,
                 run_timer: bool = True, llm_ready=None, forge=None, user_skills=None,
                 weather=None, claude_on=None):  # fmt: skip
        super().__init__()
        # "llm" พร้อมเมื่อ llama-server ของผู้ใช้ตอบได้จริง (ChatController) · ไม่ใช่ค่าคงที่ (H5)
        self._llm_ready = llm_ready or (lambda: False)
        from aipc.skills import actions, manifest, reminders

        # สกิลอัตโนมัติ (การ์ด 0017): forge(คำขอ, skills=, check=, revise=) → forge.Proposal
        # · None = ไม่มี Claude
        self._forge = forge
        self._claude_on = claude_on or (lambda: True)  # สวิตช์ Claude ในหน้าตั้งค่า (ผู้ใช้ปิดเองได้)
        self._forging = False
        self._user = user_skills
        self._builtin = manifest.load_builtin()
        self._skills = self._builtin + (user_skills.load() if user_skills is not None else [])
        self._forged.connect(self._on_forged)
        self._exec = executor or actions.Executor()
        self._root = root
        self._home = Path.home()  # หาไฟล์ด้วยการพิมพ์ในแชท ค้นใน home ของผู้ใช้
        # สกิลอากาศ (aipc.skills.weather.Weather · Open-Meteo) · None = ไม่มี (หน้า Login)
        self._weather = weather
        self._weather_day: str | None = None  # ถามเมืองกลับแล้ว รอผู้ใช้ตอบชื่อเมือง
        self._file_search = None
        self._pending: dict[str, object] = {}
        self._counter = 0
        self._undo_token = ""  # ย้อนได้เฉพาะคำสั่งล่าสุด (คำสั่งเก่ากว่าอาจถูกคำสั่งใหม่ทับไปแล้ว)
        self._now = clock or (lambda: datetime.now().astimezone())
        self._store = reminders.ReminderStore(reminders_path)
        now = self._now()
        broken = self._store.broken
        self._missed = [] if broken else reminders.missed_since_last_session(self._store, now)
        self._clock_back = reminders.clock_went_back(self._store, now)
        self._save_failed = False
        if self._missed:  # รายงานครั้งเดียว (นัดครั้งเดียว = fired · นัดซ้ำ = เลื่อนไปครั้งถัดไป)
            try:
                self._store.save(now)
            except (OSError, reminders.Unreadable):
                # พบ 2026-09-28: บันทึกล้มตรงนี้เคยทำให้หน้าจอเปิดไม่ขึ้น → ล่มซ้ำจนเซสชันจบ
                self._save_failed = True
        self._timer = QTimer(self, interval=self.TICK_MS, timeout=self.tick)
        if run_timer:  # หน้า greeter (ยังไม่มีใครเข้าเครื่อง) ไม่มีนัดของใครให้เตือน และไม่เขียนไฟล์
            self._timer.start()

    def _badge(self, skill, reason: str) -> dict:
        badge = {"name": skill.name, "reason": reason, "worker": self.WORKER_LABEL[skill.worker]}
        if self._is_user(skill.id):  # สกิลที่ Claude สร้าง: การ์ดมีปุ่มลบ / ไม่ใช่แบบนี้ (การ์ด 0017 ชั้นที่ 2)
            badge.update(forgedId=skill.id, forgedVersion=self._user.info(skill.id)["version"])
        return badge

    def _is_user(self, skill_id: str) -> bool:
        return self._user is not None and all(s.id != skill_id for s in self._builtin)

    def available(self) -> set[str]:
        return set(self.AVAILABLE) | ({"llm"} if self._llm_ready() else set())

    @Property("QVariantList", notify=skillsChanged)
    def skills(self) -> list:
        out = []
        for s in self._skills:
            missing = [n for n in s.needs if n not in self.available()]
            out.append({
                "id": s.id, "name": s.name, "description": s.description,
                "worker": self.WORKER_LABEL[s.worker], "permissions": s.permission_labels(),
                "ready": not missing, "missing": [self.NEED_LABEL[n] for n in missing],
                "byClaude": self._is_user(s.id),
            })  # fmt: skip
        return out

    @Property(bool, constant=True)
    def simulated(self) -> bool:
        return self._exec.dry_run

    # ---------- นัดหมาย (การ์ดออกแบบ 0001) ----------

    @staticmethod
    def _when_text(dt) -> str:
        return f"{thaidate.short_date(dt)} {dt.year + thaidate.BE_OFFSET} · {dt:%H:%M} น."

    @staticmethod
    def _repeat_text(r) -> str:
        from aipc.skills.when import repeat_name

        return f" · ซ้ำ{repeat_name(r.repeat)}" if getattr(r, "repeat", "") else ""

    def _reminder_dict(self, r) -> dict:
        return {"id": r.id, "what": r.what, "when": self._when_text(r.when) + self._repeat_text(r)}

    @Property("QVariantList", notify=remindersChanged)
    def upcoming(self) -> list:
        return [self._reminder_dict(r) for r in self._store.upcoming(self._now())]

    @Property("QVariantList", constant=True)
    def missed(self) -> list:
        return [self._reminder_dict(r) for r in self._missed]

    @Property(str, notify=remindersChanged)
    def reminderWarning(self) -> str:  # noqa: N802
        if self._store.broken:
            return "อ่านไฟล์นัดหมายไม่ได้ (ไฟล์และสำเนาเสียทั้งคู่) · ยังไม่ได้เขียนทับ รอคุณตัดสิน"
        if self._save_failed:
            return "บันทึกนัดหมายไม่สำเร็จ (พื้นที่อาจเต็ม) · ยังเตือนในรอบนี้ แต่ปิดเครื่องแล้วอาจแจ้งซ้ำว่าพลาด"
        if self._clock_back:
            return "นาฬิกาเครื่องอาจไม่ถูก (เวลาถอยหลังจากที่เคยเห็น) · การเตือนอาจคลาดเคลื่อน"
        if self._store.recovered_from_backup:
            return "ไฟล์นัดหมายเสีย จึงใช้สำเนาล่าสุดแทน · นัดที่เพิ่งเพิ่มอาจหาย"
        return ""

    @Slot()
    def tick(self) -> None:
        from aipc.skills import reminders

        if self._store.broken:
            return
        t = reminders.tick(self._store, self._now())
        for r in t.due:
            self.reminderDue.emit(self._reminder_dict(r))
        if t.save_failed:
            self._save_failed = True
        if t.due or t.save_failed:
            self.remindersChanged.emit()

    def _agenda_card(self, text: str) -> dict | None:
        """ "วันนี้ต้องทำอะไร" (ฟีเจอร์ข้อ 5) · None = ไม่ใช่คำถามเรื่องตารางนัด."""
        from aipc.skills import agenda

        q = agenda.parse(text, self._now().date())
        if q is None:
            return None
        items = agenda.items_for(self._store, q)
        day = thaidate.short_date(q.start)
        span = (
            day
            if q.days == 1
            else f"{day}–{thaidate.short_date(q.start + timedelta(days=q.days - 1))}"
        )
        reminder = next((s for s in self._skills if s.id == "reminder"), None)
        card = self._plain("reminder", f"{q.label} ({span}) มี {len(items)} นัด" if items
                           else f"{q.label} ({span}) ยังไม่มีนัด")  # fmt: skip
        if reminder is not None:
            card["badge"] = self._badge(reminder, "ถามตารางนัด · อ่านจากนัดที่บันทึกไว้")
        now = self._now()
        card["lines"] = [
            f"{'✓ ' if r.fired or r.when < now else ''}{self._when_text(r.when)} · {r.what}"
            + self._repeat_text(r)
            for r in items
        ] or ["จดนัดได้เลย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”"]
        return card

    def _reminder_card(self, route, text: str) -> dict:
        from aipc.skills import reminders, when

        card = {
            "kind": "reminder",
            "badge": self._badge(route.skill, route.reason),
            "title": "",
            "chips": [],
            "lines": [],
            "confirmToken": "",
            "page": "",
        }
        if self._store.broken:
            card["title"] = "จดนัดไม่ได้ตอนนี้"
            card["lines"] = [self.reminderWarning]
            return card
        w = when.parse(text, self._now().replace(tzinfo=None))
        # นัดซ้ำที่เดาเวลา/วัน (ไม่มั่นใจแต่มีเวลา) = การ์ดยืนยันพร้อมบอกว่าเดาตรงไหน · นัดครั้งเดียวที่ไม่มั่นใจ = ไม่จด
        if w.at is None or not (w.confident or (w.repeat and not w.problem)):
            card["title"] = "ยังจดนัดนี้ไม่ได้"
            card["lines"] = [w.problem, "ลองระบุให้ชัด เช่น “พรุ่งนี้ 14:00 ส่งรายงาน”"]
            return card
        self._counter += 1
        token = f"r{self._counter}"
        r = reminders.Reminder(w.what, reminders.aware(w.at), created=self._now(), repeat=w.repeat)
        self._pending[token] = r
        card["title"] = f"บันทึกนัด “{w.what}” ใช่ไหม"
        card["chips"] = [{"text": self._when_text(w.at), "kind": "accent"}]
        if w.repeat:
            name = f"ซ้ำ{when.repeat_name(w.repeat)} {w.at:%H:%M} น."
            card["chips"].append({"text": name, "kind": "accent" if w.confident else "warn"})
        card["lines"] = [f"ตีความเอง: {a}" for a in w.assumptions]
        if w.repeat:
            card["lines"].insert(
                0, f"เตือนครั้งแรก {self._when_text(w.at)} แล้วตั้งครั้งถัดไปเอง · ลบได้ในรายการนัด"
            )
        card["lines"].append("วันที่คำนวณด้วยโค้ด ไม่ใช่ให้ AI เดา · ไม่ถูกให้กด “ไม่ใช่” แล้วพิมพ์ใหม่")
        card["confirmToken"] = token
        return card

    # ---------- สกิลแบบขั้นตอน (.md · ข้อเสนอ 2026-09-29 หัวข้อ 10.1) ----------

    def _steps_card(self, route, text: str) -> dict:
        """แสดงทุกขั้นก่อนทำ · มีขั้นที่สั่งเครื่อง = ถามยืนยันครั้งเดียว (ความเสี่ยงของขั้นที่สูงสุด) แล้วทำตามลำดับ."""
        skill = route.skill
        prefix = {"llm": "ถาม AI: ", "say": "บอก: ", "action": ""}
        lines = [f"{i}. {prefix[s.kind]}{s.text}" for i, s in enumerate(skill.steps, 1)]
        card = {"kind": "steps", "badge": self._badge(skill, route.reason), "title": "",
                "chips": [], "lines": lines, "confirmToken": "", "page": ""}  # fmt: skip
        acting = [s.plan.spec.risk for s in skill.steps if s.plan is not None]
        if not acting:  # บอกข้อความ / ถาม AI อย่างเดียว = ไม่แตะเครื่อง ทำได้เลย
            return self._run_steps(skill, text, card)
        self._counter += 1
        token = f"s{self._counter}"
        self._pending[token] = ("steps", skill, text)
        risk = max(acting, key=self.RISK_ORDER.__getitem__)
        card["title"] = f"จะทำ {len(skill.steps)} ขั้นนี้ ใช่ไหม"
        card["chips"] = [{"text": self.RISK_LABEL[risk], "kind": "neutral"}]
        card["confirmToken"] = token
        return card

    def _run_steps(self, skill, text: str, card: dict) -> dict:
        """ทำทีละขั้นตามลำดับ · ขั้นไหนไม่สำเร็จ = หยุดตรงนั้นและบอกว่าเหลือกี่ขั้นที่ไม่ได้ทำ."""
        lines, simulated, total = [], False, len(skill.steps)
        undo, irreversible = [], False
        for i, s in enumerate(skill.steps, 1):
            if s.kind == "say":
                lines.append(s.text)
            elif s.kind == "llm":  # ขั้นสุดท้ายเสมอ (ตัวตรวจบังคับ) · หน้าจอส่งข้อความของผู้ใช้ให้ AI พร้อมคำสั่งนี้
                card.update(llm=True, prompt=s.text, llmText=text)
                lines.append(f"{i}. ส่งให้ AI ในเครื่องทำต่อ")
            else:
                out = self._exec.execute(s.plan)
                simulated = simulated or out.simulated
                if out.page:
                    card["page"] = out.page
                if not out.ok:
                    self._record(skill, False)
                    lines.append(f"✗ {i}. {s.plan.summary} · {out.message}")
                    if i < total:
                        lines.append(f"ขั้นที่เหลือ {total - i} ขั้นไม่ได้ทำ")
                    card.update(title=f"หยุดที่ขั้น {i}: {out.message}", lines=lines,
                                chips=[{"text": "ไม่สำเร็จ", "kind": "danger"}])  # fmt: skip
                    return card
                lines.append(f"{'จำลอง' if out.simulated else '✓'} {i}. {s.plan.summary}")
                undo = list(out.undo) + undo  # ย้อนจากขั้นหลังสุดก่อน
                irreversible = irreversible or not out.undo
        self._record(skill, True)
        chip = {"text": "จำลอง", "kind": "warn"} if simulated else {"text": "ทำแล้ว", "kind": "ok"}
        title = f"ทำครบ {total} ขั้นแล้ว" + (" (จำลอง)" if simulated else "")
        card.update(title=title, lines=lines, confirmToken="", chips=[chip])
        if undo:
            card["undoToken"] = self._offer_undo(undo)
            if irreversible:
                lines.append("ย้อนกลับได้เฉพาะขั้นที่ปรับเสียง")
        return card

    def _offer_undo(self, plans) -> str:
        self._pending.pop(self._undo_token, None)  # ปุ่มย้อนของคำสั่งก่อนหน้าใช้ไม่ได้แล้ว
        self._counter += 1
        self._undo_token = f"u{self._counter}"
        self._pending[self._undo_token] = ("undo", tuple(plans))
        return self._undo_token

    @Slot(str, result="QVariantMap")
    def undo(self, token: str) -> dict:
        """ปุ่ม "ย้อนกลับ" ใต้การ์ดคำสั่ง · ใช้ได้ครั้งเดียว และเฉพาะคำสั่งล่าสุด."""
        t0 = time.monotonic()
        return self._why(self._undo(token), t0)

    def _undo(self, token: str) -> dict:
        item = self._pending.pop(token, None) if token == self._undo_token else None
        card = {"kind": "command", "badge": {}, "title": "", "chips": [], "lines": [],
                "confirmToken": "", "page": ""}  # fmt: skip
        if not (isinstance(item, tuple) and item[0] == "undo"):
            card["title"] = "ย้อนกลับไม่ได้แล้ว (ย้อนได้เฉพาะคำสั่งล่าสุด ครั้งเดียว)"
            return card
        self._undo_token = ""
        done = []
        for plan in item[1]:
            out = self._exec.execute(plan)
            if not out.ok:
                card["title"] = f"ย้อนกลับไม่สำเร็จ: {out.message}"
                card["chips"] = [{"text": "ไม่สำเร็จ", "kind": "danger"}]
                card["lines"] = [f"✓ {d}" for d in done]
                return card
            done.append(plan.summary)
        card["title"] = "ย้อนกลับแล้ว"
        card["chips"] = [{"text": "คืนสภาพเดิม", "kind": "ok"}]
        card["lines"] = done
        return card

    def _run_plan(self, plan) -> dict:
        out = self._exec.execute(plan)
        if out.simulated:
            title = plan.summary + " (จำลอง)"
        else:
            title = plan.summary if out.ok else out.message
        card = {
            "title": title,
            "chips": [{"text": "จำลอง" if out.simulated else ("ทำแล้ว" if out.ok else "ไม่สำเร็จ"),
                       "kind": "warn" if out.simulated else ("ok" if out.ok else "danger")}],
            "lines": [out.message] if out.simulated else [],
            "page": out.page,
        }  # fmt: skip
        if out.undo:
            card["undoToken"] = self._offer_undo(out.undo)
        elif out.ok and not out.simulated and plan.action in ("open_url", "open_app"):
            card["lines"].append("คำสั่งนี้ย้อนกลับไม่ได้ · ปิดหน้าต่างที่เปิดขึ้นมาเองได้")
        return card

    # ---------- AI ในเครื่องเลือกสกิล (อาจารย์ขอ · ADR-007 ข้อ 6 · ข้อเสนอ 2026-09-29 งานข้อ ④) ----------
    def tool_catalog(self, text: str = "") -> list:
        """สกิลที่ AI ในเครื่องเลือกได้ (อาจารย์ขอ · ADR-007 ข้อ 6 · งานข้อ ④) · ดู aipc.skills.catalog."""
        from aipc.skills import catalog, retrieval

        # การ์ด 0018: สกิลในตัวส่งทุกครั้ง (ส่วนต้นคงที่ แคชใช้ได้) · สกิลของผู้ใช้เกิน 5 ตัว = ส่งเฉพาะที่ใกล้ข้อความ
        user = [s for s in self._skills if self._is_user(s.id)]
        base = [s for s in self._skills if not self._is_user(s.id)]
        return catalog.tools(
            base + retrieval.pick(user, text), self.available(), forge=self.canForge
        )

    # ---------- สกิลอัตโนมัติ (การ์ด 0017) ----------
    @Property(bool, notify=skillsChanged)
    def canForge(self) -> bool:  # noqa: N802
        return self._forge is not None and self._user is not None and bool(self._claude_on())

    FORGING_LINES = ["ครั้งแรกรอประมาณ 30–60 วินาที · ครั้งหน้าสั่งแบบนี้ AI ในเครื่องทำเองได้เลย",
                     "Claude เห็นเฉพาะประโยคนี้ ไม่เห็นแชท นัด หรือไฟล์ของคุณ"]  # fmt: skip

    def _plain(self, kind: str, title: str, lines=(), chips=()) -> dict:
        return {"kind": kind, "badge": {}, "title": title, "chips": list(chips),
                "lines": list(lines),
                "confirmToken": "", "page": ""}  # fmt: skip

    def _start_forge(self, text: str, revise_id: str = "", feedback: str = "") -> dict:
        import threading

        from aipc.skills import userskills

        if self._forge is not None and self._user is not None and not self._claude_on():
            return self._plain("needs", "สร้างสกิลใหม่ไม่ได้: ปิดการใช้ Claude ไว้",
                               ["เปิดได้ที่หน้าตั้งค่า › Claude · ระหว่างปิด ไม่มีข้อมูลออกไป Anthropic"])  # fmt: skip
        if not self.canForge:
            return self._plain("needs", "สร้างสกิลใหม่ไม่ได้: เครื่องนี้ยังไม่มี Claude",
                               ["ติดตั้งและเข้าสู่ระบบ Claude Code ก่อน (การ์ด 0016)"])  # fmt: skip
        if self._forging:
            return self._plain("forging", "กำลังสร้างสกิลอื่นอยู่ รอสักครู่แล้วสั่งใหม่")
        self._forging = True
        others = [s for s in self._skills if s.id != revise_id]
        revise = (self._user.current_md(revise_id), feedback) if revise_id else None

        def work():
            try:

                def check(md):
                    return userskills.gate(md, others, revise_id)[1]

                p = self._forge(text, skills=others, revise=revise, check=check)
            except Exception as e:  # noqa: BLE001 · ทุกความผิดพลาด = บอกผู้ใช้ ไม่ให้หน้าจอรอค้าง
                p = e
            self._forged.emit((p, text, revise_id))

        threading.Thread(target=work, daemon=True).start()
        title = "กำลังให้ Claude แก้สกิลตามที่บอก…" if revise_id else "กำลังให้ Claude สร้างสกิลสำหรับงานนี้…"
        chip = {"text": "ส่งออกนอกเครื่อง: เฉพาะประโยคนี้", "kind": "neutral"}
        return self._plain("forging", title, self.FORGING_LINES, [chip])

    @Slot(object)
    def _on_forged(self, result) -> None:
        from aipc.skills import manifest

        p, text, revise_id = result
        self._forging = False
        errors = [str(p)] if isinstance(p, Exception) else list(p.errors)
        new = None
        if not isinstance(p, Exception) and p.skill_md:
            try:
                new = self._user.install(p.skill_md, self._skills, request=text, model=p.model,
                                         cost_usd=p.cost_usd, replacing=revise_id)  # fmt: skip
            except manifest.InvalidSkill as e:
                errors = list(e.errors)
            except OSError as e:
                errors = [f"บันทึกไม่ได้: {e}"]
        if new is None:
            title = "แก้สกิลไม่สำเร็จ" if revise_id else "สร้างสกิลไม่สำเร็จ"
            card = self._plain("forge-failed", title, [*errors[:2], "ไม่ได้ติดตั้งอะไร"])
            card["fallback"] = not revise_id  # หน้าจอให้ Claude ตอบคำขอนี้แทน (การ์ด 0016)
            self.forgeDone.emit(card, text)
            return
        self._reload()
        card = dict(self.handleAs(new.id, text))
        v = self._user.info(new.id)["version"]
        note = (f"แก้สกิล “{new.name}” แล้ว (รุ่น {v})" if revise_id
                else f"สร้างสกิลใหม่ “{new.name}” แล้ว (Claude สร้าง) · ครั้งหน้าสั่งแบบนี้ได้เลย")  # fmt: skip
        card["lines"] = [note, *card.get("lines", [])]
        self.forgeDone.emit(card, text)

    def _reload(self) -> None:
        self._skills = self._builtin + self._user.load()
        self.skillsChanged.emit()

    def _record(self, skill, ok: bool) -> None:
        if self._is_user(skill.id) and self._user.record(skill.id, ok):
            self._reload()  # ทำไม่สำเร็จ 2 ครั้งติด = ปิดเอง (ชั้นที่ 3)

    @Slot(str, result="QVariantMap")
    def removeSkill(self, skill_id: str) -> dict:  # noqa: N802
        if not self._is_user(skill_id) or not self._user.remove(skill_id):
            return self._plain("command", "ลบไม่ได้: ไม่ใช่สกิลที่ Claude สร้าง")
        self._reload()
        return self._plain("command", "ลบสกิลนี้แล้ว",
                           ["กลับไปเหมือนไม่เคยมีสกิลนี้ · สั่งใหม่เมื่อไหร่ก็สร้างใหม่ได้"],
                           [{"text": "ลบแล้ว", "kind": "ok"}])  # fmt: skip

    @Property("QVariantList", notify=skillsChanged)
    def userSkills(self) -> list:  # noqa: N802
        """สกิลที่ Claude สร้างให้ผู้ใช้คนนี้ ทั้งที่เปิดและปิดอยู่ (หน้า Skill · จัดการ/ย้อนรุ่น/ลบ)."""
        if self._user is None:
            return []
        out = []
        for m in self._user.load_all():
            e = self._user.info(m.id)
            detail = (
                [s.text for s in m.steps] if m.steps else [m.prompt.strip().splitlines()[0][:120]]
            )
            out.append({
                "id": m.id, "name": m.name, "description": m.description, "detail": detail,
                "version": e["version"], "versions": self._user.versions(m.id),
                "enabled": e["enabled"],
                "uses": e["uses"],
                "imported": e.get("model") == self.IMPORT_TAG,
                "request": e.get("request") or m.extra.get("request", ""),
                "created": (e.get("created") or m.extra.get("created", ""))[:10],
            })  # fmt: skip
        return out

    # ---------- แชร์สกิลเป็นไฟล์ (ฟีเจอร์ข้อ 9 · ADR-011 ข้อเสนอ) ----------
    IMPORT_TAG = "นำเข้าจากไฟล์"

    @Slot(str, result=str)
    def exportSkill(self, skill_id: str) -> str:  # noqa: N802
        """บันทึกสกิลเป็นไฟล์ .md ใน ~/สกิลที่ส่งออก (ไฟล์ของฉัน) ไว้คัดลอกลง USB/ให้บัญชีอื่น · คืนข้อความบอกผล."""
        if not self._is_user(skill_id):
            return "ส่งออกได้เฉพาะสกิลที่ Claude สร้างหรือที่นำเข้า"
        md = self._user.current_md(skill_id)
        dest = Path.home() / "สกิลที่ส่งออก" / f"{skill_id}.md"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md, encoding="utf-8", newline="\n")
        except OSError as e:
            return f"ส่งออกไม่ได้: {e.strerror or e}"
        return f"บันทึกแล้วที่ ไฟล์ของฉัน / สกิลที่ส่งออก / {dest.name}"

    @Slot(str, bool, result=str)
    def importSkill(self, path: str, install: bool) -> str:  # noqa: N802
        """ไฟล์สกิลจากภายนอก: ตรวจด้วยประตูเดียวกับสกิลอัตโนมัติ (0017) · install=False = ดูก่อน · คืนข้อความ."""
        from aipc.skills import manifest, userskills

        if self._user is None:
            return "บัญชีนี้ติดตั้งสกิลเพิ่มไม่ได้"
        try:
            md = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return f"อ่านไฟล์ไม่ได้: {e}"
        m, errors = userskills.gate(md, self._skills)
        if m is None:
            return "ติดตั้งไม่ได้: " + "; ".join(errors[:2])
        detail = " → ".join(s.text for s in m.steps) if m.steps else "งานภาษาโดย AI ในเครื่อง"
        perms = ", ".join(m.permission_labels()) or "ไม่ขอสิทธิ์พิเศษ"
        if not install:
            return (
                f"สกิล “{m.name}”: {detail} · สิทธิ์: {perms} · "
                "ไฟล์มาจากภายนอก ตรวจแล้วผ่าน · กดอีกครั้งเพื่อติดตั้ง"
            )
        try:
            self._user.install(md, self._skills, request=f"{self.IMPORT_TAG} {Path(path).name}",
                               model=self.IMPORT_TAG)  # fmt: skip
        except (manifest.InvalidSkill, OSError) as e:
            return f"ติดตั้งไม่ได้: {e}"
        self._reload()
        return f"ติดตั้งสกิล “{m.name}” แล้ว · ดู/ปิด/ลบได้ที่หน้า Skill"

    @Slot(str, int, result=str)
    def revertSkill(self, skill_id: str, version: int) -> str:  # noqa: N802
        """กลับไปใช้รุ่นเก่า · คืนข้อความบอกผล ("" = สำเร็จ)."""
        from aipc.skills import manifest

        if not self._is_user(skill_id):
            return "ไม่ใช่สกิลที่ Claude สร้าง"
        try:
            self._user.revert(skill_id, version, self._skills)
        except manifest.InvalidSkill as e:
            return "ย้อนไม่ได้: " + "; ".join(e.errors[:2])
        self._reload()
        return ""

    @Slot(str, bool)
    def setSkillEnabled(self, skill_id: str, on: bool) -> None:  # noqa: N802
        if self._is_user(skill_id):
            self._user.set_enabled(skill_id, on)
            self._reload()

    @Slot(str, str, str, result="QVariantMap")
    def reviseSkill(self, skill_id: str, feedback: str, text: str) -> dict:  # noqa: N802
        """ผู้ใช้บอกว่าสกิลผิด (ชั้นที่ 2) · ผิดครั้งที่ 2 ติดกัน = ปิดแทนการแก้ (ชั้นที่ 3)."""
        if not self._is_user(skill_id):
            return self._plain("command", "แก้ไม่ได้: ไม่ใช่สกิลที่ Claude สร้าง")
        if self._user.wrong(skill_id):
            self._reload()
            return self._plain("command", "ปิดสกิลนี้แล้ว",
                               ["บอกว่าไม่ถูก 2 ครั้งติดกัน จึงหยุดใช้ไว้ก่อน · เปิดคืนหรือลบได้ที่หน้า Skill"],
                               [{"text": "ปิดแล้ว", "kind": "warn"}])  # fmt: skip
        request = text or self._user.info(skill_id).get("request", "")
        return self._start_forge(request, skill_id, feedback)

    @Slot(str, str, result="QVariantMap")
    def handleAs(self, skill_id: str, text: str) -> dict:  # noqa: N802
        """AI ในเครื่องเลือกสกิลนี้ → ทำทางเดียวกับที่ตัวคัดสกิลเลือก (ยืนยันก่อนถ้าเป็นงานที่แตะเครื่อง)."""
        t0 = time.monotonic()
        return self._why(self._handle_as(skill_id, text), t0)

    def _handle_as(self, skill_id: str, text: str) -> dict:
        from aipc.skills import catalog, router

        if skill_id == catalog.CREATE_SKILL:  # AI ในเครื่องขอให้ Claude สร้างสกิล (การ์ด 0017)
            return self._start_forge(text)
        if skill_id == "reminder" and (card := self._agenda_card(text)):  # AI เลือกนัด แต่เป็นคำถาม
            return card
        skill = next((s for s in self._skills if s.id == skill_id), None)

        if (
            skill is None or skill.id in catalog.NOT_FOR_AI
        ):  # AI เดาชื่อที่ไม่มี = ตอบแบบคุยทั่วไป ไม่ใช้เครื่องมือ
            card = {"kind": "chat", "llm": True, "prompt": "", "tools": False, "badge": {}}
            return {**card, "title": "", "chips": [], "lines": [], "confirmToken": "", "page": ""}
        missing = [n for n in skill.needs if n not in self.available()]
        route = router.Route("needs" if missing else "skill", skill, "AI ในเครื่องเลือกสกิลนี้",
                             missing=missing, candidates=[skill.id])  # fmt: skip
        return self._card(route, text)

    # ---------- ทำไมได้คำตอบนี้ (ข้อเสนอ 2026-10-03) ----------
    WHO = {"weather": "สกิลอากาศ · โค้ดในเครื่อง + บริการ Open-Meteo", "files": "ค้นไฟล์ · โค้ดในเครื่อง",
           "forging": "Claude (cloud) กำลังสร้างสกิล", "forge-failed": "Claude (cloud)"}  # fmt: skip
    WHY = {"weather": "ตรงรูปประโยคถามอากาศ (กฎ) · ไม่ผ่าน AI จึงไม่เดาตัวเลข",
           "files": "ตรงรูปประโยคหาไฟล์ (กฎ) · AI ในเครื่องเปิดไฟล์เองไม่ได้",
           "forging": "ขอตั้งโหมด/งานประจำที่ยังไม่มีสกิล"}  # fmt: skip

    def _why(self, card: dict, t0: float) -> dict:
        """เติม card["why"] = [{k, v}] จากสิ่งที่เกิดจริง.

        การ์ดที่ส่งต่อให้ AI ตอบ = ChatController อธิบายเองตอนตอบเสร็จ
        """
        out = card.pop("_outbound", None)
        if card.get("llm") and card.get("kind") != "steps":
            return card
        badge = card.get("badge") or {}
        kind = card.get("kind", "")
        if badge.get("name"):
            who = f"สกิล “{badge['name']}” · {badge.get('worker', '')}"
        else:
            who = self.WHO.get(kind, "โค้ดในเครื่อง")
        why = badge.get("reason") or self.WHY.get(kind, "")
        if out is None and kind == "forging" and card.get("chips"):
            out = "ส่งเฉพาะประโยคนี้ไป Claude · ดูได้ที่ ตั้งค่า › สิ่งที่ส่งออกนอกเครื่อง"
        elif out is None:
            out = "ไม่มี · ทำในเครื่องทั้งหมด"
        rows = [{"k": "ใครตอบ", "v": who}]
        if why:
            rows.append({"k": "ทำไมทางนี้", "v": why})
        rows += [{"k": "ข้อมูลออกนอกเครื่อง", "v": out},
                 {"k": "ใช้เวลา", "v": f"{time.monotonic() - t0:.2f} วินาที"}]  # fmt: skip
        card["why"] = rows
        return card

    @Slot(str, result="QVariantMap")
    def handle(self, text: str) -> dict:
        """AI ในเครื่องพร้อม = แบบผสม (router.route_ai_first) · ไม่พร้อม = กฎก่อน (router.route)."""
        t0 = time.monotonic()
        return self._why(self._handle(text), t0)

    def _handle(self, text: str) -> dict:
        from aipc.skills import router

        if card := self._agenda_card(text):  # ถามตารางนัด = ตอบจากไฟล์นัดด้วยโค้ด ไม่ใช่จดนัดใหม่
            return card
        from aipc.skills.fileintent import file_intent, file_time
        from aipc.skills.weather import place_in, weather_intent

        if self._weather is not None:
            if self._weather_day is not None:  # ตอบชื่อเมืองที่ถามกลับไป
                day, self._weather_day = self._weather_day, None
                city = place_in(text) or (text.strip() if len(text.strip()) <= 30 else "")
                if city:
                    return self._weather_card(day, city)
            if ask := weather_intent(text):  # อากาศจริง = Open-Meteo โดยตรง ไม่ผ่าน Claude
                if not ask.city:
                    self._weather_day = ask.day
                    return {"kind": "weather", "badge": {}, "chips": [], "confirmToken": "",
                            "page": "", "title": "อากาศที่เมืองไหนครับ",
                            "lines": ["พิมพ์ชื่อจังหวัดหรือเมือง เช่น เชียงใหม่ · กทม. · หาดใหญ่"]}  # fmt: skip
                return self._weather_card(ask.day, ask.city)

        if label := file_time(text):  # ดูไฟล์ตามช่วงเวลา ("ไฟล์ที่แก้เมื่อวาน")
            return self._files_card(text, label)
        if file_intent(text):  # หาไฟล์ของผู้ใช้ = ค้นในเครื่องด้วยโค้ด (AI เปิดไฟล์ไม่ได้)
            return self._files_card(text)
        if self._llm_ready():
            r = router.route_ai_first(text, self._skills)
            if r.kind == "create":  # ตั้งโหมด/งานประจำที่ยังไม่มีสกิล (การ์ด 0017)
                return (
                    self._start_forge(text)
                    if self.canForge
                    else self._card(router.Route("chat"), text)
                )
            return self._card(r, text)
        return self._card(router.route(text, self._skills, self.available()), text)

    def _weather_card(self, day: str, city: str) -> dict:
        from aipc.skills.weather import Ask, answer

        card = {"kind": "weather", "badge": {}, "chips": [], "confirmToken": "", "page": ""}
        try:
            place, fc = self._weather.lookup(city)
        except LookupError:
            return {**card, "title": f"ไม่รู้จักเมือง “{city}”", "lines": ["ลองพิมพ์ชื่อจังหวัดเต็ม ๆ อีกครั้ง"]}
        except (OSError, ValueError):
            return {**card, "title": "ดูพยากรณ์อากาศไม่ได้ตอนนี้",
                    "lines": ["เครื่องต่ออินเทอร์เน็ตไม่ได้ หรือบริการพยากรณ์อากาศไม่ตอบ",
                              "ลองใหม่อีกครั้ง"]}  # fmt: skip
        title, lines = answer(Ask(day, city), place, fc)
        sent = getattr(self._weather, "last_sent", [])
        out = ("ส่งไป Open-Meteo: " + " · ".join(sent)) if sent else ("ไม่มี · ใช้ผลที่ดึงไว้ไม่เกิน 15 นาที")
        return {**card, "title": title, "lines": lines, "_outbound": out}

    def _files_card(self, text: str, label: str | None = None) -> dict:
        """ผลค้นไฟล์ใน home (aipc.files_search) · ผล docs/benchmarks/2026-10-01-file-intent."""
        from aipc.files_search import HomeSearch

        if self._file_search is None:
            self._file_search = HomeSearch(self._home)
        when = ""
        if label is None:
            hits, n, capped = self._file_search.search(text, 5)
        else:
            from aipc.skills.fileintent import LABELS, time_range, topic

            since, until = time_range(label, self._now().replace(tzinfo=None))
            about = topic(text)
            hits, n, capped = self._file_search.search(about, 5, since=since, until=until,
                                                       by_time=not about)  # fmt: skip
            when = f"แก้ไข{LABELS[label]}" if label != "latest" else "แก้ไขล่าสุด"
            when += f" เรื่อง “{about}”" if about else ""
        files = []
        for h in hits:
            parent = Path(h.name).parent.as_posix()
            folder = "ไฟล์ของฉัน" + ("" if parent == "." else " / " + parent.replace("/", " / "))
            files.append({"name": Path(h.name).name, "abs": str(self._home / h.name),
                          "folder": folder, "snippet": h.snippet})  # fmt: skip
        more = f" · อ่านแค่ {n} ไฟล์ล่าสุด" if capped else ""
        return {"kind": "files", "badge": {}, "chips": [], "confirmToken": "", "page": "",
                "title": (f"ไฟล์ที่{when}" if when else f"พบ {len(files)} ไฟล์ที่ตรง") if files
                else (f"ไม่พบไฟล์ที่{when}" if when else "ไม่พบไฟล์ที่ตรง"),
                "lines": [(f"มี {n} ไฟล์ในช่วงนี้ (ดูจากเวลาแก้ไขไฟล์){more} · ไม่ออกนอกเครื่อง" if label else
                           f"ค้นในเนื้อหา {n} ไฟล์ในโฟลเดอร์ของคุณ{more} · ไม่ออกนอกเครื่อง"
                           + (" · ลองใช้คำที่อยู่ในไฟล์ เช่น ชื่อร้าน ชื่อคน" if not files else ""))],
                "files": files}  # fmt: skip

    def _card(self, r, text: str) -> dict:
        from aipc.skills import machine

        if r.kind == "skill" and r.tied:  # คะแนนเท่ากัน = ถาม ไม่เดา
            import dataclasses

            names = [s.name for s in self._skills if s.id in r.tied]
            self._counter += 1
            token = f"t{self._counter}"
            self._pending[token] = ("tie", dataclasses.replace(r, tied=[]), text)
            others = " · ".join(n for n in names if n != r.skill.name)
            return {"kind": "skill", "badge": self._badge(r.skill, r.reason),
                    "title": f"หมายถึงสกิล “{r.skill.name}” ใช่ไหม",
                    "chips": [{"text": n, "kind": "neutral"} for n in names],
                    "lines": [f"ข้อความนี้ตรงกับหลายสกิลเท่า ๆ กัน (มี {others} ด้วย) · ถ้าไม่ใช่ กด “ไม่ใช่” "
                              "แล้วพิมพ์ให้ชัดขึ้น"],
                    "confirmToken": token, "page": ""}  # fmt: skip

        card = {
            "kind": r.kind,
            "badge": {},
            "title": "",
            "chips": [],
            "lines": [],
            "confirmToken": "",
            "page": "",
        }

        if r.kind == "command":
            card["badge"] = self._badge(r.skill, r.reason)
            risk = self.RISK_LABEL[r.command.plan.spec.risk]
            if r.command.needs_confirmation:
                self._counter += 1
                token = f"c{self._counter}"
                self._pending[token] = r.command.plan
                card.update(
                    title=f"หมายถึง “{r.command.plan.summary}” ใช่ไหม",
                    lines=[f"ได้ยินว่า “{r.command.heard}” · ชื่อไม่ตรงเป๊ะ จึงถามก่อน"],
                    chips=[{"text": risk, "kind": "neutral"}],
                    confirmToken=token,
                )
            else:
                card.update(self._run_plan(r.command.plan))
                card["chips"].append({"text": risk, "kind": "neutral"})
        elif r.kind == "skill" and r.skill.id == "reminder":
            return self._reminder_card(r, text)
        elif r.kind == "skill" and r.skill.id == "machine-status":
            card["badge"] = self._badge(r.skill, r.reason)
            d = machine.ask(self._root)
            card["title"] = d.headline
            card["chips"] = [{"text": f.text, "kind": self.LEVEL[f.level]} for f in d.findings]
            card["lines"] = [f"ลองทำ: {a}" for a in d.advice]
            if d.unknown:
                card["lines"].append("อ่านไม่ได้ (จึงไม่สรุป): " + ", ".join(d.unknown))
            card["page"] = ""
        elif r.kind == "skill" and r.skill.steps:
            return self._steps_card(r, text)
        elif r.kind == "skill" and r.skill.worker == "llm":
            # สกิลที่ LLM ทำ (สกิล 1 แปล): ให้หน้าจอถาม LLM ด้วย prompt ของสกิล (การ์ด 0013)
            card.update(
                kind="chat", llm=True, badge=self._badge(r.skill, r.reason), prompt=r.skill.prompt
            )
        elif r.kind in ("needs", "skill"):
            card["badge"] = self._badge(r.skill, r.reason)
            card["kind"] = "needs"
            card["title"] = f"สกิล “{r.skill.name}” ยังใช้ไม่ได้"
            card["lines"] = ["ต้องมีก่อน: " + self.NEED_LABEL[n] for n in (r.missing or r.skill.needs)]
        elif self._llm_ready():
            card.update(kind="chat", llm=True, prompt="")  # คุยทั่วไป → LLM ในเครื่อง (การ์ด 0013)
        else:
            card["title"] = "ยังตอบไม่ได้: ยังไม่ได้เชื่อมต่อโมเดลในเครื่อง"
            card["lines"] = [
                "ข้อความนี้ไม่ได้ถูกส่งไปที่ไหน · ลองสั่งงานเครื่อง เช่น “เปิดยูทูบ” หรือถาม “ทำไมเครื่องช้า”"
            ]
        return card

    @Slot(str, bool, result="QVariantMap")
    def confirm(self, token: str, yes: bool) -> dict:
        t0 = time.monotonic()
        return self._why(self._confirm(token, yes), t0)

    def _confirm(self, token: str, yes: bool) -> dict:
        plan = self._pending.pop(token, None)
        card = {
            "kind": "command",
            "badge": {},
            "title": "",
            "chips": [],
            "lines": [],
            "confirmToken": "",
            "page": "",
        }
        from aipc.skills import reminders

        if plan is None:
            card["title"] = "คำสั่งนี้หมดอายุแล้ว"
        elif not yes:
            card["title"] = "ยกเลิกแล้ว ไม่ได้ทำอะไร"
        elif isinstance(plan, tuple) and plan[0] == "tie":
            _, route, text = plan
            card = self._card(route, text)
            if card.get("llm"):
                card["llmText"] = text  # หน้าจอส่งข้อความเดิมให้ AI พร้อม prompt ของสกิลที่ผู้ใช้ยืนยัน
            return card
        elif isinstance(plan, tuple) and plan[0] == "steps":
            _, skill, text = plan
            card.update(kind="steps", badge=self._badge(skill, "ยืนยันแล้ว"))
            return self._run_steps(skill, text, card)
        elif isinstance(plan, reminders.Reminder):
            try:
                self._store.add(plan, self._now())
            except (OSError, reminders.Unreadable) as e:
                card["title"] = f"บันทึกไม่สำเร็จ: {e}"
                return card
            self.remindersChanged.emit()
            card["kind"] = "reminder"
            card["title"] = f"บันทึกแล้ว: {plan.what}"
            card["chips"] = [{"text": self._when_text(plan.when), "kind": "ok"}]
            card["lines"] = ["จะเตือนตอนถึงเวลาขณะใช้เครื่องอยู่ · ถ้าปิดเครื่องอยู่ จะแจ้งตอนเข้าใช้ครั้งถัดไป"]
        else:
            card.update(self._run_plan(plan))
        return card


class ChatController(QObject):
    """แชทกับ LLM ในเครื่อง (การ์ด 0013) · ถาม llama-server ของผู้ใช้ในเธรดแยก แล้วส่ง token กลับทีละคำ.

    active=False (หน้า Login) = ไม่ติดต่อ AI เลย · สถานะมาจากการถาม /health จริงทุก 5 วิ (H5)
    คำตอบของ LLM เป็นข้อความเท่านั้น สั่ง Action ไม่ได้ (H8)
    """

    from aipc.skills.catalog import SYSTEM, TOOLS_HINT  # ข้อความเดียวกับตัววัด spikes.skill_select

    STATUS_TEXT = {"ready": "โมเดล: พร้อม · ในเครื่อง", "loading": "โมเดล: กำลังโหลด…",
                   "down": "โมเดล: ไม่พร้อม", "off": "โมเดล: ไม่ใช้ในหน้านี้",
                   "restarting": "AI กำลังเริ่มใหม่…"}  # fmt: skip
    # T7: AI ที่เคยพร้อมแล้วล่ม → systemd เปิดใหม่เอง (Pi 5: 13 วิ) · บอกว่ากำลังเริ่มใหม่ได้แค่ช่วงนี้
    # เกินนี้ยังไม่กลับ = บอก "ไม่พร้อม" ตามจริง ไม่ให้ผู้ใช้รอข้อความที่ไม่มีวันจริง
    RESTART_GRACE_S = 120
    NOTE = {"stopped": "หยุดแล้ว", "crashed": "ตอบไม่จบ: AI หยุดทำงาน · ระบบกำลังเปิด AI ใหม่เอง"}

    changed = Signal()
    streamChanged = Signal()  # noqa: N815
    statusChanged = Signal()  # noqa: N815
    finished = Signal(str, str)  # ข้อความ, หมายเหตุ ("" = จบปกติ)
    skillRequested = Signal(str, str)  # noqa: N815 · AI เลือกสกิล (id, ข้อความของผู้ใช้) · หน้าจอให้ SkillsController ทำต่อ
    _token = Signal(str)
    _done = Signal(object)
    _health = Signal(str)

    def __init__(self, active: bool = True, target=None, store=None, poll_ms: int = 5000,
                 tools=None, cloud=None, model_name: str = "", forge: bool = False,
                 claude_on=None):  # fmt: skip
        super().__init__()
        # ไฮบริด (การ์ด 0016): cloud(คำถาม, บทสนทนา) → CloudReply · None = ไม่มี Claude ในเครื่องนี้
        self._cloud = cloud
        self._claude_on = claude_on or (lambda: True)  # สวิตช์ Claude ในหน้าตั้งค่า
        self._forge = forge  # มีเครื่องมือ create-skill (การ์ด 0017) → บอก AI ใน system prompt
        self._model_name = model_name
        self._tools = tools or (
            lambda: []
        )  # สกิลที่ AI เลือกได้ ณ ตอนส่ง (SkillsController.tool_catalog)
        from aipc.chat import client
        from aipc.chat import store as chat_store

        self._active = active
        self._target = target or client.Target.from_env()
        self._store = store or chat_store.ChatStore()
        self._conv = chat_store.new_conversation()
        self._file: tuple[str, str] | None = None  # (ชื่อไฟล์, ข้อความ) ที่แนบให้คำถามถัดไป (ฟีเจอร์ข้อ 4)
        self._temporary = False
        self._status = "down" if active else "off"
        self._lost_at = None  # เวลาที่ AI ซึ่งเคยพร้อมหยุดตอบ (None = ยังไม่เคยพร้อม หรือพร้อมอยู่)
        self._busy, self._stream_text, self._stream = False, "", None
        self._trimmed, self._save_error = False, ""
        self._trace: dict = {}  # ระหว่างตอบ: เริ่มเมื่อไหร่ ทำไมทางนี้ (ทำไมได้คำตอบนี้ · ข้อเสนอ 2026-10-03)
        self._last_trace: list = []
        self._token.connect(self._on_token)
        self._done.connect(self._on_done)
        self._health.connect(self._on_health)
        self._timer = QTimer(self, interval=poll_ms, timeout=self.refresh)
        if active:
            self._timer.start()
            self.refresh()

    # ---------- สถานะที่ QML อ่าน ----------
    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:  # noqa: N802
        return self.STATUS_TEXT[self._status]

    @Property(bool, notify=statusChanged)
    def ready(self) -> bool:
        return self._status == "ready"

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=streamChanged)
    def streamText(self) -> str:  # noqa: N802
        return self._stream_text

    @Property(bool, notify=changed)
    def temporary(self) -> bool:
        return self._temporary

    @Property(str, notify=changed)
    def notice(self) -> str:
        parts = []
        if self._temporary:
            parts.append("แชทชั่วคราว: ไม่บันทึกประวัติ")
        if self._trimmed:
            parts.append("บทสนทนายาวแล้ว AI เห็นเฉพาะข้อความล่าสุด")
        if self._save_error:
            parts.append(self._save_error)
        return " · ".join(parts)

    @Property("QVariantList", notify=changed)
    def history(self) -> list:
        try:
            return self._store.list()
        except OSError:
            return []

    # ---------- สถานะ AI ----------
    @Slot()
    def refresh(self) -> None:
        if not self._active or self._busy:
            return
        import threading

        from aipc.chat import client

        target = self._target
        threading.Thread(
            target=lambda: self._health.emit(client.health(target)), daemon=True
        ).start()

    @Slot(str)
    def _on_health(self, status: str) -> None:
        import time

        if status == "ready":
            self._lost_at = None
        elif self._status == "ready" or self._lost_at is not None:
            now = time.monotonic()
            self._lost_at = self._lost_at if self._lost_at is not None else now
            if now - self._lost_at < self.RESTART_GRACE_S:
                status = "restarting"
        if status != self._status:
            self._status = status
            self.statusChanged.emit()
            # หลังตั้งสถานะ: สกิลที่ต้องใช้ AI (สรุป แปล ...) นับว่ามีเมื่อ chat.ready · อุ่นก่อนตั้ง = รายการสกิลไม่ครบ
            # ส่วนต้นไม่ตรงกับคำขอจริง แคชใช้ไม่ได้ (Pi 5 2026-09-30: อุ่น 603 token
            # แต่ข้อความแรกยังอ่านใหม่ 916 token 45 วิ)
            if status == "ready":
                self._warm_up()

    def _cloud_ok(self) -> bool:
        """มี Claude ในบัญชีนี้ และผู้ใช้เปิดสวิตช์ไว้."""
        return self._cloud is not None and bool(self._claude_on())

    @Slot()
    def claudeSwitched(self) -> None:  # noqa: N802
        """เปิด/ปิด Claude → รายการเครื่องมือและ system prompt เปลี่ยน → อุ่นแคชใหม่ให้ข้อความถัดไปไม่ต้องรอ."""
        if self._status == "ready":
            self._warm_up()

    def _system(self, tools: list) -> str:
        """system prompt ชุดเดียวกับตัววัด (catalog.system_prompt) · มีวันที่ของวันนี้ · ส่งต่อ Claude ได้ถ้ามี."""
        from datetime import date

        from aipc.skills import catalog

        base = catalog.system_prompt(date.today(), cloud=self._cloud_ok(),
                                     model=self._model_name, forge=self._forge and self._cloud_ok())  # fmt: skip
        return base + (self.TOOLS_HINT if tools else "")

    def _all_tools(self, text: str = "") -> list:
        """ask-cloud (ถ้ามี Claude) ไว้หน้าสุด + สกิล · ลำดับคงที่ แคชจึงใช้ได้
        · text = ข้อความที่ใช้เลือกสกิล (0018)."""
        from aipc.skills import catalog

        cloud = catalog.tools([], set(), cloud=True) if self._cloud_ok() else []
        try:
            skills = self._tools(text)
        except TypeError:  # ตัวให้รายการแบบเก่าที่ไม่รับข้อความ
            skills = self._tools()
        return cloud + list(skills)

    def _warm_up(self) -> None:
        """AI เพิ่งพร้อม (login ใหม่ / AI เริ่มใหม่) → อ่านรายการสกิลไว้ในแคชทันที ข้อความแรกไม่ต้องรอ ~1 นาที.

        ใช้ system prompt + รายการสกิลชุดเดียวกับ send() ทุกตัวอักษร (ส่วนต้นของคำขอต้องตรงกันแคชจึงใช้ได้)
        ผู้ใช้พิมพ์ระหว่างอุ่น = คำขอรอคิวต่อจากการอุ่น (ไม่ช้ากว่าไม่อุ่น)
        """
        import threading

        from aipc.chat import client

        tools = self._all_tools()
        args = (self._target, self._system(tools), tools)
        threading.Thread(target=client.warm, args=args, daemon=True).start()

    # ---------- คำสั่งจาก QML ----------
    @Slot(str, str, result=bool)
    @Slot(str, str, bool, result=bool)
    def send(self, text: str, prompt: str = "", use_tools: bool = True) -> bool:
        if self._busy or not text.strip() or self._status != "ready":
            return False
        import threading

        from aipc.chat import client

        if self._file is not None and not prompt:
            # ถามเกี่ยวกับไฟล์: ส่งส่วนของไฟล์ที่เกี่ยวข้อง + คำถาม · ไม่มีเครื่องมือ · ไม่ส่งต่อ Claude (_on_done)
            from aipc import files_qa

            content = files_qa.build_message(self._file[0], self._file[1], text)
            self._conv["messages"].append({"role": "user", "content": content, "shown": text,
                                           "file": self._file[0]})  # fmt: skip
            use_tools = False
        else:
            self._conv["messages"].append({"role": "user", "content": text})
        # คุยทั่วไป = ให้ AI เลือกสกิลได้ · สกิลที่ถูกเลือกแล้ว (มี prompt) = ไม่ส่งเครื่องมือ จึงไม่วนเลือกซ้ำ
        tools = self._all_tools(text) if (use_tools and not prompt) else []
        if self._conv["messages"][-1].get("file"):
            why = (f"ถามเกี่ยวกับไฟล์ “{self._file[0]}” · ตอบในเครื่องเท่านั้น "
                   "(เนื้อหาไฟล์ห้ามออกนอกเครื่อง)")  # fmt: skip
        elif prompt:
            why = "ทำตามสกิลที่เลือกไว้ (งานภาษา เช่น แปล สรุป)"
        else:
            why = "ไม่ตรงสกิลไหน จึงให้ AI ในเครื่องตอบ" + (
                f" · เลือกใช้สกิลเองได้ {len(tools)} ตัว แต่เลือกตอบเอง" if tools else ""
            )
        self._trace = {"t0": time.monotonic(), "why": why}
        if prompt:  # สกิล (เช่น แปล): งานเดียวจบ ไม่ต้องใช้บทสนทนาก่อนหน้า
            messages, trimmed = client.fit_context(prompt, self._conv["messages"][-1:])
        else:
            messages, trimmed = client.fit_context(self._system(tools), self._conv["messages"])
        self._trimmed = trimmed and not prompt
        self._busy, self._stream_text = True, ""
        stream = self._stream = client.Stream(self._target, messages, tools=tools)
        self.changed.emit()
        self.streamChanged.emit()
        threading.Thread(
            target=lambda: self._done.emit(stream.run(self._token.emit)), daemon=True
        ).start()
        return True

    @Slot()
    def stop(self) -> None:
        if self._stream is not None:
            self._stream.abort()

    @Slot(str)
    def copyText(self, text: str) -> None:  # noqa: N802
        """คัดลอกคำตอบไปคลิปบอร์ด (เอาจดหมายที่ร่างไปใช้ต่อ) · อยู่ในเครื่อง ไม่ส่งไปไหน."""
        from PySide6.QtGui import QGuiApplication

        board = QGuiApplication.clipboard()
        if board is not None:
            board.setText(text)

    @Slot(str)
    def _on_token(self, token: str) -> None:
        self._stream_text += token
        self.streamChanged.emit()

    @Slot(object)
    def _on_done(self, reply) -> None:
        self._busy, self._stream = False, None
        from aipc.skills import catalog

        with_file = bool(self._conv["messages"] and self._conv["messages"][-1].get("file"))
        if (
            self._cloud_ok()
            and not with_file  # คำถามเกี่ยวกับไฟล์ = เนื้อหาไฟล์อยู่ในข้อความ ห้ามส่งออกนอกเครื่อง
            and not reply.reason
            and not getattr(reply, "cloud", False)
        ):
            from aipc.cloud.ask import local_gave_up

            # AI ในเครื่องเลือกส่งต่อเอง หรือตอบว่าไม่รู้ = ถามพี่ใหญ่ (การ์ด 0016)
            if reply.tool_call == catalog.ASK_CLOUD:
                self._ask_cloud("AI ในเครื่องเลือกส่งต่อ: ต้องใช้ข้อมูลสด หรือยากเกินกว่า AI ในเครื่อง")
                return
            if not reply.tool_call and local_gave_up(reply.text):
                self._ask_cloud("AI ในเครื่องตอบว่าไม่รู้ จึงถาม Claude แทน")
                return
        if reply.tool_call and not reply.reason:
            # AI เลือกสกิล: เอาข้อความของผู้ใช้ออกจากบทสนทนา (ทางของสกิลจะส่งข้อความนี้เองอีกครั้ง) · ไม่บันทึก
            text = self._conv["messages"].pop()["content"]
            self._stream_text = ""
            self.changed.emit()
            self.streamChanged.emit()
            self.skillRequested.emit(reply.tool_call, text)
            self.refresh()
            return
        note = self.NOTE.get(reply.reason, reply.detail if reply.reason else "")
        if getattr(reply, "cloud", False):
            note = self.CLOUD_NOTE
        if reply.text:
            self._conv["messages"].append({"role": "assistant", "content": reply.text})
        if not self._temporary:
            try:
                self._store.save(self._conv)
                self._save_error = ""
            except OSError as e:  # บันทึกไม่ได้ = บอก ไม่หายเงียบ (H2)
                self._save_error = f"บันทึกประวัติไม่สำเร็จ ({e.strerror or e})"
        self._stream_text = ""
        self._last_trace = self._explain(reply)
        self.changed.emit()
        self.streamChanged.emit()
        self.finished.emit(reply.text, note)
        if reply.reason == "crashed":
            self._on_health("down")
        self.refresh()

    CLOUD_NOTE = "ตอบโดย Claude (cloud) · ค้นเว็บได้ · คำถามนี้ถูกส่งออกนอกเครื่อง"

    @Property("QVariantList", notify=changed)
    def lastTrace(self) -> list:  # noqa: N802
        """ทำไมได้คำตอบล่าสุด: [{k, v}] · หน้าจอเก็บไว้กับฟองคำตอบตอน finished."""
        return self._last_trace

    def _explain(self, reply) -> list:
        """ใครตอบ · ทำไมทางนี้ · ข้อมูลออกนอกเครื่องไหม · ใช้เวลาเท่าไหร่ (ข้อเสนอ 2026-10-03).

        สร้างจากสิ่งที่เกิดจริงในรอบนี้ ไม่ใช่ให้ AI อธิบายตัวเอง (AI เล่าเหตุผลของตัวเองผิดได้)
        """
        t = self._trace
        cloud = t.get("cloud")
        if cloud:
            who = "Claude (cloud)" if getattr(reply, "cloud", False) else "Claude (ถามไม่สำเร็จ)"
            why = f"{t.get('why', '')} → {cloud['why']}"
            ctx = f" + บทสนทนาล่าสุด {cloud['turns']} ข้อความ" if cloud["turns"] else ""
            out = (f"ส่งคำถาม{ctx} ({cloud['chars']} ตัวอักษร) ไป Claude · "
                   "ข้อความที่ส่งจริงดูได้ที่ ตั้งค่า › สิ่งที่ส่งออกนอกเครื่อง")  # fmt: skip
        else:
            who = "AI ในเครื่อง" + (f" ({self._model_name})" if self._model_name else "")
            why = t.get("why", "")
            out = "ไม่มี · ตอบในเครื่องทั้งหมด"
        rows = [{"k": "ใครตอบ", "v": who}, {"k": "ทำไมทางนี้", "v": why},
                {"k": "ข้อมูลออกนอกเครื่อง", "v": out}]  # fmt: skip
        if "t0" in t:
            took = f"{time.monotonic() - t['t0']:.1f} วินาที"
            n, tps = reply.timings.get("predicted_n"), reply.timings.get("predicted_per_second")
            if not cloud and n and tps:
                took += f" · {n} โทเคน ({tps:.1f} โทเคน/วิ)"
            rows.append({"k": "ใช้เวลา", "v": took})
        if self._trimmed:
            rows.append({"k": "หมายเหตุ", "v": "บทสนทนายาวเกิน จึงตัดข้อความเก่าออกก่อนส่งให้ AI"})
        return rows

    def _ask_cloud(self, why: str) -> None:
        """AI ในเครื่องเลือกส่งต่อ (ข้อมูลสด / ยาก / ไม่แน่ใจ) → ถาม Claude ในเธรดแยก · ระหว่างรอบอกตรง ๆ."""
        import threading

        from aipc.chat import client
        from aipc.cloud.ask import CONTEXT_TURNS, build_input

        question = self._conv["messages"][-1]["content"]
        history = self._conv["messages"][:-1]
        turns = min(CONTEXT_TURNS, sum(m.get("role") in ("user", "assistant") for m in history))
        self._trace.setdefault("t0", time.monotonic())
        chars = len(build_input(question, history))
        self._trace["cloud"] = {"why": why, "turns": turns, "chars": chars}
        self._busy = True
        self._stream_text = "กำลังถาม Claude (cloud) · ต้องใช้ข้อมูลสดหรือยากเกินกว่า AI ในเครื่อง…"
        self.changed.emit()
        self.streamChanged.emit()

        def work():
            c = self._cloud(question, history)
            reply = client.Reply(text=c.text if c.ok else "", reason="" if c.ok else "error",
                                 detail="" if c.ok else c.error)  # fmt: skip
            reply.cloud = c.ok  # type: ignore[attr-defined]
            self._done.emit(reply)

        threading.Thread(target=work, daemon=True).start()

    # ---------- ถามเกี่ยวกับไฟล์ของฉัน (ฟีเจอร์ข้อ 4) ----------
    @Property(str, notify=changed)
    def attachedFile(self) -> str:  # noqa: N802
        return self._file[0] if self._file else ""

    @Slot(str, result=str)
    def attachFile(self, path: str) -> str:  # noqa: N802
        """แนบไฟล์ให้คำถามถัดไป ๆ · คืนข้อความผิดพลาด ("" = สำเร็จ) · เนื้อหาไฟล์อยู่ในเครื่องเท่านั้น."""
        from aipc import files_qa

        try:
            text = files_qa.extract(Path(path))
        except files_qa.Unsupported as e:
            return str(e)
        self._file = (Path(path).name, text)
        self.changed.emit()
        return ""

    @Slot()
    def detachFile(self) -> None:  # noqa: N802
        self._file = None
        self.changed.emit()

    @Slot(str, result=bool)
    def askCloudFor(self, text: str) -> bool:  # noqa: N802
        """สร้างสกิลไม่สำเร็จ → ให้ Claude ตอบคำขอนี้แทน (การ์ด 0017 ข้อ 4.5)
        · ไม่มี Claude / กำลังตอบ = False."""
        if not self._cloud_ok() or self._busy or not text.strip():
            return False
        self._conv["messages"].append({"role": "user", "content": text})
        self._trace = {"t0": time.monotonic(), "why": "ขอให้ Claude สร้างสกิลแต่ไม่สำเร็จ"}
        self._ask_cloud("จึงให้ Claude ตอบคำขอนี้แทน")
        return True

    @Slot(bool)
    def newChat(self, temporary: bool) -> None:  # noqa: N802
        from aipc.chat import store as chat_store

        self.stop()
        self._conv, self._temporary, self._trimmed = chat_store.new_conversation(), temporary, False
        self.changed.emit()

    @Slot(str, result="QVariantList")
    def openChat(self, cid: str) -> list:  # noqa: N802
        conv = self._store.load(cid)
        if conv is None or self._busy:
            return []
        self._conv, self._temporary, self._trimmed = conv, False, False
        self.changed.emit()
        return conv["messages"]

    @Slot(str)
    def deleteChat(self, cid: str) -> None:  # noqa: N802
        self._store.delete(cid)
        self.changed.emit()

    @Slot(result=int)
    def deleteAll(self) -> int:  # noqa: N802
        n = self._store.delete_all()
        self.newChat(False)
        return n

    def shutdown(self) -> None:
        self._timer.stop()
        self.stop()
