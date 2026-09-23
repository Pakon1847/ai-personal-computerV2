"""วัตถุ Python ที่หน้าจอ QML เรียกใช้.

หลักการ: QML มีหน้าที่วาดเท่านั้น ส่วนการตัดสินใจ ตัวเลข และการตรวจข้อมูลอยู่ใน Python
ซึ่งเทสต์ได้ · QML เห็นวัตถุเหล่านี้เป็นชื่อ เช่น uiSettings.theme หรือ signup.checkUsername(...)

แต่ละ @Property คือค่าที่ QML อ่านได้ และเมื่อ Python ปล่อย signal `changed`
ทุกจุดบนจอที่ใช้ค่านั้นจะวาดใหม่เอง (นี่คือ binding ของ QML)
"""

from __future__ import annotations

import getpass
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from aipc.accounts import validation
from aipc.bench import machine
from aipc.doctor import hardware
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

    @Slot(float)
    def setFontScale(self, scale: float) -> None:  # noqa: N802
        if scale in settings.FONT_SCALES and scale != self._prefs.font_scale:
            self._prefs.font_scale = scale
            settings.save(self._prefs, self._path)
            self.changed.emit()


class SystemStatus(QObject):
    """ค่าจริงจากเครื่องสำหรับแถบสถานะและหน้าสุขภาพเครื่อง.

    อ่านจาก aipc.doctor ตัวเดียวกับที่ใช้ตรวจฮาร์ดแวร์ ค่าที่อ่านไม่ได้แสดงว่า "—" ไม่เดา
    อัปเดตนาฬิกาทุก 1 วิ และตรวจเครื่องทุก 10 วิ (การตรวจเรียก vcgencmd จึงไม่ถี่กว่านี้)
    """

    changed = Signal()
    healthChanged = Signal()  # noqa: N815

    def __init__(self, root: Path = Path("/")):
        super().__init__()
        self._root = root
        self._now = datetime.now()
        self._checks: list[dict] = []
        self._temp: float | None = None
        self._free_gb: float | None = None
        self._camera = False
        self._clock = QTimer(self, interval=1000, timeout=self._tick)
        self._clock.start()
        self._probe = QTimer(self, interval=10_000, timeout=self.refresh)
        self._probe.start()
        self.refresh()

    def _tick(self) -> None:
        self._now = datetime.now()
        self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        self._temp = machine.cpu_temp_c(self._root)
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

    def __init__(self, root: Path | None = None):
        super().__init__()
        self._root = root or Path.home()
        self._rel = ""
        self._entries: list[dict] = []
        self._error = ""
        self._load()

    def _load(self) -> None:
        try:
            self._entries = [e.to_dict() for e in files.list_dir(self._root, self._rel)]
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

    @Slot()
    def up(self) -> None:
        parent = str(Path(self._rel).parent)
        self._rel = "" if parent == "." else parent
        self._load()


class LoginController(QObject):
    """สถานะหน้า Login.

    ระบบจดจำใบหน้า (visiond) กับตัวเชื่อม greetd/PAM ยังไม่มี (เฟส 1–2)
    จึงไม่แกล้งทำเป็นสแกนหน้าได้: scanState = "unavailable" เว้นแต่สั่งโหมดสาธิต
    โหมดสาธิต (--demo-scan) มีไว้ดูหน้าตาแต่ละสถานะตามบอร์ดออกแบบ และจะขึ้นแถบเตือนเสมอ
    """

    changed = Signal()
    STATES = ("unavailable", "scanning", "found", "unknown", "manual")

    def __init__(self, dev_mode: bool, demo_scan: str | None = None):
        super().__init__()
        self._dev = dev_mode
        self._state = demo_scan if demo_scan in self.STATES else "unavailable"
        self._demo = demo_scan in self.STATES

    @Property(str, notify=changed)
    def scanState(self) -> str:  # noqa: N802
        return self._state

    @Property(bool, notify=changed)
    def demo(self) -> bool:
        return self._demo

    @Property(str, notify=changed)
    def foundName(self) -> str:  # noqa: N802
        return "Pakon" if self._demo else ""

    @Slot(str)
    def setScanState(self, state: str) -> None:  # noqa: N802
        if state in self.STATES:
            self._state = state
            self.changed.emit()

    @Slot(str, str, result=str)
    def signIn(self, username: str, password: str) -> str:  # noqa: N802
        """คืน "" เมื่อเข้าได้ หรือข้อความบอกเหตุผลที่เข้าไม่ได้.

        ยังไม่มีการตรวจรหัสผ่านจริง: โหมดพัฒนาให้ผ่านเพื่อเดินหน้าจอต่อ (มีแถบเตือน)
        นอกโหมดพัฒนาต้องปฏิเสธเสมอ ห้ามให้ผ่านโดยไม่ได้ตรวจ
        """
        if self._dev:
            return ""
        return "ยังเข้าสู่ระบบจริงไม่ได้: ตัวเชื่อม greetd/PAM อยู่ในเฟส 1"


class SignupController(QObject):
    """กฎตรวจฟอร์มสมัคร · เรียกกฎชุดเดียวกับที่ตัวสร้างบัญชีจริงจะใช้ (aipc.accounts.validation)."""

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

    @Slot(result=str)
    def newRecoveryCode(self) -> str:  # noqa: N802
        return validation.new_recovery_code()


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
        "llm": "โมเดลภาษาในเครื่อง (ยังไม่ได้เลือก — รอผลวัดบน Pi 5, ADR-007)",
        "stt": "ระบบถอดเสียงภาษาไทย (ADR-005)",
        "vlm": "โมเดลดูภาพ (ROADMAP 0.11)",
        "camera": "สิทธิ์ใช้กล้องสำหรับสกิล (ADR-015)",
    }
    LEVEL = {"ok": "ok", "warn": "warn", "danger": "danger", "neutral": "neutral"}
    TICK_MS = 30_000  # การ์ด 0001 หัวข้อ 7: ตรวจนัดทุก 30 วินาที

    reminderDue = Signal("QVariantMap")  # noqa: N815
    remindersChanged = Signal()  # noqa: N815

    def __init__(self, executor=None, root: Path = Path("/"), reminders_path=None, clock=None):
        super().__init__()
        from aipc.skills import actions, manifest, reminders

        self._skills = manifest.load_builtin()
        self._exec = executor or actions.Executor()
        self._root = root
        self._pending: dict[str, object] = {}
        self._counter = 0
        self._now = clock or (lambda: datetime.now().astimezone())
        self._store = reminders.ReminderStore(reminders_path)
        now = self._now()
        broken = self._store.broken
        self._missed = [] if broken else reminders.missed_since_last_session(self._store, now)
        self._clock_back = reminders.clock_went_back(self._store, now)
        if self._missed:
            for r in self._missed:
                r.fired = True  # รายงานครั้งเดียวว่าพลาด ไม่เตือนซ้ำเมื่อถึงรอบตรวจ
            self._store.save(now)
        self._timer = QTimer(self, interval=self.TICK_MS, timeout=self.tick)
        self._timer.start()

    def _badge(self, skill, reason: str) -> dict:
        return {"name": skill.name, "reason": reason, "worker": self.WORKER_LABEL[skill.worker]}

    @Property("QVariantList", constant=True)
    def skills(self) -> list:
        out = []
        for s in self._skills:
            missing = [n for n in s.needs if n not in self.AVAILABLE]
            out.append({
                "id": s.id, "name": s.name, "description": s.description,
                "worker": self.WORKER_LABEL[s.worker], "permissions": s.permission_labels(),
                "ready": not missing, "missing": [self.NEED_LABEL[n] for n in missing],
            })  # fmt: skip
        return out

    @Property(bool, constant=True)
    def simulated(self) -> bool:
        return self._exec.dry_run

    # ---------- นัดหมาย (การ์ดออกแบบ 0001) ----------

    @staticmethod
    def _when_text(dt) -> str:
        return f"{thaidate.short_date(dt)} {dt.year + thaidate.BE_OFFSET} · {dt:%H:%M} น."

    def _reminder_dict(self, r) -> dict:
        return {"id": r.id, "what": r.what, "when": self._when_text(r.when)}

    @Property("QVariantList", notify=remindersChanged)
    def upcoming(self) -> list:
        return [self._reminder_dict(r) for r in self._store.upcoming(self._now())]

    @Property("QVariantList", constant=True)
    def missed(self) -> list:
        return [self._reminder_dict(r) for r in self._missed]

    @Property(str, constant=True)
    def reminderWarning(self) -> str:  # noqa: N802
        if self._store.broken:
            return "อ่านไฟล์นัดหมายไม่ได้ (ไฟล์และสำเนาเสียทั้งคู่) · ยังไม่ได้เขียนทับ รอคุณตัดสิน"
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
        if t.due:
            self.remindersChanged.emit()

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
        if w.at is None or not w.confident:
            card["title"] = "ยังจดนัดนี้ไม่ได้"
            card["lines"] = [w.problem, "ลองระบุให้ชัด เช่น “พรุ่งนี้ 14:00 ส่งรายงาน”"]
            return card
        self._counter += 1
        token = f"r{self._counter}"
        self._pending[token] = reminders.Reminder(w.what, reminders.aware(w.at))
        card["title"] = f"บันทึกนัด “{w.what}” ใช่ไหม"
        card["chips"] = [{"text": self._when_text(w.at), "kind": "accent"}]
        card["lines"] = [f"ตีความเอง: {a}" for a in w.assumptions]
        card["lines"].append("วันที่คำนวณด้วยโค้ด ไม่ใช่ให้ AI เดา · ไม่ถูกให้กด “ไม่ใช่” แล้วพิมพ์ใหม่")
        card["confirmToken"] = token
        return card

    def _run_plan(self, plan) -> dict:
        out = self._exec.execute(plan)
        if out.simulated:
            title = plan.summary + " (จำลอง)"
        else:
            title = plan.summary if out.ok else out.message
        return {
            "title": title,
            "chips": [{"text": "จำลอง" if out.simulated else ("ทำแล้ว" if out.ok else "ไม่สำเร็จ"),
                       "kind": "warn" if out.simulated else ("ok" if out.ok else "danger")}],
            "lines": [out.message] if out.simulated else [],
            "page": out.page,
        }  # fmt: skip

    @Slot(str, result="QVariantMap")
    def handle(self, text: str) -> dict:
        from aipc.skills import machine, router

        r = router.route(text, self._skills, set(self.AVAILABLE))
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
            risk = {"low": "ความเสี่ยงต่ำ", "medium": "ความเสี่ยงกลาง", "high": "ความเสี่ยงสูง"}[
                r.command.plan.spec.risk
            ]
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
        elif r.kind in ("needs", "skill"):
            card["badge"] = self._badge(r.skill, r.reason)
            card["kind"] = "needs"
            card["title"] = f"สกิล “{r.skill.name}” ยังใช้ไม่ได้"
            card["lines"] = ["ต้องมีก่อน: " + self.NEED_LABEL[n] for n in (r.missing or r.skill.needs)]
        else:
            card["title"] = "ยังตอบไม่ได้: ยังไม่ได้เชื่อมต่อโมเดลในเครื่อง"
            card["lines"] = [
                "ข้อความนี้ไม่ได้ถูกส่งไปที่ไหน · ลองสั่งงานเครื่อง เช่น “เปิดยูทูบ” หรือถาม “ทำไมเครื่องช้า”"
            ]
        return card

    @Slot(str, bool, result="QVariantMap")
    def confirm(self, token: str, yes: bool) -> dict:
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
