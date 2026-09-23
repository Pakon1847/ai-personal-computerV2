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
