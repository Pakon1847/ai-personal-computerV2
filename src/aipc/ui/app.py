"""เปิดหน้าต่างของระบบ: โหลดฟอนต์ ต่อ backend กับ QML แล้วแสดง Main.qml."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

from aipc.ui.backend import (
    FilesBrowser,
    LoginController,
    SessionController,
    SignupController,
    SkillsController,
    SystemStatus,
    UiSettings,
)
from aipc.ui.face import FaceController

HERE = Path(__file__).resolve().parent
QML_DIR = HERE / "qml"
FONT_DIR = HERE / "fonts"
SCREENS = ("login", "signup", "shell")
PAGES = ("workspace", "files", "skills", "privacy", "health", "settings")


@dataclass
class Options:
    screen: str = "login"
    page: str = "workspace"
    theme: str | None = None
    dev: bool = False
    demo_scan: str | None = None
    signup_step: int = 0  # เปิดหน้าสมัครที่ขั้นนี้เลย (ใช้ถ่ายภาพ/ทดสอบ)
    software: bool = False  # วาดด้วย CPU (ใช้ตอนเทสต์ และเครื่องที่ไม่มี GPU)
    settings_path: Path | None = None
    fullscreen: bool = False  # เต็มจอบน Pi · ออกได้ด้วย Ctrl+Alt+Q เสมอ
    greeter_session: list[str] | None = None  # โหมด greeter: คำสั่งเซสชันที่ greetd เริ่มหลังเข้าได้
    session: bool = False  # เซสชันจริงหลัง login (การ์ด 0004): เริ่มที่ Shell · ออก = จบเซสชัน


def load_fonts() -> list[str]:
    """ฟอนต์มากับแอป (ไลเซนส์ OFL, ดู fonts/OFL.txt) ไม่พึ่งฟอนต์ที่ OS มี
    หน้าตาจึงเหมือนกันทุกเครื่อง รวม Pi ที่เพิ่งลง OS."""
    families = []
    for f in sorted(FONT_DIR.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(f))
        families += QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    return sorted(set(families))


def build(opts: Options, argv: list[str] | None = None):
    """สร้างแอปและ engine · คืน (app, engine, warnings) เพื่อให้เทสต์ตรวจ warning ของ QML ได้."""
    if sys.platform == "win32":
        # บนวินโดวส์ (เฉพาะเครื่องพัฒนา) Python จาก Microsoft Store ค้น DLL แบบจำกัด
        # plugin ของ QML จึงหา DLL ของ Qt ไม่เจอ ต้องบอกโฟลเดอร์ตรง ๆ · บน Pi (Linux) ไม่ต้องทำ
        import PySide6

        os.add_dll_directory(str(Path(PySide6.__file__).parent))
    if opts.software:
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app = QGuiApplication.instance() or QGuiApplication(argv or ["aipc"])
    load_fonts()

    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.addImportPath(str(QML_DIR))

    # เก็บ backend ไว้บน engine ด้วย ไม่งั้น Python จะเก็บกวาดทิ้งขณะหน้าจอยังใช้อยู่
    # เซสชันจริงกับ greeter: ไม่มีโหมดพัฒนา/สาธิต · เซสชันจริงเริ่มที่ Shell เสมอ (login ผ่าน greetd แล้ว)
    real = bool(opts.greeter_session) or opts.session
    engine._backends = {
        "uiSettings": UiSettings(opts.settings_path, opts.theme),
        "system": SystemStatus(),
        # โหมด greeter ห้ามมีทางลัดของโหมดพัฒนาหรือสถานะสาธิตเด็ดขาด
        "login": LoginController(
            opts.dev and not real,
            None if real else opts.demo_scan,
            greeter_session=opts.greeter_session,
        ),
        "signup": SignupController(),
        "filesBrowser": FilesBrowser(),
        "skills": SkillsController(run_timer=not opts.greeter_session),
        "session": SessionController(opts.session and not opts.greeter_session),
        # หน้า Login (ผู้ใช้ _greetd) ไม่มีเจ้าของเซสชัน → ไม่เปิดระบบใบหน้า (การ์ด 0006)
        "face": FaceController(active=not opts.greeter_session),
    }
    ctx = engine.rootContext()
    for name, obj in engine._backends.items():
        ctx.setContextProperty(name, obj)
    # ภาพสดขณะลงทะเบียนใบหน้า (การ์ด 0010) · QML ใช้ image://face/<เลขภาพ>
    engine._face_provider = engine._backends["face"].image_provider()
    engine.addImageProvider("face", engine._face_provider)
    screen = "shell" if opts.session else opts.screen
    ctx.setContextProperty("startScreen", screen if screen in SCREENS else "login")
    ctx.setContextProperty("startPage", opts.page if opts.page in PAGES else "workspace")
    ctx.setContextProperty("startSignupStep", max(0, min(opts.signup_step, 5)))
    dev = (opts.dev or opts.demo_scan is not None) and not real
    ctx.setContextProperty("devMode", dev)
    ctx.setContextProperty("startFullscreen", opts.fullscreen)

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "AipcUi" / "Main.qml")))
    return app, engine, warnings


def shutdown(engine) -> None:
    """ปิดตามลำดับ: ลบ engine (และหน้าจอ QML ทั้งหมดที่เป็นลูกของมัน) ก่อน แล้วค่อยปล่อย backend.

    ถ้าปล่อยให้ Python เก็บกวาดเอง ลำดับไม่แน่นอน · บน Pi backend ถูกทำลายก่อน หน้าจอที่ยังค้าง
    อ่านค่าไม่ได้ → TypeError "... of null" หลายสิบบรรทัดทุกครั้งที่ปิด (บนวินโดวส์ไม่เกิด)
    """
    import shiboken6

    backends = getattr(engine, "_backends", {})
    if shiboken6.isValid(engine):
        shiboken6.delete(engine)
    backends.clear()


def screenshot(engine, path: Path, delay_ms: int = 600) -> None:
    """ถ่ายภาพหน้าต่างแล้วปิดแอป · ใช้ทำภาพประกอบเล่มและตรวจหน้าตาโดยไม่ต้องมีจอ."""

    def grab():
        win = engine.rootObjects()[0]
        win.grabWindow().save(str(path))
        QGuiApplication.quit()

    QTimer.singleShot(delay_ms, grab)
