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
        self._network: bool | None = None
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

    def __init__(self, dev_mode: bool, demo_scan: str | None = None,
                 greeter_session: list[str] | None = None, connect=None):  # fmt: skip
        super().__init__()
        self._dev = dev_mode
        # โหมด greeter (การ์ด 0003): greetd รันหน้านี้ก่อนมีใครเข้าเครื่อง · PAM ของ OS ตรวจรหัสผ่าน
        self._session = greeter_session
        self._connect = connect
        self._state = demo_scan if demo_scan in self.STATES else "unavailable"
        self._demo = demo_scan in self.STATES

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

    def __init__(self, real: bool = False, dev: bool = False, runner=None):
        super().__init__()
        self._real, self._dev = real, dev
        self._run = runner or run_accounts_helper
        self._busy = False
        self._result.connect(self._on_result)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    def _submit(self, request: dict) -> bool:
        if self._busy:
            return False
        if not self._real:
            if self._dev:
                msg = "จำลอง (โหมดพัฒนา) · ไม่ได้สร้างหรือเปลี่ยนบัญชีจริง"
                self.finished.emit({"ok": True, "simulated": True, "message": msg})
            else:
                self.finished.emit(
                    {"ok": False, "message": "สมัครและกู้คืนได้เฉพาะหน้า Login จริงของเครื่อง"}
                )
            return True
        import threading

        self._busy = True
        self.changed.emit()
        threading.Thread(target=lambda: self._result.emit(self._run(request)), daemon=True).start()
        return True

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
        "llm": "โมเดลภาษาในเครื่อง (ยังไม่ได้เลือก — รอผลวัดบน Pi 5, ADR-007)",
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

    def __init__(self, executor=None, root: Path = Path("/"), reminders_path=None, clock=None,
                 run_timer: bool = True, llm_ready=None):  # fmt: skip
        super().__init__()
        # "llm" พร้อมเมื่อ llama-server ของผู้ใช้ตอบได้จริง (ChatController) · ไม่ใช่ค่าคงที่ (H5)
        self._llm_ready = llm_ready or (lambda: False)
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
        self._save_failed = False
        if self._missed:
            for r in self._missed:
                r.fired = True  # รายงานครั้งเดียวว่าพลาด ไม่เตือนซ้ำเมื่อถึงรอบตรวจ
            try:
                self._store.save(now)
            except (OSError, reminders.Unreadable):
                # พบ 2026-09-28: บันทึกล้มตรงนี้เคยทำให้หน้าจอเปิดไม่ขึ้น → ล่มซ้ำจนเซสชันจบ
                self._save_failed = True
        self._timer = QTimer(self, interval=self.TICK_MS, timeout=self.tick)
        if run_timer:  # หน้า greeter (ยังไม่มีใครเข้าเครื่อง) ไม่มีนัดของใครให้เตือน และไม่เขียนไฟล์
            self._timer.start()

    def _badge(self, skill, reason: str) -> dict:
        return {"name": skill.name, "reason": reason, "worker": self.WORKER_LABEL[skill.worker]}

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
                    lines.append(f"✗ {i}. {s.plan.summary} · {out.message}")
                    if i < total:
                        lines.append(f"ขั้นที่เหลือ {total - i} ขั้นไม่ได้ทำ")
                    card.update(title=f"หยุดที่ขั้น {i}: {out.message}", lines=lines,
                                chips=[{"text": "ไม่สำเร็จ", "kind": "danger"}])  # fmt: skip
                    return card
                lines.append(f"{'จำลอง' if out.simulated else '✓'} {i}. {s.plan.summary}")
        chip = {"text": "จำลอง", "kind": "warn"} if simulated else {"text": "ทำแล้ว", "kind": "ok"}
        title = f"ทำครบ {total} ขั้นแล้ว" + (" (จำลอง)" if simulated else "")
        card.update(title=title, lines=lines, confirmToken="", chips=[chip])
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

        r = router.route(text, self._skills, self.available())
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

    SYSTEM = "คุณคือผู้ช่วย AI ภาษาไทยที่ทำงานในเครื่องของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ถูกต้อง ถ้าไม่รู้ให้บอกว่าไม่รู้"
    STATUS_TEXT = {"ready": "โมเดล: พร้อม · ในเครื่อง", "loading": "โมเดล: กำลังโหลด…",
                   "down": "โมเดล: ไม่พร้อม", "off": "โมเดล: ไม่ใช้ในหน้านี้"}  # fmt: skip
    NOTE = {"stopped": "หยุดแล้ว", "crashed": "ตอบไม่จบ: AI หยุดทำงาน · ระบบกำลังเปิด AI ใหม่เอง"}

    changed = Signal()
    streamChanged = Signal()  # noqa: N815
    statusChanged = Signal()  # noqa: N815
    finished = Signal(str, str)  # ข้อความ, หมายเหตุ ("" = จบปกติ)
    _token = Signal(str)
    _done = Signal(object)
    _health = Signal(str)

    def __init__(self, active: bool = True, target=None, store=None, poll_ms: int = 5000):
        super().__init__()
        from aipc.chat import client
        from aipc.chat import store as chat_store

        self._active = active
        self._target = target or client.Target.from_env()
        self._store = store or chat_store.ChatStore()
        self._conv = chat_store.new_conversation()
        self._temporary = False
        self._status = "down" if active else "off"
        self._busy, self._stream_text, self._stream = False, "", None
        self._trimmed, self._save_error = False, ""
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

    def _on_health(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

    # ---------- คำสั่งจาก QML ----------
    @Slot(str, str, result=bool)
    def send(self, text: str, prompt: str = "") -> bool:
        if self._busy or not text.strip() or self._status != "ready":
            return False
        import threading

        from aipc.chat import client

        self._conv["messages"].append({"role": "user", "content": text})
        if prompt:  # สกิล (เช่น แปล): งานเดียวจบ ไม่ต้องใช้บทสนทนาก่อนหน้า
            messages, trimmed = client.fit_context(prompt, self._conv["messages"][-1:])
        else:
            messages, trimmed = client.fit_context(self.SYSTEM, self._conv["messages"])
        self._trimmed = trimmed and not prompt
        self._busy, self._stream_text = True, ""
        stream = self._stream = client.Stream(self._target, messages)
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

    def _on_token(self, token: str) -> None:
        self._stream_text += token
        self.streamChanged.emit()

    def _on_done(self, reply) -> None:
        self._busy, self._stream = False, None
        note = self.NOTE.get(reply.reason, reply.detail if reply.reason else "")
        if reply.text:
            self._conv["messages"].append({"role": "assistant", "content": reply.text})
        if not self._temporary:
            try:
                self._store.save(self._conv)
                self._save_error = ""
            except OSError as e:  # บันทึกไม่ได้ = บอก ไม่หายเงียบ (H2)
                self._save_error = f"บันทึกประวัติไม่สำเร็จ ({e.strerror or e})"
        self._stream_text = ""
        self.changed.emit()
        self.streamChanged.emit()
        self.finished.emit(reply.text, note)
        if reply.reason == "crashed":
            self._on_health("down")
        self.refresh()

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
