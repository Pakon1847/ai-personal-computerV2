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

from aipc import i18n
from aipc.ui.backend import (
    BackupController,
    ChatController,
    CloudUsage,
    FilesBrowser,
    LoginController,
    PresenceStatus,
    PrivacyStatus,
    SessionController,
    SignupController,
    SkillsController,
    SystemStatus,
    UiSettings,
    VoiceController,
)
from aipc.ui.face import FaceController
from aipc.ui.handsfree import BrowserController, HotkeyListener
from aipc.ui.loginface import LoginFaceController

HERE = Path(__file__).resolve().parent
QML_DIR = HERE / "qml"
FONT_DIR = HERE / "fonts"
SCREENS = ("login", "signup", "recover", "delete", "shell")
PAGES = ("workspace", "calendar", "files", "skills", "health", "settings")


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


def _cloud_client(budget=None, ledger=None):
    """ไฮบริด (การ์ด 0016): มีคำสั่ง claude ในเครื่อง = ส่งต่อได้ · ปิดได้ด้วย AIPC_CLOUD=0.

    budget (aipc.cloud.budget.Budget): ครบเพดานต่อวัน = ไม่เรียก Claude บอกผู้ใช้ตรง ๆ
    ledger (aipc.cloud.ledger.Ledger): บันทึกข้อความที่ส่งออกจริงทุกครั้ง (หน้าตั้งค่าแสดงให้ผู้ใช้ตรวจ)
    """
    import os

    from aipc.cloud import ask

    if os.environ.get("AIPC_CLOUD", "1") == "0" or ask.find_claude() is None:
        return None

    def run(question, history):
        if budget is not None and not budget.allow():
            return ask.CloudReply(False, error=budget.blocked_message())
        r = ask.ask(question, history)
        if budget is not None:
            budget.record(r.cost_usd, "ask")
        if ledger is not None:
            ledger.record("ask", ask.build_input(question, history or []), r.cost_usd, ok=r.ok)
        return r

    return run


def _skill_forge(budget=None, ledger=None):
    """สกิลอัตโนมัติ (การ์ด 0017): มีคำสั่ง claude = ให้ Claude สร้างสกิลได้.

    ปิดได้ด้วย AIPC_CLOUD=0 หรือ AIPC_FORGE=0
    """
    import os

    from aipc.cloud.ask import find_claude

    exe = find_claude()
    if exe is None or "0" in (os.environ.get("AIPC_CLOUD", "1"), os.environ.get("AIPC_FORGE", "1")):
        return None
    from aipc.skills import forge

    def run(request, **kw):  # เธรดแยก · อ่านรุ่นของ claude ตอนใช้ (ไม่ให้เปิดแอปช้าลง)
        if budget is not None and not budget.allow():
            return forge.Proposal(False, request, errors=[budget.blocked_message()])
        version = forge.run_process([exe, "--version"], "", ".", 30)[1].strip()
        p = forge.forge(request, claude=exe, model="sonnet", claude_version=version, **kw)
        if budget is not None:
            budget.record(p.cost_usd, "skill")
        if ledger is not None:
            revise = kw.get("revise")
            sent = request + (f"\nคำติ: {revise[1]}" if revise else "")
            note = "พร้อมแม่แบบคำสั่งของระบบและรายชื่อสกิลในเครื่อง · ไม่มีแชท นัด หรือไฟล์"
            if p.attempts > 1:
                note += f" · ส่ง {p.attempts} ครั้ง (แก้ตามที่ประตูตรวจตีกลับ)"
            # ok = Claude ได้ไฟล์สกิลที่ผ่านประตูตรวจ (แอปติดตั้งจากเงื่อนไขนี้) · ไม่ใช่ p.ok ที่รวมผลทดลองกับตัวคัด
            # สกิลแบบกฎ (เดิมบันทึก ok: false ทั้งที่ติดตั้งได้ · T6 2026-10-08 · การ์ด 0022 ข้อ ข)
            made = bool(p.skill_md)
            if made and not p.ok:
                note += " · ทดลองกับตัวคัดสกิลแบบกฎไม่ครบทุกประโยค (ไม่กระทบการติดตั้ง)"
            ledger.record("skill", sent, p.cost_usd, ok=made, note=note)
        return p

    return run


def _weather(ledger=None):
    """สกิลอากาศ (Open-Meteo · Pakon อนุมัติ 2026-10-02) · ทุกครั้งที่ส่งชื่อเมือง/พิกัดออก = บันทึกใน ledger."""
    from aipc.skills.weather import Weather

    if ledger is None:
        return Weather()
    return Weather(record=lambda sent: ledger.record("weather", sent))


def _holidays(ledger=None):
    """วันหยุดไทยจากปฏิทินสาธารณะของ Google (การ์ด 0033) · ค่าเริ่มต้นปิด · ทุกครั้งที่ดึง = บันทึกใน ledger."""
    from aipc.skills import gcal

    link_file, cache_file = gcal.holiday_files()
    record = (lambda sent, ok: None) if ledger is None else (
        lambda sent, ok: ledger.record("calendar", sent, ok=ok))  # fmt: skip
    return gcal.GoogleCalendar(link_file, cache_file, record=record, source="holidays",
                               future=gcal.HOLIDAY_FUTURE, stale_after=gcal.HOLIDAY_STALE,
                               sent=gcal.HOLIDAY_SENT, classify=True)  # fmt: skip


def _gcal(ledger=None):
    """ปฏิทิน Google แบบอ่านอย่างเดียว (การ์ด 0014) · ทุกครั้งที่ดึง = บันทึกใน ledger (ไม่มีลิงก์ลับในข้อความ)."""
    from aipc.skills.gcal import GoogleCalendar

    if ledger is None:
        return GoogleCalendar()
    return GoogleCalendar(record=lambda sent, ok: ledger.record("calendar", sent, ok=ok))


def _start_idle_lock(ui_settings, app):
    """ล็อกจอเมื่อไม่ได้ใช้เครื่อง แล้วออกเอง (aipc.ui.idle · ขั้น A) · เฉพาะเซสชันจริง ·
    ค่าเปลี่ยน = เริ่ม swayidle ใหม่."""
    import getpass
    import pwd

    from aipc.ui import idle

    try:
        name = (pwd.getpwnam(getpass.getuser()).pw_gecos or "").split(",")[0] or getpass.getuser()
    except (KeyError, OSError):
        name = ""
    screen = app.primaryScreen()
    size = (1920, 1080)
    if screen is not None:
        g, r = screen.geometry(), screen.devicePixelRatio()
        size = (max(640, int(g.width() * r)), max(480, int(g.height() * r)))
    lock = idle.IdleLock()
    idle.clear_orphans()

    def apply() -> None:
        presence = (
            (ui_settings.presenceLockS, ui_settings.presenceLogoutS)
            if ui_settings.presence
            else None
        )
        lock.apply(ui_settings.lockMin, ui_settings.logoutMin, name, size, presence=presence)

    apply()
    ui_settings.changed.connect(apply)  # ค่าเดิม = IdleLock ไม่ทำอะไร (ธีม/ตัวอักษรเปลี่ยนไม่กระทบ)
    app.aboutToQuit.connect(lock.stop)
    return lock


def _local_model_name() -> str:
    """ชื่อโมเดลจาก /etc/aipc/llm.conf (ให้ AI ตอบได้ว่าใช้โมเดลอะไร) · อ่านไม่ได้ = ""."""
    from pathlib import Path

    try:
        for line in Path("/etc/aipc/llm.conf").read_text(encoding="utf-8").splitlines():
            if line.startswith("MODEL="):
                return Path(line.split("=", 1)[1].strip()).stem
    except OSError:
        pass
    return ""


def _face_client(short: bool = False):
    """ตัวต่อ visiond (การ์ด 0015) · ไม่ได้ติดตั้ง = None (ใช้รหัสผ่านตามเดิม).

    short = หน้าตั้งค่า: ถามสถานะ ("enabled") รอไม่เกิน 5 วิ เพราะเรียกจากเธรดหน้าจอ
    """
    from aipc.vision import client

    if not client.available():
        return None

    def ask(req, on_progress=None):
        timeout = 5.0 if short and req.get("op") == "enabled" else 120.0
        return client.request(req, on_progress, timeout=timeout)

    return ask


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
    # หน้า Login ไม่มีเจ้าของเซสชัน → ไม่คุยกับ AI (การ์ด 0013) · เซสชัน/หน้าต่างพัฒนาใช้ llama-server ของผู้ใช้
    # AI เลือกสกิลได้ (อาจารย์ขอ · งานข้อ ④): รายการสกิลอ่านจาก SkillsController ตอนส่งทุกครั้ง
    holder: dict = {}

    def tools(text: str = "") -> list:
        return holder["skills"].tool_catalog(text) if "skills" in holder else []

    in_session = not opts.greeter_session
    budget = ledger = None
    if in_session:
        from aipc.cloud.budget import Budget

        budget = Budget()  # เพดานค่าใช้จ่าย Claude ต่อวันของผู้ใช้คนนี้
        from aipc.cloud.ledger import Ledger

        ledger = Ledger()  # บันทึกสิ่งที่ส่งออกนอกเครื่อง
    skill_forge = _skill_forge(budget, ledger) if in_session else None
    user_skills = None
    if in_session:
        from aipc.skills.userskills import UserSkills

        user_skills = UserSkills()  # ~/.local/share/aipc/skills ของผู้ใช้คนนี้ (การ์ด 0017)
    ui_settings = UiSettings(opts.settings_path, opts.theme)
    from aipc.skills.actions import Executor

    # สั่งเว็บด้วยเสียง (การ์ด 0024) · เบราว์เซอร์ของผู้ช่วย เปิดเมื่อสั่งครั้งแรก · ใช้ร่วมกับปุ่มและสกิล (การ์ด 0031)
    browser_ctl = BrowserController(active=in_session, ledger=ledger)
    claude_on = lambda: ui_settings.useClaude  # noqa: E731 · สวิตช์ Claude ในหน้าตั้งค่า (การ์ด 0016)
    chat = ChatController(active=in_session, tools=tools,
                          cloud=_cloud_client(budget, ledger) if in_session else None,
                          model_name=_local_model_name(),
                          forge=skill_forge is not None, claude_on=claude_on)  # fmt: skip
    engine._backends = {
        "uiSettings": ui_settings,
        "system": SystemStatus(),
        # โหมด greeter ห้ามมีทางลัดของโหมดพัฒนาหรือสถานะสาธิตเด็ดขาด
        "login": LoginController(
            opts.dev and not real,
            None if real else opts.demo_scan,
            greeter_session=opts.greeter_session,
            # สแกนหน้าเข้าเครื่อง (การ์ด 0015) · เฉพาะหน้า Login จริงที่มี visiond
            face=_face_client() if opts.greeter_session else None,
        ),
        # สมัคร/กู้คืนจริงเฉพาะหน้า Login จริง · หน้าต่างพัฒนาเป็นแบบจำลองที่บอกว่า "จำลอง" (การ์ด 0012)
        "signup": SignupController(
            real=bool(opts.greeter_session),
            dev=opts.dev and not real,
            face=_face_client() if opts.greeter_session else None,
        ),
        "filesBrowser": FilesBrowser(),
        "skills": SkillsController(
            # การ์ด 0031: เปิดเว็บ (พิมพ์ · ปุ่ม · ขั้นตอนสกิล) ด้วยเบราว์เซอร์ของผู้ช่วยตัวเดียวกับคำสั่งเสียง
            executor=Executor(browser=browser_ctl.open_web) if in_session else None,
            run_timer=not opts.greeter_session,
            llm_ready=lambda: chat.ready,
            forge=skill_forge,
            user_skills=user_skills,
            weather=_weather(ledger) if in_session else None,
            claude_on=claude_on,
            weather_on=lambda: ui_settings.useWeather,
            gcal=_gcal(ledger) if in_session else None,
            gcal_alert_min=lambda: ui_settings.gcalAlertMin,
            holidays=_holidays(ledger) if in_session else None,
        ),
        "chat": chat,
        "cloudUsage": CloudUsage(budget, available=chat._cloud is not None, ledger=ledger),
        # แผงความเป็นส่วนตัวแบบสด (2026-10-07) · หน้า Login ไม่มีเจ้าของข้อมูล → ไม่แสดง
        "privacyStatus": PrivacyStatus(
            ledger=ledger,
            claude_on=claude_on,
            weather_on=lambda: ui_settings.useWeather,
            active=in_session,
        ),
        # ขั้น C: สถานะตัวตรวจด้วยกล้อง (อ่านไฟล์ทุก 2 วิ เฉพาะเซสชันจริง)
        "presenceStatus": PresenceStatus(active=opts.session and not opts.greeter_session),
        # อ่านคำตอบออกเสียง (การ์ด 0019) · หน้า Login ไม่มีเจ้าของเซสชัน → ไม่มีปุ่ม
        "voice": VoiceController(active=in_session),
        "browser": browser_ctl,
        # หน้า Login ไม่มีเจ้าของข้อมูล → ไม่มีรายการไดรฟ์ให้สำรอง
        "backupCtl": BackupController(drives=(lambda: []) if opts.greeter_session else None),
        "session": SessionController(opts.session and not opts.greeter_session),
        # หน้า Login (ผู้ใช้ _greetd) ไม่มีเจ้าของเซสชัน → ไม่เปิดระบบใบหน้า (การ์ด 0006)
        "face": FaceController(active=not opts.greeter_session),
        # เจ้าของบัญชีเปิด/ปิดเข้าเครื่องด้วยใบหน้าเอง (การ์ด 0015) · หน้า Login ไม่มีสวิตช์นี้
        "loginFace": LoginFaceController(
            face=None if opts.greeter_session or not real else _face_client(short=True)
        ),
    }
    chat.statusChanged.connect(engine._backends["skills"].skillsChanged)  # สกิลแปลพร้อมเมื่อ AI พร้อม
    last_claude = [ui_settings.useClaude]

    def on_settings() -> None:  # สวิตช์ Claude เปลี่ยนจริง (ไม่ใช่ธีม/ขนาดตัวอักษร) → เครื่องมือของ AI เปลี่ยน
        if ui_settings.useClaude != last_claude[0]:
            last_claude[0] = ui_settings.useClaude
            chat.claudeSwitched()
            engine._backends["skills"].skillsChanged.emit()

    ui_settings.changed.connect(on_settings)
    # เฉพาะเซสชันจริงบนจอ Wayland (เทสต์ใช้ offscreen = ไม่เริ่ม swayidle และไม่เขียนภาพจอล็อก)
    if opts.session and not opts.greeter_session and app.platformName() == "wayland":
        engine._idle = _start_idle_lock(ui_settings, app)
    voice = engine._backends["voice"]
    # คีย์ลัด F9 ทั้งเครื่อง (labwc → FIFO · การ์ด 0024) · เฉพาะเซสชันจริงของผู้ใช้
    engine._hotkey = HotkeyListener(active=opts.session and not opts.greeter_session)
    engine._hotkey.pressed.connect(voice.toggleHandsFree)
    app.aboutToQuit.connect(engine._backends["browser"].close)  # ออกจากระบบ = ปิดเบราว์เซอร์ของผู้ช่วย
    # การ์ด 0028: คำพูดจากคีย์ลัดที่ตรงเป๊ะกับสกิลที่ทำด้วยโค้ด (เช่น ที่ Claude สร้าง) = ทำสกิลนั้น
    engine._backends["browser"]._skill_match = engine._backends["skills"].voiceSkill
    voice.use_skill_phrases(engine._backends["skills"].voicePhrases)  # ทาง ข: hotwords ของสกิล

    def ready_inputs() -> dict:
        from aipc.cloud.ask import find_claude

        return {"ai_ready": chat.ready, "voice_available": voice.available,
                "mic_available": voice.micAvailable, "claude": find_claude()}  # fmt: skip

    engine._backends["system"].ready_inputs = ready_inputs  # ตรวจความพร้อมก่อนสาธิต (หน้าเครื่อง)
    holder["skills"] = engine._backends["skills"]
    ctx = engine.rootContext()
    for name, obj in engine._backends.items():
        ctx.setContextProperty(name, obj)
    # ภาพสดขณะลงทะเบียนใบหน้า (การ์ด 0010) · QML ใช้ image://face/<เลขภาพ>
    engine._face_provider = engine._backends["face"].image_provider()
    engine.addImageProvider("face", engine._face_provider)
    # ภาพสดตอนลงทะเบียนผ่าน visiond (หน้าสมัคร / สวิตช์เข้าเครื่องด้วยใบหน้า · การ์ด 0015)
    from aipc.ui.enrollview import EnrollPreviewProvider

    views = (("signupface", "signupEnroll", engine._backends["signup"].enroll_view),
             ("loginface", "loginFaceEnroll", engine._backends["loginFace"].enroll_view),
             ("loginscan", "loginScan", engine._backends["login"].scan_view))  # fmt: skip
    for name, prop, view in views:
        engine.rootContext().setContextProperty(prop, view)
        provider = EnrollPreviewProvider(view)
        setattr(engine, f"_{name}_provider", provider)  # กัน Python เก็บกวาดทิ้ง
        engine.addImageProvider(name, provider)
    screen = "shell" if opts.session else opts.screen
    ctx.setContextProperty("startScreen", screen if screen in SCREENS else "login")
    ctx.setContextProperty("startPage", opts.page if opts.page in PAGES else "workspace")
    ctx.setContextProperty("startSignupStep", max(0, min(opts.signup_step, 3)))
    dev = (opts.dev or opts.demo_scan is not None) and not real
    ctx.setContextProperty("devMode", dev)
    ctx.setContextProperty("i18nTable", i18n.table())  # การ์ด 0039: ตารางแปล (ไทย → อังกฤษ)
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
    face = backends.get("face")
    if face is not None:  # หยุดงานกล้องและรอเธรดจบก่อนรื้อหน้าจอ (พบ 2026-09-28)
        face.shutdown()
    chat = backends.get("chat")
    if chat is not None:  # หยุดคำตอบที่ค้างและตัวจับเวลาตรวจสถานะ AI
        chat.shutdown()
    voice = backends.get("voice")
    if voice is not None:  # ปิดตัวสังเคราะห์เสียงที่เปิดค้าง (คืน RAM ~670 MB)
        voice.close()
    if shiboken6.isValid(engine):
        shiboken6.delete(engine)
    # ชิ้นหน้าจอที่ Qt ตั้งให้ลบทีหลัง (deleteLater) ต้องหายก่อนปล่อย backend · ไม่งั้นมันทำงานต่อในรอบ event ถัดไป
    # แล้วอ่าน backend ที่ถูกลบไปแล้ว (พบ 2026-10-01: เทสต์หน้าจอล้มสลับข้อ "voice/face เป็น undefined")
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    backends.clear()


def screenshot(engine, path: Path, delay_ms: int = 600) -> None:
    """ถ่ายภาพหน้าต่างแล้วปิดแอป · ใช้ทำภาพประกอบเล่มและตรวจหน้าตาโดยไม่ต้องมีจอ."""

    def grab():
        win = engine.rootObjects()[0]
        win.grabWindow().save(str(path))
        QGuiApplication.quit()

    QTimer.singleShot(delay_ms, grab)
