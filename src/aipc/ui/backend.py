"""วัตถุ Python ที่หน้าจอ QML เรียกใช้.

หลักการ: QML มีหน้าที่วาดเท่านั้น ส่วนการตัดสินใจ ตัวเลข และการตรวจข้อมูลอยู่ใน Python
ซึ่งเทสต์ได้ · QML เห็นวัตถุเหล่านี้เป็นชื่อ เช่น uiSettings.theme หรือ signup.checkUsername(...)

แต่ละ @Property คือค่าที่ QML อ่านได้ และเมื่อ Python ปล่อย signal `changed`
ทุกจุดบนจอที่ใช้ค่านั้นจะวาดใหม่เอง (นี่คือ binding ของ QML)
"""

from __future__ import annotations

import getpass
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from aipc import i18n
from aipc.accounts import validation
from aipc.bench import machine
from aipc.doctor import hardware
from aipc.i18n import tr
from aipc.skills import machine as skill_machine
from aipc.ui import files, privacy, settings, thaidate


class I18nBridge(QObject):
    """ให้ QML แปลข้อความที่สร้างตอนทำงาน (การ์ดคำตอบ การเตือน) ด้วยแม่แบบในตารางแปล (การ์ด 0039 · Tr.x)."""

    @Slot(str, result=str)
    def text(self, s: str) -> str:
        from aipc import i18n

        return i18n.tr_text(s)


class UiSettings(QObject):
    changed = Signal()
    languageChanged = Signal()  # noqa: N815 · การ์ด 0039

    def __init__(self, path: Path | None = None, override_theme: str | None = None):
        super().__init__()
        self._path = path
        self._prefs = settings.load(path)
        if override_theme in settings.THEMES:
            self._prefs.theme = override_theme
        from aipc import i18n

        i18n.set_lang(self._prefs.language)  # ภาษาของบัญชีนี้ (การ์ด 0039)

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

    @Property(str, notify=changed)
    def language(self) -> str:  # การ์ด 0039: "th" | "en" · หน้าจอผูกกับค่านี้ผ่าน Tr.lang
        return self._prefs.language

    @Slot(str)
    def setLanguage(self, lang: str) -> None:  # noqa: N802
        from aipc import i18n

        if lang in settings.LANGS and lang != self._prefs.language:
            self._prefs.language = lang
            settings.save(self._prefs, self._path)
            i18n.set_lang(lang)  # ข้อความที่สร้างจาก Python (การ์ดคำตอบ ฯลฯ)
            self.changed.emit()
            self.languageChanged.emit()  # app.py ให้ตัวอื่นอ่านข้อความใหม่ในภาษานี้

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
    def clearWebOnLogout(self) -> bool:  # noqa: N802
        """ออกจากบัญชีเว็บทุกครั้งที่ออกจากระบบ (การ์ด 0031 รอบ 3) · สคริปต์เซสชันอ่านค่านี้จาก ui.json ตอนจบ."""
        return self._prefs.clear_web_on_logout

    @Property(bool, notify=changed)
    def webClearFailed(self) -> bool:  # noqa: N802
        """ล้างบัญชีเว็บตอนออกจากระบบครั้งก่อนไม่สำเร็จ (ไฟล์ธงของ logout_clear) · บอกผู้ใช้ (H2)."""
        from aipc.browser import logout_clear

        return (logout_clear.state_dir() / logout_clear.FAILED).exists()

    @Slot(bool)
    def setClearWebOnLogout(self, on: bool) -> None:  # noqa: N802
        if bool(on) != self._prefs.clear_web_on_logout:
            self._prefs.clear_web_on_logout = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Property(bool, notify=changed)
    def useClaude(self) -> bool:  # noqa: N802
        return self._prefs.use_claude

    # โมเดลของแชทงาน (การ์ด 0053)
    @Property(str, notify=changed)
    def cloudModel(self) -> str:  # noqa: N802
        return self._prefs.cloud_model

    @Property("QVariantList", constant=True)
    def cloudModels(self) -> list:  # noqa: N802
        return list(settings.CLOUD_MODELS)

    @Property(str, notify=changed)
    def cloudEffort(self) -> str:  # noqa: N802
        return self._prefs.cloud_effort

    @Property("QVariantList", constant=True)
    def cloudEfforts(self) -> list:  # noqa: N802
        return list(settings.CLOUD_EFFORTS)

    @Slot(str, result=bool)
    def setCloudEffort(self, effort: str) -> bool:  # noqa: N802
        if effort not in settings.CLOUD_EFFORTS:
            return False
        if effort != self._prefs.cloud_effort:
            self._prefs.cloud_effort = effort
            settings.save(self._prefs, self._path)
            self.changed.emit()
        return True

    @Slot(str, result=bool)
    def setCloudModel(self, model: str) -> bool:  # noqa: N802
        if model not in settings.CLOUD_MODELS:
            return False
        if model != self._prefs.cloud_model:
            self._prefs.cloud_model = model
            settings.save(self._prefs, self._path)
            self.changed.emit()
        return True

    @Slot(bool)
    def setUseClaude(self, on: bool) -> None:  # noqa: N802
        """สวิตช์ส่งต่อ Claude (การ์ด 0016 หัวข้อ 1) · ปิด = ไม่ถาม Claude และไม่สร้างสกิล ·
        ข้อมูลไม่ออกไป Anthropic."""
        if bool(on) != self._prefs.use_claude:
            self._prefs.use_claude = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Property(bool, notify=changed)
    def useWeather(self) -> bool:  # noqa: N802
        return self._prefs.use_weather

    @Slot(bool)
    def setUseWeather(self, on: bool) -> None:  # noqa: N802
        """สวิตช์อากาศ (แผงความเป็นส่วนตัว 2026-10-07) · ปิด = ไม่ส่งชื่อเมืองไป Open-Meteo."""
        if bool(on) != self._prefs.use_weather:
            self._prefs.use_weather = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    # ล็อกเมื่อไม่ได้ใช้เครื่อง (aipc.ui.idle · ขั้น A 2026-10-06)
    @Property(int, notify=changed)
    def lockMin(self) -> int:  # noqa: N802
        return self._prefs.lock_min

    @Property(int, notify=changed)
    def logoutMin(self) -> int:  # noqa: N802
        return self._prefs.logout_min

    @Property("QVariantList", constant=True)
    def lockChoices(self) -> list:  # noqa: N802
        return list(settings.LOCK_CHOICES)

    @Property("QVariantList", constant=True)
    def logoutChoices(self) -> list:  # noqa: N802
        return list(settings.LOGOUT_CHOICES)

    @Slot(int)
    def setLockMin(self, minutes: int) -> None:  # noqa: N802
        if minutes in settings.LOCK_CHOICES and minutes != self._prefs.lock_min:
            self._prefs.lock_min = int(minutes)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Slot(int)
    def setLogoutMin(self, minutes: int) -> None:  # noqa: N802
        if minutes in settings.LOGOUT_CHOICES and minutes != self._prefs.logout_min:
            self._prefs.logout_min = int(minutes)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    # เตือนนัดจากปฏิทิน Google ล่วงหน้า (การ์ด 0032)
    @Property(int, notify=changed)
    def gcalAlertMin(self) -> int:  # noqa: N802
        return self._prefs.gcal_alert_min

    @Property("QVariantList", constant=True)
    def gcalAlertChoices(self) -> list:  # noqa: N802
        return list(settings.GCAL_ALERT_CHOICES)

    @Slot(int)
    def setGcalAlertMin(self, minutes: int) -> None:  # noqa: N802
        if minutes in settings.GCAL_ALERT_CHOICES and minutes != self._prefs.gcal_alert_min:
            self._prefs.gcal_alert_min = int(minutes)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    # ขั้น C: กล้องช่วยดูว่าเจ้าของยังอยู่ (aipc.ui.presence)
    @Property(bool, notify=changed)
    def presence(self) -> bool:
        return self._prefs.presence

    @Property(int, notify=changed)
    def presenceLockS(self) -> int:  # noqa: N802
        return self._prefs.presence_lock_s

    @Property(int, notify=changed)
    def presenceLogoutS(self) -> int:  # noqa: N802
        return self._prefs.presence_logout_s

    @Property("QVariantList", constant=True)
    def presenceChoices(self) -> list:  # noqa: N802
        return list(settings.PRESENCE_CHOICES)

    @Property("QVariantList", constant=True)
    def presenceLogoutChoices(self) -> list:  # noqa: N802
        return list(settings.PRESENCE_LOGOUT_CHOICES)

    @Slot(bool)
    def setPresence(self, on: bool) -> None:  # noqa: N802
        if bool(on) != self._prefs.presence:
            self._prefs.presence = bool(on)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Slot(int)
    def setPresenceLockS(self, s: int) -> None:  # noqa: N802
        if s in settings.PRESENCE_CHOICES and s != self._prefs.presence_lock_s:
            self._prefs.presence_lock_s = int(s)
            settings.save(self._prefs, self._path)
            self.changed.emit()

    @Slot(int)
    def setPresenceLogoutS(self, s: int) -> None:  # noqa: N802
        if s in settings.PRESENCE_LOGOUT_CHOICES and s != self._prefs.presence_logout_s:
            self._prefs.presence_logout_s = int(s)
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


# การ์ด 0044: ลองฟังเป็นอังกฤษเฉพาะข้อความไทยที่สั้น (คำสั่งอังกฤษที่ Zipformer ถอดเป็นไทยเพี้ยนจะสั้น)
# Pakon 2026-10-20: เดิม 16 ตัด "What time is it" (ถอดเป็นไทย 17 ตัวอักษร · การ์ด 0044 L5)
ENGLISH_TRY_MAX = 24


def _thai_missed(text: str, skill=None, intent=None) -> bool:
    """ข้อความไทยจากคีย์ลัดไม่ตรงอะไรเลย → ลองฟังเป็นอังกฤษ (การ์ด 0040 หัวข้อ 13).

    การ์ด 0044: ใช้เส้นทางเต็มของแอป (ตั้งเตือน สกิล ค่าตั้ง · skill/intent จาก SkillsController) ·
    คำถามภาษาไทย (มีคำถาม ไหม อะไร กี่ ใคร …) และประโยคยาว = ภาษาไทยแน่ ไม่ต้องลอง
    (เดิมเสีย 1.3–2.0 วิทุกประโยค)
    """
    from aipc.skills import router
    from aipc.ui import handsfree

    if handsfree.route(text, False, skill, intent) != handsfree.UNKNOWN or handsfree.yes_no(text):
        return False
    return not router.is_question(text) and len(re.sub(r"\s+", "", text)) <= ENGLISH_TRY_MAX


def _command_complete(text: str, skill=None, intent=None) -> bool:
    """คำสั่งครบแล้ว (เว็บ เครื่อง ค่าตั้ง สกิลตรงเป๊ะ) → จบการฟังเร็ว (การ์ด 0044) ·
    ตั้งเตือน/งาน AI/คำถาม ไม่นับ (อาจพูดต่อ เช่น "เตือนประชุม … พรุ่งนี้สิบโมง")."""
    from aipc.ui import handsfree

    done = (
        handsfree.BROWSER,
        handsfree.COMMAND,
        handsfree.APP,
        handsfree.OPEN_BROWSER,
        handsfree.SKILL,
    )
    return handsfree.route(text, True, skill, intent) in done


def listener_extras() -> dict:
    """ค่าที่ตัวอัดของแอปใช้ (เครื่องมือวัด aipc.spikes.voice_e2e_latency ใช้ชุดเดียวกัน)."""
    return {"complete": _command_complete}


def _english_command(text: str) -> bool:
    """ข้อความอังกฤษเป็นคำสั่งที่รู้จักแน่ (ตัวแปลงระยะ C) หรือคำตอบใช่/ไม่ → ใช้แทนข้อความไทย."""
    from aipc.skills import english
    from aipc.ui import handsfree

    return english.to_thai(text) is not None or handsfree.yes_no(text) in ("yes", "no")


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
    # กดคีย์ลัด F9 (การ์ด 0024) · Pakon เลือก 2026-10-13: ถอดเสร็จทำทันที ไม่ต้องกดส่ง
    heardHandsFree = Signal(str)  # noqa: N815
    _state = Signal(int, bool, str)
    _heard = Signal(str, str, float)

    def __init__(
        self, speaker=None, active: bool = True, idle_poll_ms: int = 60_000, listener=None
    ):
        super().__init__()
        from aipc.voice import stt, tts, zipformer

        self._speaker = (speaker or tts.Speaker(self._weak("_state"))) if active else None
        # กดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) · None = หน้า Login
        # คีย์ลัดถอดด้วย Zipformer + hotwords (การ์ด 0026) · ปุ่มไมค์ใช้ whisper เหมือนเดิม
        if active and listener is None:
            from aipc import i18n

            # การ์ด 0044: Zipformer ไม่ปิดตัวเองเมื่อไม่ได้ใช้ (เดิม 10 นาที → กดครั้งถัดไปรอโหลด 4.6 วิ)
            fast = zipformer.Transcriber(idle_s=float("inf"))
            listener = stt.Listener(self._weak("_heard"), fast=fast, complete=_command_complete,
                                    language=i18n.lang, try_english=_thai_missed,
                                    use_english=_english_command)  # fmt: skip # การ์ด 0040
        self._listener = listener if active else None
        self._key, self._job, self._message = -1, -1, ""
        self._transcribing, self._mic_message, self._last_stt_s = False, "", 0.0
        # ตัวอัดหยุดเองเมื่อพูดจบ (การ์ด 0019 ข้อ 10) จากเธรดของมัน → ดูสถานะทุก 0.15 วิระหว่างฟัง
        self._awaiting = False
        self._hands_free = False
        self._mic_poll = QTimer(self, interval=150, timeout=self._poll_mic)
        self._state.connect(self._on_state)
        self._heard.connect(self._on_heard)
        self._idle = QTimer(self, interval=idle_poll_ms, timeout=self._idle_check)
        if self._speaker is not None or self._listener is not None:
            self._idle.start()

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._speaker is not None and self._speaker.available

    @Property(bool, notify=changed)
    def englishVoice(self) -> bool:  # noqa: N802
        """มีเสียงอ่านภาษาอังกฤษ (การ์ด 0039 ระยะ B) · หน้าตั้งค่าบอกสถานะ."""
        return self._speaker is not None and self._speaker.english_available

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
        from aipc.voice import tts

        job = self._speaker.say(text)
        if job < 0 and tts.language(text) == "en" and not self._speaker.english_available:
            self._key, self._message = -1, "ยังไม่ได้ติดตั้งเสียงอ่านภาษาอังกฤษ"
        elif job < 0:
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
    def set_route_hooks(self, skill, intent) -> None:
        """การ์ด 0044: ตัวอัดใช้เส้นทางเต็มของแอป (SkillsController.voiceSkill / voiceIntent) ตัดสินว่า
        จะลองฟังอังกฤษไหม และคำสั่งครบหรือยัง · app.py ต่อให้หลังสร้าง SkillsController."""
        lis = self._listener
        if lis is None:
            return
        lis._try_english = lambda t: _thai_missed(t, skill, intent)
        lis._complete = lambda t: _command_complete(t, skill, intent)

    @Slot()
    def preload(self) -> None:
        """โหลดตัวถอดของคีย์ลัดไว้ก่อน (การ์ด 0044 · เดิมโหลดตอนกดครั้งแรก 4.6 วิ) · เบื้องหลัง ไม่ค้างหน้าจอ."""
        fast = getattr(self._listener, "_fast", None) if self._listener is not None else None
        if fast is not None and fast.available:
            fast.warm()

    def _idle_check(self) -> None:
        if self._speaker is not None:
            self._speaker.idle_check()
        fast = getattr(self._listener, "_fast", None)
        if fast is not None:  # ตัวถอดของคีย์ลัดไม่ได้ใช้นาน = ปิดคืน RAM
            fast.idle_check()

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

    @Property(bool, notify=micChanged)
    def handsFree(self) -> bool:  # noqa: N802
        """กำลังฟัง/ถอดจากคีย์ลัด (ไม่ใช่ปุ่มไมค์ในแชท) · หน้าจอแสดงกล่องคำสั่งเสียงทุกหน้า (Pakon 2026-10-20)."""
        return self._hands_free

    @Property(str, notify=micChanged)
    def micMessage(self) -> str:  # noqa: N802
        return self._mic_message

    @Slot()
    def startListening(self) -> None:  # noqa: N802
        self._start_listening(fast=False)

    def _start_listening(self, fast: bool) -> None:
        if self._listener is None or self._transcribing:
            return
        if self._key != -1:  # กำลังอ่านออกเสียงอยู่ = หยุดก่อน ไม่ให้ไมค์ได้ยินลำโพง
            self.stop()
        err = self._listener.start(fast=fast)
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

    @Slot()
    def toggleHandsFree(self) -> None:  # noqa: N802
        """คีย์ลัด F9 / Alt+Space: เริ่มฟัง (เสียงติ๊ก) · กดอีกครั้งระหว่างฟัง = หยุดแล้วถอดเลย."""
        if self._listener is None:
            return
        if self._listener.listening:
            self.stopListening()
            return
        from aipc.ui.handsfree import beep

        self._hands_free = True
        self._start_listening(fast=True)
        if self._awaiting:
            beep(high=True)
        else:
            self._hands_free = False
            self.micChanged.emit()  # เริ่มฟังไม่ได้ = หน้าจอบอกเหตุผล (micMessage) แล้วปิดกล่องเอง

    @Slot(str, str, float)
    def _on_heard(self, text: str, err: str, secs: float) -> None:
        hands_free, self._hands_free = self._hands_free, False
        self._awaiting = False
        self._mic_poll.stop()
        self._transcribing, self._last_stt_s = False, secs
        done = "ทำตามที่สั่งแล้ว" if hands_free else "ตรวจข้อความแล้วกดส่ง"
        self._mic_message = err or f"ถอดเสียงใน {secs:.1f} วิ · {done}"
        self.micChanged.emit()
        if hands_free:
            from aipc.ui.handsfree import beep

            beep(high=False)
        if text:
            (self.heardHandsFree if hands_free else self.transcribed).emit(text)
        elif hands_free and self.available:  # ไม่ได้มองจอ (เบราว์เซอร์เต็มจอ) = พูดบอกว่าทำไมไม่ได้ทำ
            self.speak(-3, err or "ไม่ได้ยินเสียงพูด")

    def use_skill_phrases(self, phrases) -> None:
        """การ์ด 0028 ทาง ข: ประโยคของสกิลผู้ใช้เป็น hotwords ของตัวถอดคีย์ลัด (app.py ต่อให้)."""
        fast = getattr(self._listener, "_fast", None)
        if fast is not None and hasattr(fast, "extra_hotwords"):
            fast.extra_hotwords = phrases

    def close(self) -> None:
        if self._speaker is not None:
            self._speaker.close()
        if self._listener is not None:
            self._listener.cancel()
            fast = getattr(self._listener, "_fast", None)
            if fast is not None:
                fast.close()


class CloudUsage(QObject):
    """ค่าใช้จ่าย Claude วันนี้ + เพดานต่อวัน (หน้าตั้งค่า) · ข้อมูลจาก aipc.cloud.budget
    · ไม่มี Claude = available False."""

    changed = Signal()
    guideChanged = Signal()  # noqa: N815

    def __init__(self, budget=None, available: bool = False, poll_ms: int = 15000, ledger=None,
                 user: str | None = None, addresses=None, terminal=None, spawn=None,
                 find=None):  # fmt: skip
        super().__init__()
        self._user = user or getpass.getuser()
        self._addresses = addresses  # ฟังก์ชันอ่าน IP (เทสต์ใส่ของปลอม) · None = setup_guide.addresses
        self._guide: list = []
        # เชื่อมต่อที่เครื่องนี้ (การ์ด 0021 หัวข้อ 10)
        # terminal = path ของ lxterminal (None = หาเอง · "" = ไม่มี)
        self._terminal = (shutil.which("lxterminal") or "") if terminal is None else terminal
        self._spawn = spawn  # เทสต์ใส่ตัวเปิดโปรเซสปลอม · None = subprocess.Popen
        self._find = find  # None = aipc.cloud.ask.find_claude
        self._proc = None
        self._connected_now = False
        self._watch = QTimer(self, interval=1000, timeout=self._check_connect)
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

    # ---------- คู่มือเชื่อมต่อ Claude (การ์ด 0021) ----------
    @Property("QVariantList", notify=guideChanged)
    def guideSteps(self) -> list:  # noqa: N802
        return self._guide

    @Slot()
    def refreshGuide(self) -> None:  # noqa: N802
        """อ่าน IP ใหม่ตอนผู้ใช้กดเปิดคู่มือ (เพิ่งต่อเน็ตก็ได้ที่อยู่ล่าสุด)."""
        from aipc.cloud import setup_guide

        read = self._addresses or setup_guide.addresses
        self._guide = setup_guide.steps(self._user, read())
        self.guideChanged.emit()

    @Property(bool, notify=guideChanged)
    def canConnectHere(self) -> bool:  # noqa: N802
        """มีหน้าต่างคำสั่งในเครื่อง (lxterminal) = เชื่อมต่อจากจอนี้ได้ · ไม่มี = เหลือทาง SSH."""
        return bool(self._terminal)

    @Property(bool, notify=guideChanged)
    def connecting(self) -> bool:
        return self._proc is not None

    @Property(bool, notify=guideChanged)
    def connectedNow(self) -> bool:  # noqa: N802
        """หน้าต่างเชื่อมต่อปิดแล้วและตอนนี้มี claude · แอปยังใช้ไม่ได้จนกว่าจะออกแล้วเข้าใหม่."""
        return self._connected_now

    @Slot()
    def connectHere(self) -> None:  # noqa: N802
        """เปิด lxterminal ที่รัน `python -m aipc.cloud.connect` ของรุ่นแอปนี้เท่านั้น.

        คำสั่งตายตัว ไม่ใช่ shell ทั่วไป
        """
        import shlex
        import subprocess
        import sys

        if not self._terminal or self._proc is not None:
            return  # ไม่มีเทอร์มินัล หรือหน้าต่างเดิมยังเปิดอยู่ = ไม่เปิดเพิ่ม
        inner = shlex.join([sys.executable, "-m", "aipc.cloud.connect"])
        # --no-remote: โปรเซสแยกต่อหน้าต่าง (ปิดหน้าต่าง = โปรเซสจบ · แอปจึงรู้ว่าเสร็จ) และได้ env ของแอป
        cmd = [self._terminal, "--no-remote", "--title=เชื่อมต่อ Claude", "--geometry=100x32",
               "--command=" + inner]  # fmt: skip
        try:
            self._proc = (self._spawn or subprocess.Popen)(cmd)
        except OSError:
            self._proc = None
            return
        self._watch.start()
        self.guideChanged.emit()

    def _check_connect(self) -> None:
        if self._proc is None or self._proc.poll() is None:
            return
        from aipc.cloud.ask import find_claude

        self._proc = None
        self._watch.stop()
        self._connected_now = (self._find or find_claude)() is not None
        self.guideChanged.emit()

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
    devicesChanged = Signal()  # noqa: N815 · รายการอุปกรณ์ (การ์ด 0051)
    _devicesDone = Signal(object)  # noqa: N815

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
        self._devices: list[dict] = []
        self._devices_busy = False
        self._devicesDone.connect(self._on_devices)
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

    # ---------- อุปกรณ์ที่ต่ออยู่ (การ์ด 0051 · aipc.doctor.devices · อ่านอย่างเดียว) ----------
    @Property("QVariantList", notify=devicesChanged)
    def devices(self) -> list:
        return self._devices

    @Property(bool, notify=devicesChanged)
    def devicesBusy(self) -> bool:  # noqa: N802
        return self._devices_busy

    @Slot()
    def scanDevices(self) -> None:  # noqa: N802
        """ตรวจในเธรดแยก (wpctl/bluetoothctl อาจช้า) · เปิดหน้าหรือกด "ตรวจใหม่" เท่านั้น ไม่ตรวจวนเอง."""
        import threading

        from aipc.doctor import devices

        if self._devices_busy:
            return
        self._devices_busy = True
        self.devicesChanged.emit()
        root = self._root

        def work():
            try:
                found = devices.scan(root)
            except Exception:  # noqa: BLE001 · ตรวจไม่ได้ทั้งหมด ดีกว่าค้าง
                found = dict.fromkeys(devices.KINDS)
            self._devicesDone.emit(found)

        threading.Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_devices(self, found) -> None:
        from aipc.doctor import devices

        self._devices = [
            {"label": devices.LABELS[k], "items": found.get(k) or [],
             "state": "unknown" if found.get(k) is None else ("none" if not found[k] else "ok")}
            for k in devices.KINDS
        ]  # fmt: skip
        self._devices_busy = False
        self.devicesChanged.emit()

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
            {"id": c.id, "title": c.title, "status": c.status, "detail": c.detail, "fix": c.fix,
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
        return tr("ว่าง {gb} GB", gb=f"{self._free_gb:.0f}") if self._free_gb is not None else "—"

    @Property(bool, notify=changed)
    def cameraPresent(self) -> bool:  # noqa: N802
        return self._camera

    @Property("QVariantList", notify=changed)
    def alerts(self) -> list:
        """ปัญหาเครื่องที่แถบบนต้องบอก (BRIEF 5.7 ข้อ 3 · การ์ด 0041) · ว่าง = "เครื่องปกติ".

        โค้ดตัดสินจากเกณฑ์เดียวกับหน้าเครื่อง (H6): ออฟไลน์ · ร้อน ≥ HOT_C · พื้นที่เกิน 80% · ไฟเลี้ยงไม่พอ ·
        ค่าที่อ่านไม่ได้ ("ไม่รู้") ไม่นับเป็นปัญหา (ไม่เดา)
        """
        out = []
        if self._network is False:
            out.append({"id": "network", "text": tr("ออฟไลน์"), "level": "warn"})
        if self._temp is not None and self._temp >= hardware.HOT_C:
            out.append(
                {"id": "temp", "text": tr("ร้อน {t}°C", t=f"{self._temp:.0f}"), "level": "danger"}
            )
        bad = {c["id"]: c["level"] for c in self._checks if c["level"] in ("warn", "danger")}
        if "storage" in bad:
            out.append(
                {
                    "id": "storage",
                    "text": tr("พื้นที่ใกล้เต็ม · {free}", free=self.storageText),
                    "level": bad["storage"],
                }
            )
        if "power" in bad:
            out.append({"id": "power", "text": tr("ไฟเลี้ยงไม่พอ"), "level": bad["power"]})
        return out

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
        return tr("ไฟล์ของฉัน") + (
            "".join(" / " + p for p in Path(self._rel).parts) if self._rel else ""
        )

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
        return tr(
            "ว่าง {free} จาก {total} GB", free=f"{du.free / 1e9:.0f}", total=f"{du.total / 1e9:.0f}"
        )

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
            folder = tr("ไฟล์ของฉัน") + ("" if parent == "." else " / " + parent.replace("/", " / "))
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
                 greeter_session: list[str] | None = None, connect=None, face=None,
                 remember=None):  # fmt: skip
        super().__init__()
        self._dev = dev_mode
        # เข้าสำเร็จ → บอกตัวช่วยว่าใครเข้าล่าสุด (ธีมหน้า Login ครั้งถัดไป · การ์ด 0051) · None = ไม่ต้องจำ
        self._remember = remember
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
            self._remember_user(self._found_user)
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
        self._remember_user(username.strip())
        # greetd จะเริ่มเซสชันของผู้ใช้หลัง greeter ปิดตัวเอง
        QTimer.singleShot(0, QCoreApplication.quit)
        return ""

    def _remember_user(self, user: str) -> None:
        """จำไม่ได้ (ตัวช่วยไม่ตอบ) = หน้า Login ครั้งถัดไปใช้ธีมของคนเดิม · ไม่ขวางการเข้าระบบ."""
        if self._remember is not None:
            try:
                self._remember(user)
            except Exception:  # noqa: BLE001 · เรื่องสีหน้าจอต้องไม่ทำให้เข้าระบบไม่ได้
                pass


def _display_name(user: str) -> str:
    """ชื่อที่แสดงจากช่อง comment ของบัญชี (ตั้งตอนสมัคร) · อ่านไม่ได้ = ชื่อผู้ใช้."""
    try:
        import pwd

        return pwd.getpwnam(user).pw_gecos.split(",")[0] or user
    except (ImportError, KeyError):
        return user


POWER_ACTIONS = ("power_off", "reboot")  # การ์ด 0052


class PowerController(QObject):
    """ปุ่มปิดเครื่อง/รีสตาร์ต (การ์ด 0052) ทั้งหน้า Login และในเซสชัน · หน้าจอถามยืนยันก่อนเรียกเสมอ.

    active = หน้า Login จริง หรือเซสชันจริงบน Pi · หน้าต่างพัฒนา = ไม่ปิดเครื่องจริง และบอกว่าจำลอง (H5)
    สั่งผ่าน systemctl (systemd-logind + polkit) · ไม่ต้องใช้ sudo หรือแก้ /etc
    สั่งไม่สำเร็จ = ข้อความค้างให้เห็น (H2) · สั่งแล้ว = ไม่ให้กดซ้ำ
    """

    changed = Signal()

    def __init__(self, active: bool, runner=None):
        super().__init__()
        self._active = active
        self._run = runner or _run_quiet
        self._error = ""
        self._busy = False

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Slot(str, result=bool)
    def request(self, action: str) -> bool:
        from aipc.skills.actions import POWER_CMDS

        if action not in POWER_CMDS or self._busy:
            return False
        if not self._active:
            self._error = "จำลอง: หน้าต่างพัฒนาไม่ปิด/รีสตาร์ตเครื่องจริง"
            self.changed.emit()
            return False
        self._busy, self._error = True, ""
        self.changed.emit()
        code = self._run(POWER_CMDS[action])
        if code != 0:
            self._busy = False
            what = "ปิดเครื่อง" if action == "power_off" else "รีสตาร์ต"
            self._error = f"{what}ไม่สำเร็จ (systemctl ตอบ {code}) · ลองอีกครั้ง หรือกดปุ่มที่ตัวเครื่องค้างไว้"
            self.changed.emit()
            return False
        return True


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


class PresenceStatus(QObject):
    """สถานะของตัวตรวจด้วยกล้อง (ขั้น C) จากไฟล์ที่ตัวตรวจเขียน · อ่านทุก 2 วิ เฉพาะในเซสชันจริง."""

    changed = Signal()
    TEXT = {"active": "พร้อม · กล้องเปิดเมื่อไม่ได้แตะเครื่อง 10 วินาที",
            "watching": "กล้องกำลังดูว่าเจ้าของยังอยู่ (ไม่บันทึกภาพ)",
            "locked": "ล็อกแล้ว", "logout": "กำลังออกจากระบบ",
            "no-template": "ยังไม่ได้ลงทะเบียน \"ใบหน้าของฉัน\" · ลงทะเบียนในหน้านี้ก่อน",
            "camera-error": "ใช้กล้องไม่ได้ตอนนี้ · จะลองใหม่เอง"}  # fmt: skip

    def __init__(self, path: Path | None = None, poll_ms: int = 2000, active: bool = True):
        super().__init__()
        self._path = path
        self._text = ""
        if active:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.refresh)
            self._timer.start(poll_ms)

    @Property(str, notify=changed)
    def text(self) -> str:
        return self._text

    @Slot()
    def refresh(self) -> None:
        import json

        from aipc.ui import presence

        try:
            d = json.loads((self._path or presence.status_path()).read_text(encoding="utf-8"))
            base = self.TEXT.get(d.get("state", ""), "")
            detail = str(d.get("detail", ""))
            text = (
                f"{base} · {detail}"
                if base and detail and d.get("state") in ("locked", "camera-error")
                else base
            )
        except (OSError, ValueError):
            text = ""
        if text != self._text:
            self._text = text
            self.changed.emit()


class PrivacyStatus(QObject):
    """แผงความเป็นส่วนตัวแบบสดในแถบบน (Pakon เลือกข้อ ข 2026-10-07 · aipc.ui.privacy).

    บันทึกส่งออก: ดูเวลาแก้ไฟล์ทุก 2 วิ อ่านทั้งไฟล์เมื่อเปลี่ยน · มีรายการใหม่ = ป้ายเปลี่ยนสี FLASH_S วิ ·
    AI ในเครื่อง: อ่านจาก OS ทุก 15 วิ · หน้า Login ไม่มีเจ้าของข้อมูล (active False) = ไม่แสดง
    """

    changed = Signal()
    FLASH_S = 3.0

    def __init__(self, ledger=None, claude_on=None, weather_on=None, active: bool = True,
                 poll_ms: int = 2000, llm_poll_ms: int = 15000, clock=time.monotonic,
                 today=None, llm_state=None):  # fmt: skip
        super().__init__()
        self._active = active
        self._ledger = ledger
        self._claude_on = claude_on or (lambda: True)
        self._weather_on = weather_on or (lambda: True)
        self._clock = clock
        self._today = today or (lambda: datetime.now().date())
        self._llm_state = llm_state or (lambda: privacy.sandbox_state(privacy.llm_pid()))
        self._llm, self._sent, self._flash_until = "unknown", 0, 0.0
        self._mtime = self._day = None
        self._newest: object = ()  # () = ยังไม่เคยอ่าน · ไม่เปลี่ยนสีตอนเปิดแอป
        self._state: tuple = ()
        if active:
            self.refreshLlm()
            self.refresh()
            self._timer = QTimer(self, interval=poll_ms, timeout=self.refresh)
            self._timer.start()
            self._llm_timer = QTimer(self, interval=llm_poll_ms, timeout=self.refreshLlm)
            self._llm_timer.start()

    @Slot()
    def refreshLlm(self) -> None:  # noqa: N802
        self._llm = self._llm_state()
        self._publish()

    @Slot()
    def refresh(self) -> None:
        if self._ledger is not None:
            try:
                mtime = self._ledger.path.stat().st_mtime_ns
            except OSError:
                mtime = None
            day = self._today()
            if mtime != self._mtime or day != self._day:
                self._mtime, self._day = mtime, day
                entries = self._ledger.entries()  # ใหม่สุดก่อน
                newest = entries[0] if entries else None
                sig = (
                    (newest.get("time"), newest.get("kind"), newest.get("chars"))
                    if newest
                    else None
                )
                if self._newest != () and sig is not None and sig != self._newest:
                    self._flash_until = self._clock() + self.FLASH_S
                self._newest = sig
                self._sent = sum(privacy.today_counts(entries, day).values())
        self._publish()

    def _publish(self) -> None:
        all_off = not self._claude_on() and not self._weather_on()
        state = (self._llm, self._sent, all_off, self._clock() < self._flash_until)
        if state != self._state:
            self._state = state
            self.changed.emit()

    @Property(bool, constant=True)
    def visible(self) -> bool:
        return self._active

    @Property(str, notify=changed)
    def llmState(self) -> str:  # noqa: N802
        return self._state[0] if self._state else "unknown"

    @Property(int, notify=changed)
    def sentToday(self) -> int:  # noqa: N802
        return self._state[1] if self._state else 0

    @Property(bool, notify=changed)
    def allOff(self) -> bool:  # noqa: N802
        return bool(self._state and self._state[2])

    @Property(bool, notify=changed)
    def flash(self) -> bool:
        return bool(self._state and self._state[3])

    @Property(str, notify=changed)
    def text(self) -> str:
        return privacy.panel_text(self.llmState, self.sentToday, self.allOff)

    @Property(str, notify=changed)
    def kind(self) -> str:
        return privacy.panel_kind(self.llmState, self.allOff, self.flash)


def _run_quiet(args: list[str]) -> int:
    import subprocess

    try:
        return subprocess.run(args, check=False, capture_output=True, timeout=10).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


HELPER = "/usr/local/sbin/aipc-accounts"  # ตัวช่วย root ของการ์ด 0012 (ติดตั้งโดย install-greeter.sh)


def greeter_theme(user: str | None = None) -> str:
    """ธีมของหน้า Login จากตัวช่วย (การ์ด 0051) · user = เพิ่งเข้าสำเร็จ (ให้จำไว้) · ไม่ตอบ = ธีมดำ."""
    req = {"op": "greeter-theme"} if user is None else {"op": "greeter-theme", "user": user}
    theme = run_accounts_helper(req, timeout=5).get("theme")
    return theme if theme in settings.THEMES else "dark"


APPS_HELPER = "/usr/local/sbin/aipc-apps"  # ตัวติดตั้งแอปของการ์ด 0054 (ติดตั้งโดย install-apps.sh)


def run_apps_helper(request: dict, on_progress=None) -> dict:
    """เรียกตัวติดตั้งแอปผ่าน sudo (-n = ไม่ถามรหัส sudo) · อ่านทีละบรรทัด: มี "ok" = ผล · อื่น ๆ = ความคืบหน้า."""
    import json
    import subprocess

    try:
        proc = subprocess.Popen(["sudo", "-n", APPS_HELPER], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # fmt: skip
    except OSError as e:
        return {"ok": False, "message": f"เรียกตัวติดตั้งแอปไม่ได้ ({e.strerror or e})"}
    proc.stdin.write(json.dumps(request).encode())
    proc.stdin.close()
    result = None
    for raw in proc.stdout:
        try:
            msg = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(msg, dict) and "ok" in msg:
            result = msg
        elif isinstance(msg, dict) and on_progress is not None:
            on_progress(msg)
    proc.wait()
    return result or {"ok": False,
                      "message": "ตัวติดตั้งแอปยังไม่ได้ติดตั้งในเครื่องนี้ (install-apps.sh)"}  # fmt: skip


def _simulated_install(request: dict, on_progress=None) -> dict:
    """เครื่องพัฒนา (ไม่ใช่ Linux): ไม่ติดตั้งจริง และบอกตรง ๆ ว่าจำลอง (H5)."""
    return {"ok": True, "simulated": True, "message": "จำลอง: เครื่องนี้ไม่ใช่ Pi · ไม่ได้ติดตั้งจริง"}


def run_accounts_helper(request: dict, timeout: float = 30, helper: str = "",
                        missing: str = "") -> dict:  # fmt: skip
    """เรียกตัวช่วยผ่าน sudo (-n = ห้ามถามรหัส ถ้ากฎ sudo ไม่ตรงให้ล้มทันที ไม่ค้าง).

    คำขอส่งทาง stdin เป็น JSON · ตัวช่วยตรวจทุกอย่างซ้ำเอง (H7) หน้าจอแค่ส่งและแสดงผล
    """
    import json
    import subprocess

    try:
        r = subprocess.run(["sudo", "-n", helper or HELPER], input=json.dumps(request).encode(),
                           capture_output=True, timeout=timeout, check=False)  # fmt: skip
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "ตัวจัดการบัญชีไม่ตอบ · ลองอีกครั้ง"}
    except OSError as e:
        return {"ok": False, "message": f"เรียกตัวจัดการบัญชีไม่ได้ ({e.strerror or e})"}
    try:
        out = json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {
            "ok": False,
            "message": missing or "ตัวจัดการบัญชียังไม่ได้ติดตั้งในเครื่องนี้ (install-greeter.sh)",
        }
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


UNSYNCED = "⚠ เครื่องยังไม่ได้ตั้งเวลาจากอินเทอร์เน็ต · เวลาอาจไม่ตรง (ต่อเน็ตแล้วรอ ~1 นาที)"
_SYNC_CACHE: list = [0.0, True]


def _ntp_synced() -> bool:
    """timedatectl บอกว่าตั้งเวลาจากเน็ตแล้ว · อ่านได้ไม่เกินนาทีละครั้ง · อ่านไม่ได้ (วินโดวส์) = ไม่เตือน."""
    from aipc.doctor.hardware import WARN
    from aipc.doctor.ready import check_clock

    if time.monotonic() - _SYNC_CACHE[0] > 60:
        _SYNC_CACHE[:] = [time.monotonic(), check_clock().status != WARN]
    return _SYNC_CACHE[1]


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
    gcalChanged = Signal()  # noqa: N815 · ปฏิทิน Google (การ์ด 0014) และวันหยุดไทย (0033)
    _gcal_done = Signal(object)
    appInstallChanged = Signal()  # noqa: N815 · ติดตั้งแอป (การ์ด 0054)
    appInstallDone = Signal("QVariantMap")  # noqa: N815 · การ์ดผล (ติดตั้ง/เปิดแล้ว หรือเหตุที่ไม่สำเร็จ)
    _app_done = Signal(object)
    _app_progress = Signal(object)
    _hol_done = Signal(object)

    def __init__(self, executor=None, root: Path = Path("/"), reminders_path=None, clock=None,
                 run_timer: bool = True, llm_ready=None, forge=None, user_skills=None,
                 weather=None, claude_on=None, weather_on=None, gcal=None,
                 gcal_alert_min=None, holidays=None, time_synced=None, chat_mode=None,
                 chat_switch=None, installer=None):  # fmt: skip
        super().__init__()
        # นาฬิกาตั้งจากเน็ตแล้วไหม (ตรวจทั้งระบบ 1.1: แบต RTC 0.00V → บูตไม่มีเน็ต = เวลาค้างที่ตอนปิดเครื่อง) ·
        # ไม่ได้ตั้ง = การ์ดเวลา/นัดบอกว่าเวลาอาจไม่ตรง (H5) · เทสต์ที่ใส่นาฬิกาปลอม = ถือว่าตั้งแล้ว
        self._time_synced = time_synced or ((lambda: True) if clock is not None else _ntp_synced)
        # ปฏิทิน Google แบบอ่านอย่างเดียว (การ์ด 0014 · aipc.skills.gcal.GoogleCalendar)
        # · None = ไม่มี (หน้า Login)
        self._gcal = gcal
        self._gcal_busy = False
        self._gcal_msg = ""  # ผลการเชื่อมต่อ/ดึงครั้งล่าสุดที่ผู้ใช้สั่ง (แสดงในหน้าตั้งค่า)
        # ลองดึงเองครั้งล่าสุดเมื่อไหร่ · ออฟไลน์แล้วถามนัดซ้ำ ๆ ต้องไม่ลองดึงทุกครั้ง (สมุดบันทึกส่งออกจะรก)
        self._gcal_tried = None
        self._gcal_done.connect(self._on_gcal_done)
        # เตือนนัด Google ก่อนเวลากี่นาที (การ์ด 0032 · ค่าตั้งในหน้าตั้งค่า · 0 = ไม่เตือน)
        self._gcal_alert_min = gcal_alert_min or (lambda: 10)
        # วันหยุดไทย (การ์ด 0033 · GoogleCalendar ของปฏิทินสาธารณะ) · None = ไม่มี (หน้า Login)
        self._hol = holidays
        self._hol_busy = False
        self._hol_msg = ""
        self._hol_done.connect(self._on_hol_done)
        # "llm" พร้อมเมื่อ llama-server ของผู้ใช้ตอบได้จริง (ChatController) · ไม่ใช่ค่าคงที่ (H5)
        self._llm_ready = llm_ready or (lambda: False)
        # แชท 2 แบบ (การ์ด 0053): แชทงานส่ง Claude ได้แม้ AI ในเครื่องยังไม่พร้อม
        # chat_switch(kind, ค่า) → (ok, ข้อความ)
        self._chat_mode = chat_mode or (lambda: "general")
        self._chat_switch = chat_switch
        # ติดตั้งแอป (การ์ด 0054): installer(คำขอ) → {"ok", "message"} · ตัวจริง = ตัวติดตั้ง root ผ่าน sudo
        # (aipc.accounts.apphelper) · ไม่ใช่ Linux = จำลองและบอกว่าจำลอง (H5)
        self._installer = installer
        self._installing = ""  # ชื่อแอปที่กำลังติดตั้ง ("" = ไม่มี)
        self._install_pct, self._install_stage = -1.0, ""  # -1 = ยังไม่รู้ (ยังไม่มีตัวเลขจาก apt)
        self._app_done.connect(self._on_app_installed)
        self._app_progress.connect(self._on_app_progress)
        from aipc.skills import actions, manifest, reminders

        # สกิลอัตโนมัติ (การ์ด 0017): forge(คำขอ, skills=, check=, revise=) → forge.Proposal
        # · None = ไม่มี Claude
        self._forge = forge
        self._claude_on = claude_on or (lambda: True)  # สวิตช์ Claude ในหน้าตั้งค่า (ผู้ใช้ปิดเองได้)
        self._forging = False
        self._voice_forges: set[str] = set()  # การ์ด 0030: คำขอที่เริ่มจากเสียง (ไม่สำเร็จ = ไม่ส่งต่อ)
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
        self._weather_on = weather_on or (lambda: True)  # สวิตช์อากาศในหน้าตั้งค่า (2026-10-07)
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
            # ดึงปฏิทิน Google ตอนเข้าสู่ระบบ (เบื้องหลัง)
            if self._gcal is not None and self._gcal.connected:
                self._gcal_refresh()
            # วันหยุดไทย (การ์ด 0033): สำเนาเก่ากว่า 7 วัน = ดึงใหม่
            if self._hol is not None and self._hol.stale():
                self._hol_refresh(True)

    # ---------- ปฏิทิน Google แบบอ่านอย่างเดียว (การ์ด 0014) ----------

    def _gcal_refresh(self, link: str | None = None) -> bool:
        """ดึงใหม่ (หรือเชื่อมต่อด้วยลิงก์ใหม่) ในเธรดแยก · หน้าจอไม่ค้างระหว่างรอเน็ต · กำลังดึงอยู่ = ไม่ซ้อน."""
        import threading

        from aipc.skills import gcal

        if self._gcal is None or self._gcal_busy:
            return False
        self._gcal_busy = True
        self._gcal_tried = self._now()
        self.gcalChanged.emit()

        def work():
            try:
                r = self._gcal.connect(link) if link is not None else self._gcal.sync()
            except Exception as e:  # noqa: BLE001 · เธรดเบื้องหลังห้ามล้มเงียบ (H2) · บอกผู้ใช้แทน
                r = gcal.SyncResult(False, 0, f"ดึงปฏิทินไม่สำเร็จ: {e}")
            self._gcal_done.emit(r)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _on_gcal_done(self, result) -> None:
        self._gcal_busy = False
        self._gcal_msg = result.message
        self.gcalChanged.emit()
        self.remindersChanged.emit()  # นัดถัดไปที่หน้าแรกรวมนัด Google ด้วย

    def _gcal_between(self, start, days: int) -> list:
        """นัด Google + วันหยุดไทย (ถ้าเปิด) ในช่วงวัน · ส่วน "นัดถัดไป" ไม่รวมวันหยุด (ไม่ใช่นัด)."""
        out = self._gcal.between(start, days) if self._gcal is not None else []
        return out + (self._hol.between(start, days) if self._hol is not None else [])

    def _gcal_upcoming(self, now) -> list:
        return self._gcal.upcoming(now) if self._gcal is not None else []

    def _gcal_note(self, now) -> str:
        """บรรทัดบอกที่มาและความสด (H5) · ไม่ได้เชื่อมต่อ = "" · สำเนาเก่ากว่า 30 นาที = ดึงใหม่เบื้องหลัง."""
        g = self._gcal
        if g is None or not g.connected:
            return ""
        from aipc.skills.gcal import STALE

        if g.stale(now) and (self._gcal_tried is None or now - self._gcal_tried > STALE):
            self._gcal_refresh()
        if g.last_sync is None:
            return "ปฏิทิน Google: ยังดึงไม่สำเร็จ" + (f" ({g.error})" if g.error else "")
        at = g.last_sync.astimezone()
        when = (
            f"{at:%H:%M} น."
            if at.date() == now.date()
            else f"{thaidate.short_date(at)} {at:%H:%M} น."
        )
        note = f"ปฏิทิน Google: ข้อมูลเมื่อ {when}"
        if g.old(now):
            note += " · เก่ากว่า 1 วัน"
        if g.error:
            note += " · ดึงครั้งล่าสุดไม่สำเร็จ"
        return note

    @Property(bool, constant=True)
    def gcalAvailable(self) -> bool:  # noqa: N802
        return self._gcal is not None

    @Property(bool, notify=gcalChanged)
    def gcalConnected(self) -> bool:  # noqa: N802
        return self._gcal is not None and self._gcal.connected

    @Property(str, notify=gcalChanged)
    def gcalHint(self) -> str:  # noqa: N802
        return self._gcal.hint if self._gcal is not None else ""

    @Property(bool, notify=gcalChanged)
    def gcalBusy(self) -> bool:  # noqa: N802
        return self._gcal_busy

    @Property(str, notify=gcalChanged)
    def gcalStatus(self) -> str:  # noqa: N802
        g = self._gcal
        if g is None:
            return ""
        if self._gcal_busy:
            return "กำลังดึงปฏิทินจาก Google…"
        if not g.connected:
            return self._gcal_msg
        if g.last_sync is None:
            return g.error or self._gcal_msg
        at = g.last_sync.astimezone()
        n = len(g.between(at.date(), 60))
        text = f"ดึงล่าสุด {thaidate.short_date(at)} {at:%H:%M} น. · {n} นัดในช่วง 60 วัน"
        return text + (f" · ครั้งล่าสุดดึงไม่ได้: {g.error}" if g.error else "")

    @Slot(str, result=bool)
    def gcalConnect(self, link: str) -> bool:  # noqa: N802
        """เชื่อมต่อด้วยลิงก์ที่ผู้ใช้วาง · ลองดึงจริงก่อน สำเร็จแล้วจึงจำลิงก์ (aipc.skills.gcal)."""
        return self._gcal_refresh(link)

    @Slot(result=bool)
    def gcalSyncNow(self) -> bool:  # noqa: N802
        return self._gcal is not None and self._gcal.connected and self._gcal_refresh()

    # ---------- วันหยุดไทย (การ์ด 0033) ----------
    def _hol_refresh(self, on: bool) -> bool:
        import threading

        from aipc.skills import gcal

        if self._hol is None or self._hol_busy:
            return False
        if not on:
            self._hol.disconnect()
            self._hol_msg = "ปิดแล้ว · ลบสำเนาวันหยุดออกจากเครื่องแล้ว"
            self.gcalChanged.emit()
            return True
        self._hol_busy = True
        self.gcalChanged.emit()

        def work():
            try:
                r = self._hol.connect(gcal.HOLIDAYS_TH)
            except Exception as e:  # noqa: BLE001 · เธรดเบื้องหลังห้ามล้มเงียบ (H2)
                r = gcal.SyncResult(False, 0, f"ดึงวันหยุดไม่สำเร็จ: {e}")
            self._hol_done.emit(r)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _on_hol_done(self, result) -> None:
        self._hol_busy = False
        self._hol_msg = result.message
        self.gcalChanged.emit()

    @Property(bool, constant=True)
    def holidaysAvailable(self) -> bool:  # noqa: N802
        return self._hol is not None

    @Property(bool, notify=gcalChanged)
    def holidaysOn(self) -> bool:  # noqa: N802
        return self._hol is not None and self._hol.connected

    @Property(bool, notify=gcalChanged)
    def holidaysBusy(self) -> bool:  # noqa: N802
        return self._hol_busy

    @Property(str, notify=gcalChanged)
    def holidaysStatus(self) -> str:  # noqa: N802
        h = self._hol
        if h is None:
            return ""
        if self._hol_busy:
            return "กำลังดึงวันหยุดจาก Google…"
        if h.connected and h.last_sync is not None:
            at = h.last_sync.astimezone()
            text = f"ดึงล่าสุด {thaidate.short_date(at)} {at:%H:%M} น. · ดึงใหม่สัปดาห์ละครั้ง"
            return text + (f" · ครั้งล่าสุดดึงไม่ได้: {h.error}" if h.error else "")
        return self._hol_msg

    @Slot(bool, result=bool)
    def setHolidays(self, on: bool) -> bool:  # noqa: N802
        """สวิตช์วันหยุดไทย: เปิด = ดึงปฏิทินสาธารณะ (เบื้องหลัง) · ปิด = ลบสำเนา (H3)."""
        return self._hol_refresh(bool(on))

    def _holidays(self, now) -> list:
        """วันหยุดและวันสำคัญที่ยังไม่ผ่าน (รวมวันนี้) จากสำเนา · เรียงตามวัน."""
        if self._hol is None or not self._hol.connected:
            return []
        today = now.date()
        return [e for e in self._hol.between(today, 400) if e.when.date() >= today]

    def _hol_date(self, d) -> str:
        return f"{thaidate.short_date(d)} {thaidate.year(d)}"

    def _holiday_until(self, text: str, now) -> dict | None:
        """ "อีกกี่วันจะถึงวันมาฆบูชา" ที่ไม่อยู่ในรายการวันตายตัว → หาในปฏิทินวันหยุด (การ์ด 0033)."""
        from aipc.skills import agenda

        target = agenda.until_target(text)
        if target is None or self._hol is None or not self._hol.connected:
            return None
        key = agenda.holiday_key(target)
        if not key or key.startswith("หยุด"):
            return None  # "อีกกี่วันถึงวันหยุด" = _holiday_card
        hits = [e for e in self._holidays(now)
                if agenda.holiday_match(key, e.what)
                and ("ชดเชย" in key or not e.what.startswith("วันหยุดชดเชย"))]  # fmt: skip
        if not hits and not agenda.is_holiday_name(target):
            return None  # ไม่ใช่ชื่อวันหยุด ("นัดโทรหาหมอ" "วันพระ" "วันที่ 25") → ทางเดิม ไม่ตอบว่า "ยังไม่มีข้อมูล"
        if not hits:
            return self._plain("clock", f"ยังไม่มีข้อมูล{target}", [
                "ปฏิทินวันหยุดของ Google ยังไม่มีวันนี้ในช่วง 1 ปีข้างหน้า "
                "(วันทางจันทรคติของปีหน้ามักมีหลังประกาศทางการ) · ไม่เดาวันที่",
            ])  # fmt: skip
        e = hits[0]
        n = (e.when.date() - now.date()).days
        title = f"อีก {n} วันถึง{e.what}" if n else f"วันนี้คือ{e.what}"
        kind = "วันหยุดราชการ" if e.kind == "holiday" else "วันสำคัญ (ไม่ได้หยุด)"
        return self._plain(
            "clock", title, [f"{self._hol_date(e.when)} · {kind} · จากปฏิทินวันหยุดของ Google"]
        )

    def _holiday_card(self, text: str) -> dict | None:
        """วันหยุดถัดไป · อีกกี่วันถึงวันหยุด · ช่วงวันนี้มีวันหยุดไหม (การ์ด 0033) · ไม่ใช่คำถามวันหยุด = None."""
        from aipc.skills import agenda

        now = self._now()
        nxt = agenda.asks_next_holiday(text)
        rng = None if nxt else agenda.holiday_range(text, now.date())
        if not nxt and rng is None:
            return None
        if self._hol is None:
            return None
        if not self._hol.connected:
            hint = "เปิดได้ที่หน้าตั้งค่า ส่วน “ปฏิทิน Google” · ดึงปฏิทินสาธารณะ ไม่ส่งข้อมูลของคุณ"
            return self._plain("clock", "ยังไม่ได้เปิดปฏิทินวันหยุดไทย", [hint])
        if nxt:
            public = [e for e in self._holidays(now) if e.kind == "holiday"]
            if not public:
                return self._plain(
                    "clock", "ยังไม่มีข้อมูลวันหยุดถัดไป", ["ปฏิทินวันหยุดของ Google ยังไม่มีข้อมูลช่วงนี้"]
                )
            first = public[0]
            n = (first.when.date() - now.date()).days
            title = f"วันนี้เป็นวันหยุด: {first.what}" if n == 0 else f"วันหยุดถัดไป: {first.what}"
            lines = [f"{self._hol_date(first.when)} · " + ("วันนี้" if n == 0 else f"อีก {n} วัน")]
            lines += [f"ถัดไป: {self._hol_date(e.when)} · {e.what}" for e in public[1:3]]
            return self._plain("clock", title, lines)
        days = [e for e in self._hol.between(rng.start, rng.days) if e.kind == "holiday"]
        day = thaidate.short_date(rng.start)
        span = (
            day
            if rng.days == 1
            else f"{day}–{thaidate.short_date(rng.start + timedelta(days=rng.days - 1))}"
        )
        if not days:
            return self._plain("clock", f"{rng.label} ({span}) ไม่มีวันหยุดราชการ", [])
        return self._plain("clock", f"{rng.label} ({span}) มีวันหยุด {len(days)} วัน",
                           [f"{self._hol_date(e.when)} · {e.what}" for e in days])  # fmt: skip

    @Slot()
    def gcalDisconnect(self) -> None:  # noqa: N802
        if self._gcal is None or self._gcal_busy:
            return
        self._gcal.disconnect()
        self._gcal_msg = "เลิกเชื่อมต่อแล้ว · ลบลิงก์และสำเนานัดจาก Google ออกจากเครื่องนี้แล้ว"
        self.gcalChanged.emit()
        self.remindersChanged.emit()

    def _badge(self, skill, reason: str) -> dict:
        badge = {"name": skill.name, "reason": reason, "worker": self.WORKER_LABEL[skill.worker]}
        if self._is_user(skill.id):  # สกิลที่ Claude สร้าง: การ์ดมีปุ่มลบ / ไม่ใช่แบบนี้ (การ์ด 0017 ชั้นที่ 2)
            badge.update(forgedId=skill.id, forgedVersion=self._user.info(skill.id)["version"])
        return badge

    def _is_user(self, skill_id: str) -> bool:
        return self._user is not None and all(s.id != skill_id for s in self._builtin)

    def available(self) -> set[str]:
        work = self._chat_mode() == "work"
        return set(self.AVAILABLE) | ({"llm"} if self._llm_ready() or work else set())

    @staticmethod
    def _tile_examples(skill) -> list[str]:
        """ตัวอย่างคำพูด 2 ข้อแรกสำหรับไทล์หน้า Skill (การ์ด 0041) · หน้าจออังกฤษ: แสดงเฉพาะที่มีคำแปล
        (คำแปลที่ใส่ไว้ผ่านตัวแปลงคำสั่งอังกฤษแล้ว) · ไม่มีคำแปล = ไม่แสดงประโยคไทยปนในหน้าอังกฤษ"""
        out = [tr(e) for e in skill.examples[:2]]
        return [e for e in out if not i18n.THAI.search(e)] if i18n.lang() == "en" else out

    @staticmethod
    def _command_text(c) -> str:
        """คำสั่งของสกิลประจำเว็บสำหรับหน้า Skill: คำพูด → ทำอะไร (เห็นคีย์/ตัวเลือกจริงที่ไฟล์เขียน · H5)."""
        what = f"กดคีย์ {c.arg}" if c.kind == "key" else f"คลิกปุ่ม {c.arg}"
        ask = " · ยืนยันก่อน" if c.confirm else ""
        return " / ".join(f"“{p}”" for p in c.phrases) + f" → {what}{ask}"

    @Property("QVariantList", notify=skillsChanged)
    def skills(self) -> list:
        out = []
        for s in self._skills:
            missing = [n for n in s.needs if n not in self.available()]
            out.append({
                # แปลตอนแสดง (การ์ด 0039) · สกิลที่ Claude สร้างไม่มีคำแปล = แสดงภาษาเดิม
                "id": s.id, "name": tr(s.name), "description": tr(s.description),
                "worker": tr(self.WORKER_LABEL[s.worker]),
                "permissions": [tr(p) for p in s.permission_labels()],
                "ready": not missing, "missing": [tr(self.NEED_LABEL[n]) for n in missing],
                "byClaude": self._is_user(s.id),
                "examples": self._tile_examples(s),
                "commands": [self._command_text(c) for c in s.commands],  # สกิลประจำเว็บ (การ์ด 0046)
            })  # fmt: skip
        return out

    @Property(bool, constant=True)
    def simulated(self) -> bool:
        return self._exec.dry_run

    # ---------- นัดหมาย (การ์ดออกแบบ 0001) ----------

    @staticmethod
    def _when_text(dt) -> str:
        return f"{thaidate.short_date(dt)} {thaidate.year(dt)} · {dt:%H:%M} น."

    @staticmethod
    def _repeat_text(r) -> str:
        from aipc.skills.when import repeat_name

        return f" · ซ้ำ{repeat_name(r.repeat)}" if getattr(r, "repeat", "") else ""

    def _item_when(self, r) -> str:
        """เวลาของนัด · นัดทั้งวันจาก Google ไม่มีเวลา (การ์ด 0014)."""
        if getattr(r, "all_day", False):
            return f"{thaidate.short_date(r.when)} {thaidate.year(r.when)} · ทั้งวัน"
        return self._when_text(r.when)

    @staticmethod
    def _source_text(r) -> str:
        source = getattr(r, "source", "")
        if source == "holidays":  # การ์ด 0033: แยกวันหยุดราชการกับวันสำคัญที่ไม่ได้หยุด
            return " · วันหยุด" if getattr(r, "kind", "") == "holiday" else " · วันสำคัญ"
        return " · Google" if source == "google" else ""

    @staticmethod
    def _is_past(r, now) -> bool:
        """นัดทั้งวันผ่านไปเมื่อวันนั้นจบ ไม่ใช่ตอนเที่ยงคืนต้นวัน."""
        end = r.end if getattr(r, "all_day", False) else r.when
        return getattr(r, "fired", False) or end < now

    def _reminder_dict(self, r) -> dict:
        when = self._item_when(r) + self._repeat_text(r) + self._source_text(r)
        return {"id": r.id, "what": r.what, "when": when}

    def _upcoming_all(self, now) -> list:
        """นัดที่ยังไม่ถึงเวลา: นัดในเครื่อง + นัดจากปฏิทิน Google (ถ้าเชื่อมต่อ) · เรียงตามเวลา."""
        return sorted([*self._store.upcoming(now), *self._gcal_upcoming(now)], key=lambda r: r.when)

    @Property("QVariantList", notify=remindersChanged)
    def upcoming(self) -> list:
        return [self._reminder_dict(r) for r in self._upcoming_all(self._now())]

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

        # ไฟล์นัดในเครื่องเสีย = หยุดแค่นัดในเครื่อง · เตือนนัด Google ยังทำ
        # (เดิม return ก่อน → เตือน Google หยุดเงียบ · ตรวจทั้งระบบ 2026-10-18 ข้อ 3.9)
        if not self._store.broken:
            t = reminders.tick(self._store, self._now())
            for r in t.due:
                self.reminderDue.emit(self._reminder_dict(r))
            if t.save_failed:
                self._save_failed = True
            if t.due or t.save_failed:
                self.remindersChanged.emit()
        self._gcal_auto_sync()
        self._gcal_tick()

    def _gcal_auto_sync(self) -> None:
        """ดึงปฏิทิน Google เองทุก 15 นาทีระหว่างเข้าระบบ (การ์ด 0051) · นับจากครั้งที่ลองล่าสุด
        (ออฟไลน์ = ลองใหม่รอบหน้า ไม่ถี่กว่านี้) · ไม่ได้เชื่อมต่อ = ไม่ทำ."""
        from aipc.skills.gcal import AUTO_SYNC

        g = self._gcal
        if g is None or not g.connected:
            return
        last = [t for t in (self._gcal_tried, g.last_sync) if t is not None]
        if not last or self._now() - max(last) >= AUTO_SYNC:
            self._gcal_refresh()

    GCAL_ALERT_MAX = (
        3  # การ์ด 0032: นัดพร้อมกันหลายนัด = เตือนทีละไม่เกิน 3 + บอกที่เหลือ (ไม่อ่านออกเสียงยาวเหยียด)
    )

    def _gcal_tick(self) -> None:
        """เตือนนัดจากปฏิทิน Google ล่วงหน้า (การ์ด 0032).

        อ่านจากสำเนาในเครื่อง ไม่ใช้เน็ต · เตือนแล้วจำไว้ไม่เตือนซ้ำ
        """
        import math

        g = self._gcal
        minutes = self._gcal_alert_min()
        if g is None or minutes <= 0:
            return
        now = self._now()
        due = g.due_alerts(now, timedelta(minutes=minutes))
        if not due:
            return
        at = g.last_sync.astimezone() if g.last_sync else None
        source = " · ปฏิทิน Google" + (f" (ข้อมูลเมื่อ {at:%H:%M} น.)" if at else "")
        for e in due[: self.GCAL_ALERT_MAX]:
            left = max(1, math.ceil((e.when - now).total_seconds() / 60))
            self.reminderDue.emit({"id": e.id, "what": e.what, "title": f"อีก {left} นาที",
                                   "when": self._item_when(e) + source})  # fmt: skip
        if len(due) > self.GCAL_ALERT_MAX:
            more = len(due) - self.GCAL_ALERT_MAX
            self.reminderDue.emit({"id": "g:more", "what": f"และอีก {more} นัดจากปฏิทิน Google",
                                   "title": "นัดใกล้ถึงเวลา",
                                   "when": "ถาม “วันนี้มีนัดอะไร” เพื่อดูทั้งหมด"})  # fmt: skip
        g.mark_alerted(due, now)

    def _clock_card(self, text: str) -> dict | None:
        """ "ตอนนี้กี่โมง" · None = ไม่ใช่คำถามเวลา (agenda.asks_time)."""
        from aipc.skills import agenda

        if not agenda.asks_time(text):
            return None
        now = self._now()
        lines = [f"{thaidate.long_date(now)} · ตามนาฬิกาของเครื่องนี้"]
        if not self._time_synced():
            lines.append(UNSYNCED)
        return self._plain("clock", f"ตอนนี้ {thaidate.clock(now)} น.", lines)

    def _cancel_card(self, text: str) -> dict | None:
        """ "ยกเลิกนัดส่งรายงาน" · "ลบนัดทั้งหมด" → แสดงนัดที่จะลบ แล้วรอยืนยัน · None = ไม่ใช่คำขอลบนัด."""
        from aipc.skills import agenda

        key = agenda.cancel_target(text)
        if key is None:
            return None
        if self._store.broken:
            return self._plain("reminder", "ลบนัดไม่ได้ตอนนี้", [self.reminderWarning])
        live = [r for r in self._store.items if not r.fired]
        hits = [r for r in live if not key or key in (w := r.what.replace(" ", "")) or w in key]

        def line(r):
            return f"{self._when_text(r.when)} · {r.what}{self._repeat_text(r)}"

        google = [e for e in self._gcal_upcoming(self._now())
                  if key and (key in (w := e.what.replace(" ", "")) or w in key)]  # fmt: skip
        if not hits and google:  # การ์ด 0014: เครื่องนี้อ่านปฏิทิน Google อย่างเดียว ลบไม่ได้
            lines = ["เครื่องนี้อ่านปฏิทิน Google อย่างเดียว · ลบหรือแก้ได้ในแอป Google Calendar"]
            return self._plain("reminder", f"นัด “{key}” อยู่ในปฏิทิน Google",
                               lines + [self._reminder_line(e) for e in google[:5]])  # fmt: skip
        if not hits:
            names = [line(r) for r in live[:5]]
            title = f"ไม่พบนัด “{key}”" if key and live else "ยังไม่มีนัดให้ลบ"
            return self._plain("reminder", title, names and ["นัดที่มีอยู่:", *names])
        self._counter += 1
        token = f"r{self._counter}"
        self._pending[token] = ("cancel", [r.id for r in hits])
        lines = [line(r) for r in hits]
        if not key and self._gcal_upcoming(self._now()):
            lines.append("นัดจากปฏิทิน Google ไม่ถูกลบ (เครื่องนี้อ่านอย่างเดียว)")
        card = self._plain("reminder", f"ลบนัด {len(hits)} รายการ ใช่ไหม", lines)
        card["confirmToken"] = token
        if reminder := next((s for s in self._skills if s.id == "reminder"), None):
            card["badge"] = self._badge(reminder, "ขอลบนัด · ลบด้วยโค้ดหลังกดยืนยัน")
        return card

    def _reminder_line(self, r) -> str:
        return f"{self._item_when(r)} · {r.what}{self._repeat_text(r)}{self._source_text(r)}"

    def _with_reminder_badge(self, card: dict, why: str) -> dict:
        if reminder := next((s for s in self._skills if s.id == "reminder"), None):
            card["badge"] = self._badge(reminder, why)
        return card

    def _next_card(self, text: str) -> dict | None:
        """ "นัดถัดไปของฉันคืออะไร" → นัดที่ยังไม่ถึงเวลา (ไม่เกิน 10) · None = ไม่ใช่คำถามนี้."""
        from aipc.skills import agenda

        if not agenda.asks_next(text):
            return None
        now = self._now()
        up = self._upcoming_all(now)
        title = f"นัดที่ยังไม่ถึงเวลา {len(up)} นัด" if up else "ยังไม่มีนัดที่รออยู่"
        lines = [self._reminder_line(r) for r in up[:10]] or [
            "จดนัดได้เลย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”"
        ]
        if note := self._gcal_note(now):
            lines.append(note)
        return self._with_reminder_badge(
            self._plain("reminder", title, lines), "ถามนัด · อ่านจากนัดที่บันทึกไว้"
        )

    def _move_card(self, text: str) -> dict | None:
        """ "เลื่อนนัดประชุมไปบ่ายสาม" → ยังเลื่อนเองไม่ได้ บอกวิธีทำด้วยสองคำสั่ง (ไม่จดนัดใหม่ผิด ๆ)."""
        from aipc.skills import agenda

        rest = agenda.move_target(text)
        if rest is None:
            return None
        hits = [r for r in self._store.items
                if not r.fired and r.what.replace(" ", "").removeprefix("นัด") in rest]  # fmt: skip
        lines = ["ทำได้ 2 ขั้น: พิมพ์ “ยกเลิกนัด…” แล้วจดนัดใหม่ เช่น “พรุ่งนี้บ่ายสามประชุม”"]
        lines += [self._reminder_line(r) for r in hits[:5]]
        google = [e for e in self._gcal_upcoming(self._now())
                  if e.what.replace(" ", "").removeprefix("นัด") in rest]  # fmt: skip
        if google:  # การ์ด 0014: นัดจาก Google แก้ได้ในแอป Google Calendar เท่านั้น
            lines.append("นัดจากปฏิทิน Google เลื่อนได้ในแอป Google Calendar เท่านั้น:")
            lines += [self._reminder_line(e) for e in google[:5]]
        card = self._plain("reminder", "ยังเลื่อนนัดให้ไม่ได้", lines)
        return self._with_reminder_badge(card, "ขอเลื่อนนัด · ยังไม่รองรับ จึงไม่จดนัดใหม่")

    def _until_card(self, text: str) -> dict | None:
        """ "อีกกี่วันจะถึงปีใหม่" → นับจากวันที่ของเครื่อง · None = ไม่ใช่คำถามนี้."""
        from aipc.skills import agenda

        now = self._now()
        hit = agenda.days_until(text, now.date())
        if hit is None:
            return self._holiday_until(text, now)
        name, d = hit
        n = (d - now.date()).days
        title = f"อีก {n} วันถึง{name}" if n else f"วันนี้คือ{name}"
        when = f"{thaidate.short_date(d)} {thaidate.year(d)}"
        return self._plain(
            "clock", title, [f"{when} · นับจากวันที่ของเครื่องนี้ ({thaidate.short_date(now)})"]
        )

    def _agenda_card(self, text: str) -> dict | None:
        """ "วันนี้ต้องทำอะไร" (ฟีเจอร์ข้อ 5) · None = ไม่ใช่คำถามเรื่องตารางนัด."""
        from aipc.skills import agenda

        q = agenda.parse(text, self._now().date())
        if q is None:
            return None
        now = self._now()
        if q.days == 0:  # วันที่ไม่มีจริง (การ์ด 0037) · ไม่เดาวันใกล้เคียง
            card = self._plain("reminder", f"ไม่มี{q.label}", ["ลองระบุวันที่ใหม่ เช่น “วันที่ 30 มีนัดอะไร”"])
            card["route"] = "agenda"
            return card
        # นัดในเครื่อง + นัดจากปฏิทิน Google ในช่วงเดียวกัน (การ์ด 0014 · อ่านจากสำเนา ไม่ต้องใช้เน็ต)
        items = self._range_items(q)
        day = thaidate.short_date(q.start)
        span = (
            day
            if q.days == 1
            else f"{day}–{thaidate.short_date(q.start + timedelta(days=q.days - 1))}"
        )
        reminder = next((s for s in self._skills if s.id == "reminder"), None)
        card = self._plain("reminder", f"{q.label} ({span}) มี {len(items)} นัด" if items
                           else f"{q.label} ({span}) ยังไม่มีนัด")  # fmt: skip
        note = self._gcal_note(now)
        g = self._gcal
        if (
            note and g is not None and g.last_sync is not None
        ):  # ช่วงยาวเกินสำเนา Google (เดือนหน้า) = บอก (H5)
            from aipc.skills.gcal import FUTURE

            until = (g.last_sync + FUTURE).astimezone().date()
            if q.start + timedelta(days=q.days - 1) > until:
                note += f" · มีข้อมูลถึง {thaidate.short_date(until)}"
        if reminder is not None:
            why = "ถามตารางนัด · อ่านจากนัดที่บันทึกไว้" + (" + สำเนาปฏิทิน Google" if note else "")
            card["badge"] = self._badge(reminder, why)
        card["lines"] = [
            f"{'✓ ' if self._is_past(r, now) else ''}{self._reminder_line(r)}" for r in items
        ] or ["จดนัดได้เลย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”"]
        if note:
            card["lines"].append(note)
        if not self._time_synced():  # "วันนี้" ของเครื่องอาจไม่ใช่วันนี้จริง (ตรวจทั้งระบบ 1.1)
            card["lines"].append(UNSYNCED)
        card["route"] = "agenda"
        return card

    def _range_items(self, q) -> list:
        """นัดในเครื่อง + Google + วันหยุดในช่วงวันของคำถาม · เรียงตามเวลา.

        ใช้ทั้งคำตอบนัดและหน้าปฏิทิน (การ์ด 0038) · สองที่จึงแสดงตรงกันเสมอ
        """
        from aipc.skills import agenda

        return sorted([*agenda.items_for(self._store, q), *self._gcal_between(q.start, q.days)],
                      key=lambda r: r.when)  # fmt: skip

    @Slot(int, int, result="QVariantMap")
    def monthItems(self, year: int, month: int) -> dict:  # noqa: N802
        """ตารางเดือน 6 × 7 ช่อง (เริ่มวันจันทร์) สำหรับหน้าปฏิทิน (การ์ด 0038) · ปี/เดือน 0 = เดือนนี้.

        บรรทัดของแต่ละวันสร้างแบบเดียวกับคำตอบ "…มีนัดอะไร" ทุกตัวอักษร (H5: หน้าจอกับคำตอบไม่มีทางต่างกัน)
        """
        from datetime import date

        from aipc.skills import agenda

        now = self._now()
        if not 1 <= month <= 12 or year < 1:
            year, month = now.year, now.month
        first = date(year, month, 1)
        start = first - timedelta(days=first.weekday())
        cells = []
        for i in range(42):
            d = start + timedelta(days=i)
            items = self._range_items(agenda.Query(d, 1, ""))
            sources = {getattr(r, "source", "") for r in items}
            kinds = {getattr(r, "kind", "") for r in items}
            lines = [
                f"{'✓ ' if self._is_past(r, now) else ''}{self._reminder_line(r)}" for r in items
            ]
            cells.append({
                "day": d.day, "iso": d.isoformat(), "inMonth": d.month == month,
                "today": d == now.date(), "local": "" in sources, "google": "google" in sources,
                "holiday": "holiday" in kinds, "observance": "observance" in kinds, "lines": lines,
                "label": thaidate.long_date(datetime.combine(d, datetime.min.time())),
            })  # fmt: skip
        note = ""
        g = self._gcal
        if g is not None and g.connected and g.last_sync is not None:
            from aipc.skills.gcal import FUTURE

            until = (g.last_sync + FUTURE).astimezone().date()
            last = start + timedelta(days=41)
            if last > until:
                when = f"{thaidate.short_date(until)} {thaidate.year(until)}"
                note = f"นัดจาก Google มีข้อมูลถึง {when}"
        title = f"{thaidate.month_name(month)} {thaidate.year(year)}"
        return {"year": year, "month": month, "title": title, "cells": cells, "note": note,
                "todayIso": now.date().isoformat()}  # fmt: skip

    def _agenda_step(self, step_text: str) -> list[str]:
        """ขั้น "บอกนัดวันนี้/พรุ่งนี้/สัปดาห์นี้" ของสกิล → บรรทัดเดียวกับคำตอบ "…มีนัดอะไร" (การ์ด 0034)."""
        label = step_text.removeprefix("บอกนัด")
        card = self._agenda_card(f"{label}มีนัดอะไร")
        if card is None:  # ไม่ควรเกิด: ตัวตรวจสกิลรับแค่ 3 ช่วงนี้
            return [f"อ่านนัด{label}ไม่ได้"]
        return [card["title"], *card["lines"]]

    def _title_card(self, text: str) -> dict | None:
        """ "นัดหมอวันไหน" · "มีนัดกับหมอไหม" (การ์ด 0037) → นัดที่ยังไม่ถึงซึ่งชื่อมีคำนั้น · ไม่ใช่คำถามนี้ = None."""
        from aipc.skills import agenda

        hit = agenda.title_query(text)
        if hit is None:
            return None
        name, strict = hit
        now = self._now()
        found = [r for r in self._upcoming_all(now) if name in r.what.replace(" ", "")]
        if not found and not strict:
            return None  # "ทีมชาติไทยแข่งครั้งหน้าเมื่อไหร่" ที่ไม่มีนัดชื่อนี้ = ไม่ใช่คำถามนัด
        title = f"นัด “{name}” ที่ยังไม่ถึง {len(found)} นัด" if found else f"ไม่พบนัด “{name}” ที่ยังไม่ถึง"
        lines = [self._reminder_line(r) for r in found[:10]]
        if note := self._gcal_note(now):
            lines.append(note)
        card = self._with_reminder_badge(
            self._plain("reminder", title, lines), "ค้นนัดตามชื่อ · อ่านจากนัดที่บันทึกไว้"
        )
        card["route"] = "agenda"
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
                0, f"เตือนครั้งแรก {self._when_text(w.at)} แล้วตั้งครั้งถัดไปเอง · เลิกเตือน: พิมพ์ “ยกเลิกนัด…”"
            )
        card["lines"].append("วันที่คำนวณด้วยโค้ด ไม่ใช่ให้ AI เดา · ไม่ถูกให้กด “ไม่ใช่” แล้วพิมพ์ใหม่")
        card["confirmToken"] = token
        return card

    # ---------- สกิลแบบขั้นตอน (.md · ข้อเสนอ 2026-09-29 หัวข้อ 10.1) ----------

    def _steps_card(self, route, text: str) -> dict:
        """แสดงทุกขั้นก่อนทำ · มีขั้นที่สั่งเครื่อง = ถามยืนยันครั้งเดียว (ความเสี่ยงของขั้นที่สูงสุด) แล้วทำตามลำดับ."""
        skill = route.skill
        prefix = {"llm": "ถาม AI: ", "say": "บอก: ", "action": "", "agenda": ""}
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
            elif s.kind == "agenda":  # การ์ด 0034: โค้ดอ่านนัด (ในเครื่อง + Google + วันหยุด) · ไม่ใช้ AI
                lines.extend(self._agenda_step(s.text))
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

    @Slot(str, result=str)
    def openSite(self, key: str) -> str:  # noqa: N802
        """ปุ่มแอปที่ใช้บ่อยในหน้าแรก (การ์ด 0031) · ทางเดียวกับพิมพ์ "เปิดยูทูบ" (ตัวสั่งงาน → เบราว์เซอร์ของผู้ช่วย).

        หน้าจอส่งมาได้แค่ชื่อเว็บในรายการ ไม่ใช่ URL (H7) · คืนข้อความผล (บอกเมื่อเปิดด้วยเบราว์เซอร์ปกติแทน)
        """
        from aipc.skills.actions import SITES, Plan

        if key not in SITES:
            return "ไม่มีเว็บนี้ในรายการ"
        out = self._exec.execute(Plan("open_url", {"site": key}, f"เปิด {SITES[key][0]}"))
        return out.message

    def _run_plan(self, plan) -> dict:
        if plan.action == "gcal_sync":
            return self._gcal_sync_card()
        if plan.action == "show_devices":
            return self._devices_card()
        if plan.action in ("chat_mode", "cloud_model"):
            return self._chat_switch_card(plan)
        if plan.action == "missing_app":
            return self._missing_app_card(plan.params["app"])
        out = self._exec.execute(plan)
        if out.simulated:
            title = plan.summary + " (จำลอง)"
        else:
            title = plan.summary if out.ok else out.message
        card = {
            "title": title,
            "chips": [{"text": "จำลอง" if out.simulated else ("ทำแล้ว" if out.ok else "ไม่สำเร็จ"),
                       "kind": "warn" if out.simulated else ("ok" if out.ok else "danger")}],
            # เปิดเว็บ: บอกว่าเปิดในเบราว์เซอร์ไหน (การ์ด 0031) · ข้อความต่างจากหัวเรื่องเท่านั้นถึงแสดง
            "lines": [out.message] if out.simulated or (out.ok and out.message != plan.summary)
                     else [],
            "page": out.page,
        }  # fmt: skip
        if out.undo:
            card["undoToken"] = self._offer_undo(out.undo)
        elif out.ok and not out.simulated and plan.action in ("open_url", "open_app"):
            card["lines"].append("คำสั่งนี้ย้อนกลับไม่ได้ · ปิดหน้าต่างที่เปิดขึ้นมาเองได้")
        return card

    def _devices_card(self) -> dict:
        """สั่ง "มีอุปกรณ์อะไรต่ออยู่" (การ์ด 0051) · ตรวจจริงตอนนี้ บรรทัดละชนิด แล้วพาไปหน้าสุขภาพเครื่อง."""
        from aipc.doctor import devices

        return {"title": "อุปกรณ์ที่ต่ออยู่", "chips": [{"text": "ตรวจแล้ว", "kind": "ok"}],
                "lines": devices.summary(devices.scan(self._root)), "page": "health"}  # fmt: skip

    def _gcal_sync_card(self) -> dict:
        """สั่ง "อัปเดตปฏิทิน" (การ์ด 0051) · ผลจริงมาทีหลังทาง gcalChanged · การ์ดบอกแค่ว่าเริ่มแล้วหรือยัง (H5)."""
        card = {"title": "", "chips": [], "lines": [], "page": ""}
        if self._gcal is None or not self._gcal.connected:
            card["title"] = "ยังไม่ได้เชื่อมต่อปฏิทิน Google"
            card["chips"] = [{"text": "ไม่ได้ทำ", "kind": "warn"}]
            card["lines"] = ["วางลิงก์ iCal ลับได้ที่หน้าตั้งค่า"]
            card["page"] = "settings"
        elif self._gcal_refresh():
            card["title"] = "กำลังดึงปฏิทิน Google ใหม่"
            card["chips"] = [{"text": "ทำแล้ว", "kind": "ok"}]
            card["lines"] = ["นัดใหม่จะขึ้นในหน้าปฏิทินเมื่อดึงเสร็จ"]
        else:
            card["title"] = "กำลังดึงปฏิทิน Google อยู่แล้ว"
            card["chips"] = [{"text": "ทำแล้ว", "kind": "ok"}]
        return card

    def _chat_switch_card(self, plan) -> dict:
        """สลับแชท/โมเดลด้วยเสียงหรือพิมพ์ (การ์ด 0053) · ผลจริงจาก ChatController/UiSettings."""
        if plan.action == "chat_mode":
            kind, value = "mode", plan.params["mode"]
        else:
            kind, value = "model", plan.params["model"]
        if self._chat_switch is None:
            ok, msg = False, "ใช้ได้ในเซสชันจริงเท่านั้น"
        else:
            ok, msg = self._chat_switch(kind, value)
        return {"title": msg, "chips": [{"text": "ทำแล้ว" if ok else "ไม่ได้ทำ",
                                         "kind": "ok" if ok else "warn"}],
                "lines": [], "page": "workspace" if ok and kind == "mode" else ""}  # fmt: skip

    # ---------- แอปที่ไม่มีในเครื่อง (การ์ด 0054) ----------
    # ถามทุกครั้ง ไม่จำคำตอบ (Pakon 2026-10-22): ติดตั้งไหม → ไม่ = เปิดผ่านเว็บไหม → ไม่ = ไม่ทำอะไร
    INSTALL_NOTE = "ติดตั้งแล้วทุกบัญชีในเครื่องใช้ได้ · ใช้เวลาหลายนาทีและต้องต่ออินเทอร์เน็ต"

    def _ask(self, card: dict, pending) -> dict:
        self._counter += 1
        token = f"c{self._counter}"
        self._pending[token] = pending
        card["confirmToken"] = token
        return card

    def _missing_app_card(self, key: str) -> dict:
        from aipc.skills import app_catalog

        entry = app_catalog.load().get(key)
        card = {"kind": "command", "title": "", "chips": [], "lines": [], "page": "",
                "confirmToken": ""}  # fmt: skip
        if entry is None:
            card["title"] = "ไม่พบแอปนี้ในเครื่อง"
        elif entry.apt:
            card.update(title=f"ไม่มี {entry.name} ในเครื่อง · ติดตั้งไหม?", lines=[self.INSTALL_NOTE])
            return self._ask(card, ("app-install", key))
        elif entry.web:
            return self._web_question(entry, card)
        else:
            card["title"] = f"ไม่มี {entry.name} ในเครื่อง"
        return card

    def _web_question(self, entry, card: dict) -> dict:
        card.update(title=f"ไม่มี {entry.name} ในเครื่อง · จะเปิดผ่านเบราว์เซอร์ไหม?",
                    lines=[f"เปิด {entry.web} ในเบราว์เซอร์ของผู้ช่วย"])  # fmt: skip
        return self._ask(card, ("app-web", entry.key))

    def _missing_app_answer(self, step: str, key: str, yes: bool) -> dict:
        from aipc.skills import app_catalog
        from aipc.skills.actions import Plan

        entry = app_catalog.load().get(key)
        card = {"kind": "command", "badge": {}, "title": "", "chips": [], "lines": [], "page": "",
                "confirmToken": ""}  # fmt: skip
        if entry is None:
            card["title"] = "แอปนี้ไม่อยู่ในรายการแล้ว"
        elif step == "app-install" and yes:
            # หน้าจอถาม ตกลง/ยกเลิก อีกครั้งก่อนติดตั้งจริง (Pakon 2026-10-23: ไม่ต้องใส่รหัส)
            card.update(kind="app-install", appInstall=key, appName=entry.name,
                        title=f"กด “ตกลง” เพื่อติดตั้ง {entry.name}")  # fmt: skip
        elif step == "app-install" and entry.web:
            return self._web_question(entry, card)
        elif step == "app-web" and yes:
            say = f"เปิด {entry.name} ผ่านเบราว์เซอร์"
            plan = Plan("open_url", {"url": entry.web, "site": key}, say)
            card.update(self._run_plan(plan))
        else:
            card["title"] = "ไม่ได้ติดตั้งและไม่ได้เปิด"
        return card

    @Property(str, notify=appInstallChanged)
    def installing(self) -> str:
        return self._installing

    @Property(float, notify=appInstallChanged)
    def installPercent(self) -> float:  # noqa: N802
        """เปอร์เซ็นต์รวมจากตัวเลขของ apt (การ์ด 0054 · Pakon 2026-10-23) · -1 = ยังไม่มีตัวเลข."""
        return self._install_pct

    @Property(str, notify=appInstallChanged)
    def installStage(self) -> str:  # noqa: N802
        return self._install_stage

    @Slot(object)
    def _on_app_progress(self, msg) -> None:
        try:
            self._install_pct = float(msg.get("percent", self._install_pct))
        except (TypeError, ValueError):
            return
        self._install_stage = str(msg.get("stage", self._install_stage))
        self.appInstallChanged.emit()

    @Slot(str, result=bool)
    def installApp(self, key: str) -> bool:  # noqa: N802
        """ผู้ดูแลกดติดตั้ง · ทำในเธรดแยก (apt ใช้เวลาหลายนาที) · ผลมาทาง appInstallDone.

        กำลังติดตั้งอยู่ / ไม่อยู่ในรายการ = False
        """
        import sys
        import threading

        from aipc.skills import app_catalog

        entry = app_catalog.load().get(key)
        if self._installing or entry is None or not entry.apt:
            return False
        run = self._installer
        if run is None:
            run = run_apps_helper if sys.platform.startswith("linux") else _simulated_install
        self._installing = entry.name
        self._install_pct, self._install_stage = -1.0, ""
        self.appInstallChanged.emit()
        req = {"app": key}

        def work():
            try:
                r = run(req, self._app_progress.emit)
            except Exception as e:  # noqa: BLE001 · บอกผู้ใช้แทนการค้าง (H2)
                r = {"ok": False, "message": f"ติดตั้งไม่สำเร็จ: {e}"}
            self._app_done.emit((entry, r))

        threading.Thread(target=work, daemon=True).start()
        return True

    @Slot(object)
    def _on_app_installed(self, done) -> None:
        from aipc.skills import command

        entry, r = done
        self._installing = ""
        self.appInstallChanged.emit()
        card = {"kind": "command", "badge": {}, "title": str(r.get("message", "")), "lines": [],
                "page": "", "confirmToken": "",
                "chips": [{"text": "ติดตั้งแล้ว" if r.get("ok") else "ไม่สำเร็จ",
                           "kind": "ok" if r.get("ok") else "danger"}]}  # fmt: skip
        if r.get("ok") and not r.get("simulated"):
            # เปิดเลยด้วยทางเดิมของ "เปิด X" (แอปที่เพิ่งติดตั้งมีไฟล์ .desktop แล้ว)
            cmd = command.parse(f"เปิด{entry.aliases[0]}")
            if cmd is not None and cmd.plan.action == "open_app":
                card["lines"].append(self._run_plan(cmd.plan)["title"])
        self.appInstallDone.emit(card)

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
            return self._plain(
                "needs",
                "สร้างสกิลใหม่ไม่ได้: ปิดการใช้ Claude ไว้",
                ["เปิดได้ที่หน้าตั้งค่า › Claude · ระหว่างปิด ไม่มีข้อมูลออกไป Anthropic"],
            )
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
        by_voice = text in self._voice_forges
        self._voice_forges.discard(text)
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
            if by_voice:  # การ์ด 0030: คีย์ลัดไม่ส่งให้ AI คุย (0027) = ไม่ส่งต่อ
                card.update(fallback=False, voice=True)
                card["lines"].append("สั่งด้วยเสียง: ไม่ส่งต่อให้ Claude ตอบแทน · พิมพ์ในแชทถ้าต้องการ")
            self.forgeDone.emit(card, text)
            return
        self._reload()
        if new.site:  # การ์ด 0046: สกิลประจำเว็บ = บอกว่าพูดอะไรได้ · ทำเมื่อพูดในเว็บนั้น
            v = self._user.info(new.id)["version"]
            what = (
                f"แก้สกิล “{new.name}” แล้ว (รุ่น {v})"
                if revise_id
                else f"สร้างสกิล “{new.name}” แล้ว (Claude สร้าง)"
            )
            says = [c.phrases[0] for c in new.commands][:8]
            say = "พูดในเว็บนี้ได้: " + " · ".join(f"“{p}”" for p in says)
            card = self._plain("command", what, [say], [{"text": "สกิลประจำเว็บ", "kind": "ok"}])
            if by_voice:
                card["voice"] = True
            self.forgeDone.emit(card, text)
            return
        card = dict(self.handleAs(new.id, text))
        v = self._user.info(new.id)["version"]
        note = (f"แก้สกิล “{new.name}” แล้ว (รุ่น {v})" if revise_id
                else f"สร้างสกิลใหม่ “{new.name}” แล้ว (Claude สร้าง) · ครั้งหน้าสั่งแบบนี้ได้เลย")  # fmt: skip
        # การ์ด 0028: บอกประโยคที่พูดผ่านคีย์ลัดแล้วถึงสกิลนี้จริง · เฉพาะสกิลที่ทำด้วยโค้ด
        say = self.voiceExample(new.id)
        spoken = [f"กด Alt+Space แล้วพูดได้: “{say}”"] if say else []
        card["lines"] = [note, *spoken, *card.get("lines", [])]
        if by_voice:
            card["voice"] = True  # หน้าจออ่านผลออกเสียง (การ์ด 0030)
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
        if not md.lstrip("\ufeff \r\n").startswith("---"):  # โน้ต .md ทั่วไป (ปุ่มขึ้นทุกไฟล์ .md)
            return "ไฟล์นี้เป็นโน้ตธรรมดา ไม่ใช่ไฟล์สกิล · ติดตั้งได้เฉพาะไฟล์ที่ส่งออกจากหน้า Skill"
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

    # ---------- สั่งสกิลด้วยเสียง (การ์ด 0028) ----------
    def _voice_skills(self) -> list:
        """สกิลที่สั่งด้วยคีย์ลัดได้: มีขั้นตอนและทำด้วยโค้ดทั้งหมด · สกิลที่ถาม AI ไม่เข้า (สัญญาของการ์ด 0027)."""
        return [s for s in self._skills if s.steps and s.worker == "code"]

    @Slot(str, result=str)
    def voiceSkill(self, text: str) -> str:  # noqa: N802
        """id ของสกิลที่ประโยคตรงเป๊ะกับตัวอย่าง/คำขอที่ใช้สร้าง · "" = ไม่ตรง.

        ใช้ router.repeat_of ตัวเดียวกับแชท (ไม่สนช่องว่างและคำสุภาพหัวท้าย)
        """
        from aipc.skills import router

        m = router.repeat_of(text, self._voice_skills())
        return m.id if m else ""

    def voicePhrases(self) -> list[str]:  # noqa: N802
        """ทาง ข (การ์ด 0028 หัวข้อ 12): ประโยคตัวอย่างของสกิลโค้ดล้วน → hotwords ของตัวถอดคีย์ลัด.

        เรียกจากเธรดของตัวอัดเสียง · อ่านรายการอย่างเดียว
        """
        site = [
            p for s in self._skills if s.site for c in s.commands for p in c.phrases
        ]  # การ์ด 0046
        return [e for s in self._voice_skills() for e in s.examples] + site

    @Slot(str, result=str)
    def voiceExample(self, skill_id: str) -> str:  # noqa: N802
        """ประโยคตัวอย่างแรกที่พูดผ่านคีย์ลัดแล้วถึงสกิลนี้จริง · "" = ไม่มี.

        ตัวอย่างที่ชนคำสั่งเว็บ/คำสั่งเครื่องเดิม (เช่น "เปิดแผนที่ให้หน่อย") ไปทางคำสั่งเดิม จึงไม่บอก (H5)
        """
        from aipc.ui.handsfree import SKILL, route

        skill = next((s for s in self._voice_skills() if s.id == skill_id), None)
        for example in skill.examples if skill else []:
            ways = {route(example, running, self.voiceSkill) for running in (False, True)}
            if ways == {SKILL} and self.voiceSkill(example) == skill_id:
                return example
        return ""

    def _nearest_voice(self, text: str):
        """(สกิล, ประโยคตัวอย่าง) ที่ใกล้ที่สุดเมื่อใกล้พอ · ไม่ใกล้ = (None, "").

        เกณฑ์ใกล้ = FUZZY_CUTOFF ตัวเดียวกับคำสั่งเครื่อง (0.72)
        """
        import difflib

        from aipc.skills import command

        key, best, score = command.normalize(text), (None, ""), 0.0
        for s in self._voice_skills():
            for example in s.examples:
                r = difflib.SequenceMatcher(None, key, command.normalize(example)).ratio()
                if r > score:
                    best, score = (s, example), r
        return best if key and score >= command.FUZZY_CUTOFF else (None, "")

    # ---------- ถามด้วยเสียง ตอบด้วยโค้ด (การ์ด 0029) ----------
    # สุขภาพเครื่องทางเสียง: คำสำคัญของสกิลมี "เครื่อง" เดี่ยว ๆ ("เปิดแอปเครื่องคิดเลข" จะตรง) → ใช้กฎที่เข้มกว่า
    MACHINE_SYMPTOMS = ("ช้า", "อืด", "ค้าง", "ร้อน")
    MACHINE_WORDS = ("อุณหภูมิ", "แรม", "ram", "หน่วยความจำ", "พื้นที่เหลือ", "พัดลม")
    _NET = re.compile(r"(?:อินเทอร์)?เน็ต(?!ฟ)|ไวไฟ|wi-?fi")
    NET_ASK = ("หลุด", "ช้า", "ต่อ", "ล่ม", "ไหม", "มั้ย", "ใช้ได้", "ใช้ไม่ได้")

    @Slot(str, result="QVariantMap")
    def voiceAnswer(self, text: str) -> dict:  # noqa: N802
        """คำถามที่แชทตอบด้วยโค้ดก่อนถึง AI (นาฬิกา สมุดนัด ค้นไฟล์ สุขภาพเครื่อง) · ไม่ตรง = {}.

        ลำดับเดียวกับ _handle · ไม่ใช้ทางที่ส่งออก (อากาศ · สร้างสกิล) · ยกเลิกนัด = การ์ดยืนยันเดิม
        """
        from aipc.skills import english, router
        from aipc.skills.fileintent import file_intent, file_time

        t0 = time.monotonic()
        text = english.to_thai(text) or text  # คำถามอังกฤษทางคีย์ลัด (การ์ด 0040) · ไทยไม่แตะ
        if card := self._unsupported_card(text):
            return self._why(card, t0)
        asks = (self._agenda_card, self._clock_card, self._until_card, self._holiday_card,
                self._cancel_card, self._next_card, self._move_card, self._title_card)  # fmt: skip
        for ask in asks:
            if card := ask(text):
                return self._why(card, t0)
        if label := file_time(text):
            return self._why(self._files_card(text, label), t0)
        if file_intent(text):
            return self._why(self._files_card(text), t0)
        t = text.lower().replace(" ", "")
        machine = next((s for s in self._skills if s.id == "machine-status"), None)
        about_machine = ("เครื่อง" in t and any(w in t for w in self.MACHINE_SYMPTOMS)) or any(
            w in t for w in self.MACHINE_WORDS
        )
        # เน็ต (การ์ด 0042 รอบ 3): "เน็ตหลุดไหม" "ต่อเน็ตอยู่ไหม" · ไม่ใช่ "เน็ตฟลิกซ์" · ต้องเป็นคำถาม/อาการ
        if self._NET.search(t) and any(w in t for w in self.NET_ASK):
            about_machine = True
        if machine is not None and about_machine:
            route = router.Route("skill", machine, "ถามสุขภาพเครื่องด้วยเสียง")
            return self._why(self._card(route, text), t0)
        return {}

    # ---------- คีย์ลัดใช้ได้กับทุกสกิล (การ์ด 0042) ----------
    # ตั้งเตือนต้องขึ้นต้นด้วยคำสั่ง ("เตือน…" "ช่วยเตือน…" "อย่าลืมเตือน…" "นัด…") หรือบอกเวลา + คำของสกิลนัด ·
    # เล่าเรื่อง ("แม่ชอบเตือนให้กินข้าว") ไม่ขึ้นต้นด้วยคำสั่งและไม่มีเวลา = ไม่ใช่
    _REMIND_START = re.compile(r"^(?:(?:ช่วย|อย่าลืม|ขอ|รบกวน)*(?:เตือน|นัด|จดนัด|ปลุก)|อย่าลืม)")
    # เลื่อน/ย้าย/ลบ/ยกเลิกนัด = แก้นัดเดิม ไม่ใช่ตั้งใหม่ (ได้ยินเพี้ยน "เลื่อนนักประชุม…" ก็ไม่สร้างนัดใหม่ · เกณฑ์ V3)
    _EDIT_START = re.compile(r"^(?:ช่วย|ขอ|รบกวน)*(?:เลื่อน|ย้าย|ลบ|ยกเลิก|เปลี่ยน|แก้)")
    _LETTER = re.compile(r"^(?:ช่วย|ขอ|รบกวน)*(?:ร่าง|เขียน)(?:อีเมล์?|จดหมาย|ข้อความ|หนังสือ)")
    # สั่งสรุปด้วยเสียงไม่มีเนื้อความต่อท้าย (พูดแปะข้อความไม่ได้) · กฎแปล/สรุปของแชทต้องมีเนื้อความ →
    # ส่งไปแชทแล้วผู้ใช้วางข้อความต่อเอง · "สรุปแล้ว…" (คำเชื่อม) ไม่เข้า
    _SUMMARY = re.compile(r"^(?:ช่วย|ขอ|รบกวน)*สรุป(?:ข้อความ|อีเมล์?|ข่าว|บทความ|เนื้อหา|เอกสาร|รายงาน)")

    def voiceIntent(self, text: str) -> str:  # noqa: N802
        """ประโยคจากคีย์ลัดเป็นงานของสกิลไหน (กฎล้วน · H6) · "reminder" · "llm:<id>" · "" = ไม่ใช่."""
        from aipc.skills import english, router, when
        from aipc.skills.langintent import lang_intent

        text = english.to_thai(text) or text
        t = re.sub(r"\s+", "", text.strip())
        by_id = {s.id: s for s in self._skills}
        # งานที่ใช้ AI ก่อน: ประโยคร่างจดหมายมักมีวันที่ ("ร่างอีเมลขอลางานพรุ่งนี้" เคยไปทางตั้งเตือน · รอบ 1)
        want = {"translate": "translate", "summarize": "summarize-text"}
        lang = want.get(lang_intent(text) or "", "")
        if lang in by_id:
            return "llm:" + lang
        if self._LETTER.match(t) and "letter-writer" in by_id:
            return "llm:letter-writer"
        if self._SUMMARY.match(t) and "summarize-text" in by_id:
            return "llm:summarize-text"
        rem = by_id.get("reminder")
        if rem is None or router.is_question(t) or self._EDIT_START.match(t):
            return ""
        # บอกวัน/เวลาต้องมีคำของสกิลนัดด้วย (เตือน นัด อย่าลืม ปลุก) · "วันนี้อากาศร้อนมาก" = คุยเล่น (รอบ 1)
        keyword = any(router.has_keyword(text, k) for k in rem.keywords)
        timed = keyword and when.mentions_time(text, part_of_day=False)
        return "reminder" if self._REMIND_START.match(t) or timed else ""

    @Slot(str, result="QVariantMap")
    def voiceReminder(self, text: str) -> dict:  # noqa: N802
        """ตั้งเตือนด้วยคีย์ลัด = การ์ดของสกิลนัดเดิม (ยืนยันก่อนบันทึก · เวลาไม่ชัด = ถามกลับ) · ไม่ผ่าน AI ·
        เลื่อน/ลบ/ถามนัด ("เลื่อนนัดประชุมไปพรุ่งนี้") = การ์ดที่โค้ดตอบเดิม (การ์ด 0029) ก่อน ไม่สร้างนัดใหม่
        (พบจากเกณฑ์ V3 ของการ์ด 0042)."""
        from aipc.skills import english

        if card := self.voiceAnswer(text):
            return card
        t0 = time.monotonic()
        card = self._handle_as("reminder", english.to_thai(text) or text)
        if card.get("badge"):  # _handle_as เขียนว่า "AI ในเครื่องเลือก" · ทางนี้กฎเป็นคนเลือก (H5)
            card["badge"] = {**card["badge"], "reason": "คำสั่งเสียง · กฎตรวจว่าเป็นการตั้งเตือน"}
        return self._why(card, t0)

    @Slot(str, result="QVariantMap")
    def voiceToChat(self, text: str) -> dict:  # noqa: N802
        """สกิลที่ใช้ AI ทางคีย์ลัด → การ์ด "ส่งไปที่แชทให้ AI ทำ ใช่ไหม" (BRIEF 5.6 ข้อ 1: คีย์ลัดไม่คุยกับ AI เอง) ·
        "ใช่" = ทางเดียวกับการ์ดเลือกสกิล (pending "tie") → หน้าจอส่งข้อความเดิมเข้าแชทพร้อม prompt ของสกิล."""
        from aipc.skills import english, router

        t0 = time.monotonic()
        want = self.voiceIntent(text)
        skill = next((s for s in self._skills if "llm:" + s.id == want), None)
        if skill is None:
            return {}
        thai = english.to_thai(text) or text
        self._counter += 1
        token = f"c{self._counter}"
        self._pending[token] = ("tie", router.Route("skill", skill, "สั่งด้วยคีย์ลัด · ยืนยันแล้ว"), thai)
        card = {"kind": "steps", "badge": self._badge(skill, "งานที่ใช้ AI · ยืนยันก่อนส่งไปแชท"),
                "title": "ส่งไปที่แชทให้ AI ทำ ใช่ไหม", "chips": [], "confirmToken": token,
                "lines": [f"ได้ยินว่า “{text}”",
                          "งานที่ AI ต้องคิด (แปล สรุป ร่างจดหมาย) ทำในหน้าแชท · “ใช่” = ส่งไปที่แชท"],
                "page": ""}  # fmt: skip
        return self._why(card, t0)

    @Slot(str, result="QVariantMap")
    def voiceAsk(self, text: str) -> dict:  # noqa: N802
        """ไม่ใช่คำสั่งทันที (คำถาม ข้อมูลสด คุยเล่น) → การ์ด "ส่งไปถามในแชทไหม" (การ์ด 0042 รอบ 3) ·
        "ใช่" = หน้าจอส่งข้อความเดิมเข้าแชทเหมือนพิมพ์ (สกิลทุกตัว + AI + การยืนยันก่อนส่งออกของแชทเดิม) ·
        คีย์ลัดไม่ส่งเอง (BRIEF 5.6 ข้อ 1) · สั้นเกินไป = {} (เสียงรบกวน)."""
        t0 = time.monotonic()
        if len(re.sub(r"\s+", "", text)) < 3:
            return {}
        self._counter += 1
        token = f"a{self._counter}"
        self._pending[token] = ("ask", text)
        card = {"kind": "steps", "badge": {}, "title": "ส่งไปถามผู้ช่วยในแชทไหม", "chips": [],
                "confirmToken": token, "page": "",
                "lines": [f"ได้ยินว่า “{text}”",
                          "ไม่ใช่คำสั่งที่ทำได้ทันที · คำถามและงานอื่น ๆ ตอบในหน้าแชท · "
                          "“ใช่” = ส่งไปที่แชท"]}  # fmt: skip
        return self._why(card, t0)

    # ---------- พูดสั่งให้ Claude สร้างสกิล (การ์ด 0030) ----------
    @Slot(str, result="QVariantMap")
    def voiceCreate(self, text: str) -> dict:  # noqa: N802
        """ขอโหมด/งานประจำที่ยังไม่มีสกิล → การ์ดยืนยันข้อความตามตัวอักษร **ก่อนส่ง Claude** · อื่น ๆ = {}.

        ไม่มี Claude / ปิดสวิตช์ / กำลังสร้างอยู่ = การ์ดอธิบายเดิมของ _start_forge (ไม่ส่ง)
        """
        from aipc.skills import router

        t0 = time.monotonic()
        new_mode = router.define_intent(text)
        if not new_mode or router.route_ai_first(text, self._skills).kind != "create":
            return {}  # ไม่ใช่คำขอสร้าง หรือมีสกิลเดิมตรงอยู่แล้ว
        if not self.canForge or self._forging:  # _start_forge กรณีนี้แค่อธิบาย ไม่ส่งอะไร
            return self._why(self._start_forge(text), t0)
        self._counter += 1
        token = f"f{self._counter}"
        self._pending[token] = ("forge", text)
        card = {"kind": "forge-ask", "badge": {}, "title": "ส่งให้ Claude สร้างสกิลนี้ ใช่ไหม",
                "chips": [{"text": "ส่งออกนอกเครื่อง", "kind": "warn"}], "confirmToken": token,
                "lines": [f"ได้ยินว่า “{text}”",
                          "ข้อความนี้จะส่งไปให้ Claude (นอกเครื่อง) สร้างสกิล · บันทึกในสิ่งที่ส่งออก",
                          "ไม่ตรงกับที่พูด = ตอบ “ไม่” แล้วพูดใหม่"],
                "page": "", "_outbound": "ยังไม่มี · จะส่งข้อความนี้ไป Claude เมื่อตอบ “ใช่”"}  # fmt: skip
        return self._why(card, t0)

    @Slot(str, result="QVariantMap")
    def voiceConfirm(self, text: str) -> dict:  # noqa: N802
        """ทาง ก (การ์ด 0028 หัวข้อ 12): ได้ยินใกล้เคียงสกิลแต่ไม่ตรงเป๊ะ → การ์ด "หมายถึง … ใช่ไหม" ใบเดียว.

        ไม่ทำอะไรจนกว่าตอบ "ใช่" (BRIEF 5.6 ข้อ 2) · ใช่ = ทำขั้นตอนทางเดียวกับการ์ดสกิลที่ยืนยันแล้ว ·
        ตรงเป๊ะ / ไม่ใกล้ = {} (หน้าจอใช้ทางเดิม)
        """
        t0 = time.monotonic()
        skill, example = self._nearest_voice(text)
        if skill is None and not self.voiceSkill(text):
            return self._near_command_card(text, t0)  # การ์ด 0045: ใกล้เคียงคำสั่งของระบบ
        if skill is None or self.voiceSkill(text):
            return {}
        self._counter += 1
        token = f"v{self._counter}"
        self._pending[token] = ("steps", skill, text)
        prefix = {"llm": "ถาม AI: ", "say": "บอก: ", "action": "", "agenda": ""}
        steps = [f"{i}. {prefix[s.kind]}{s.text}" for i, s in enumerate(skill.steps, 1)]
        card = {"kind": "steps", "badge": self._badge(skill, "ได้ยินใกล้เคียง · ยืนยันก่อนทำ"),
                "title": f"หมายถึง “{skill.name}” ใช่ไหม", "chips": [], "confirmToken": token,
                "lines": [f"ได้ยินว่า “{text}” · ใกล้กับ “{example}”", *steps], "page": ""}  # fmt: skip
        return self._why(card, t0)

    # ---------- สกิลประจำเว็บ (การ์ด 0046) ----------
    @Slot(str, str, result="QVariantMap")
    def siteCommand(self, text: str, url: str) -> dict:  # noqa: N802
        """คำพูดตรงกับคำสั่งของสกิลประจำเว็บที่เปิดอยู่ → {"siteRun": …} (ทำเลย) · มี "ยืนยันก่อน" = การ์ดยืนยัน ·
        ไม่ตรง = {} · หน้าจอเรียกก่อนทางเสียงอื่น (คำสั่งของเว็บที่เปิดอยู่มาก่อน · การ์ด 0046)."""
        return self._site_card(text, url, near=False)

    @Slot(str, str, result="QVariantMap")
    def siteNear(self, text: str, url: str) -> dict:  # noqa: N802
        """ได้ยินใกล้คำสั่งของสกิลประจำเว็บ → "หมายถึง … ใช่ไหม" (BRIEF 5.6 ข้อ 2 · การ์ด 0045) · ไม่ใกล้ = {} ·
        หน้าจอเรียกเมื่อทางเดิมไม่รู้จักเท่านั้น (ไม่ให้ความคล้ายเสียงแย่งคำสั่งที่ถูกอยู่แล้ว)."""
        return self._site_card(text, url, near=True)

    def _site_card(self, text: str, url: str, near: bool) -> dict:
        from aipc.skills import sitecmd

        t0 = time.monotonic()
        skill, cmd, exact = sitecmd.match(text, self._skills, url)
        if skill is None or exact == near:
            return {}
        run = {"kind": cmd.kind, "arg": cmd.arg, "site": skill.site}
        phrase = cmd.phrases[0]
        if exact and not cmd.confirm:
            return {
                "kind": "site-run",
                "siteRun": run,
                "title": phrase,
                "badge": self._badge(skill, "คำสั่งของสกิลประจำเว็บ"),
            }
        self._counter += 1
        token = f"w{self._counter}"
        self._pending[token] = ("site", run, phrase)
        title = f"ทำ “{phrase}” ใช่ไหม" if exact else f"หมายถึง “{phrase}” ใช่ไหม"
        why = f"ได้ยินว่า “{text}” · ใกล้กับ “{phrase}”"
        if exact:
            why = "คำสั่งนี้ย้อนไม่ได้หรือแตะบัญชี · ยืนยันก่อน"
        card = {"kind": "steps", "badge": self._badge(skill, "สกิลประจำเว็บ"), "title": title,
                "chips": [], "confirmToken": token, "page": "",
                "lines": [why, "ตอบ “ใช่” = ทำ · “ไม่” = ไม่ทำอะไร"]}  # fmt: skip
        return self._why(card, t0)

    @Slot(str, str, result="QVariantMap")
    def siteLearn(self, text: str, url: str) -> dict:  # noqa: N802
        """อยู่ในเว็บที่คุมได้ + พูดคำสั่งที่ยังไม่มี → "เพิ่มคำสั่ง … ให้สกิล … ไหม" (ส่งให้ Claude เมื่อตอบใช่) ·
        คำถาม / ไม่มี Claude / เว็บที่ไม่ได้คุม = {} (หน้าจอใช้ทางเดิม)."""
        from aipc.skills import router, sitecmd
        from aipc.skills.actions import SITES, SYSTEM_BROWSER_SITES

        t0 = time.monotonic()
        site = next(
            (k for k in SITES if k not in SYSTEM_BROWSER_SITES and sitecmd.on_site(k, url)), ""
        )
        if not site or not self.canForge or self._forging or router.is_question(text):
            return {}
        if len(re.sub(r"\s+", "", text)) < 3:
            return {}
        mine = next((s for s in self._skills if s.site == site and self._is_user(s.id)), None)
        self._counter += 1
        token = f"l{self._counter}"
        self._pending[token] = ("site-learn", site, mine.id if mine else "", text)
        name = SITES[site][0]
        card = {"kind": "forge-ask", "badge": {}, "confirmToken": token, "page": "",
                "chips": [{"text": "ส่งออกนอกเครื่อง", "kind": "warn"}],
                "title": f"เพิ่มคำสั่ง “{text}” ให้สกิลของ {name} ไหม",
                "lines": [f"ยังไม่มีคำสั่งนี้ใน {name} · "
                          "ส่งประโยคนี้ให้ Claude (นอกเครื่อง) เขียนเพิ่มในสกิล",
                          "ตอบ “ใช่” = ให้ Claude เพิ่ม · ครั้งหน้าพูดแล้วทำได้เลย · “ไม่” = ไม่ส่งอะไร"],
                "_outbound": "ยังไม่มี · จะส่งประโยคนี้ + ชื่อเว็บ ไป Claude เมื่อตอบ “ใช่”"}  # fmt: skip
        return self._why(card, t0)

    def _site_request(self, site: str, text: str, sid: str) -> str:
        """คำขอที่ส่ง Claude: ประโยคนี้ + ชื่อเว็บ + คำสั่งที่สกิลอื่นของเว็บนี้มีแล้ว (ไม่ให้ซ้ำ) · ไม่มีข้อมูลผู้ใช้."""
        from aipc.skills.actions import SITES

        ask = (f"ผู้ใช้เปิดเว็บ {SITES[site][0]} อยู่ แล้วสั่งด้วยเสียงว่า “{text}” · "
               f"ทำเป็นสกิลประจำเว็บ (site: {site} · หัวข้อ ## คำสั่ง) ที่มีคำสั่งนี้ "
               "(ใส่คำพูดแบบอื่นที่คนไทยพูดบ่อยด้วย) "
               "ด้วยคีย์ลัดของเว็บ หรือคลิกปุ่มด้วยตัวเลือก CSS ที่มั่นใจว่ามีจริง")  # fmt: skip
        others = [s for s in self._skills if s.site == site and s.id != sid]
        have = [c.phrases[0] for s in others for c in s.commands][:40]
        if have:
            ask += " · สกิลอื่นของเว็บนี้มีคำสั่งเหล่านี้แล้ว (ไม่ต้องใส่ซ้ำ): " + ", ".join(have)
        return ask

    def _near_command_card(self, text: str, t0: float) -> dict:
        """ได้ยินใกล้เคียงคำสั่งของระบบ (การ์ด 0045) → "หมายถึง … ใช่ไหม" ·
        ใช่ = ทำประโยคคำสั่งนั้น · ไม่ใกล้ = {}."""
        from aipc.skills.voice_phrases import near_command

        phrase = near_command(text)
        if not phrase:
            return {}
        self._counter += 1
        token = f"n{self._counter}"
        self._pending[token] = ("redo", phrase)
        card = {"kind": "steps", "badge": {}, "title": f"หมายถึง “{phrase}” ใช่ไหม", "chips": [],
                "confirmToken": token, "page": "", "suggest": phrase,
                "lines": [f"ได้ยินว่า “{text}” · ใกล้กับคำสั่ง “{phrase}”",
                          "ตอบ “ใช่” = ทำคำสั่งนี้ · “ไม่” = ไม่ทำอะไร"]}  # fmt: skip
        return self._why(card, t0)

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
           "weather-off": "สกิลอากาศ · โค้ดในเครื่อง (ไม่ได้ติดต่อ Open-Meteo)",
           "forging": "Claude (cloud) กำลังสร้างสกิล", "forge-failed": "Claude (cloud)",
           "clock": "นาฬิกาเครื่อง · โค้ดในเครื่อง",
           "forge-ask": "โค้ดในเครื่อง · ยังไม่ได้ส่งอะไร"}  # fmt: skip
    WHY = {"weather": "ตรงรูปประโยคถามอากาศ (กฎ) · ไม่ผ่าน AI จึงไม่เดาตัวเลข",
           "forge-ask": "ขอโหมด/งานประจำที่ยังไม่มีสกิล (กฎ) · ส่งออกต้องยืนยันก่อน (การ์ด 0030)",
           "files": "ตรงรูปประโยคหาไฟล์ (กฎ) · AI ในเครื่องเปิดไฟล์เองไม่ได้",
           "forging": "ขอตั้งโหมด/งานประจำที่ยังไม่มีสกิล",
           "weather-off": "ถามอากาศ แต่ปิดสวิตช์อากาศในหน้าตั้งค่า",
           "clock": "ตรงรูปประโยคถามเวลา (กฎ) · AI ในเครื่องไม่รู้เวลาตอนนี้"}  # fmt: skip

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
        from aipc.skills import english

        t0 = time.monotonic()
        # คำสั่งอังกฤษ → รูปไทยให้ตัวแปลเดิม (การ์ด 0039 ระยะ C) · แปลงแล้วยังไปจบที่ AI = ส่งข้อความเดิม
        # ให้ AI แทน (AI ตอบอังกฤษตามภาษาคำถาม) · ไม่ใช่คำสั่ง = to_thai คืน None ไม่แตะอะไร
        th = english.to_thai(text)
        card = self._handle(th) if th else None
        if card is None or card.get("llm"):
            return self._why(self._handle(text), t0)
        card = self._why(card, t0)
        card.setdefault("why", []).insert(1, {"k": "แปลงคำสั่งอังกฤษ", "v": th})
        return card

    def _unsupported_card(self, text: str) -> dict | None:
        """ "เปิดเฟซบุ๊ก" · "เปิดไลน์" = บริการที่ตั้งใจไม่มี → บอกตรง ๆ (H5) · None = ไม่ใช่."""
        from aipc.skills import command

        name = command.unsupported(text)
        if name is None:
            return None
        return self._plain("command", f"ระบบนี้ไม่มี {name}",
                           ["ตั้งใจไม่รวมไว้ในผู้ช่วย · เปิดเองได้จากเบราว์เซอร์"])  # fmt: skip

    def _handle(self, text: str) -> dict:
        from aipc.skills import router

        if card := self._unsupported_card(text):
            return card

        if card := self._agenda_card(text):  # ถามตารางนัด = ตอบจากไฟล์นัดด้วยโค้ด ไม่ใช่จดนัดใหม่
            return card
        if card := self._clock_card(text) or self._until_card(text):  # เวลา · อีกกี่วัน = นาฬิกาเครื่อง
            return card
        if card := self._holiday_card(text):  # วันหยุดถัดไป · ช่วงนี้มีวันหยุดไหม (การ์ด 0033)
            return card
        if card := self._cancel_card(text):  # ยกเลิก/ลบนัด = การ์ดยืนยัน แล้วลบด้วยโค้ด
            return card
        if card := self._next_card(text) or self._move_card(text):  # นัดถัดไป · ขอเลื่อนนัด
            return card
        if card := self._title_card(text):  # "นัดหมอวันไหน" (การ์ด 0037)
            return card
        # ขอสกิลใหม่ระหว่างปิดสวิตช์ Claude (AI ไม่มีเครื่องมือ create-skill) = บอกให้เปิดที่หน้าตั้งค่า
        # · พบบน Pi 5 2026-10-12: เดิม AI ในเครื่องตอบ "ไม่รู้ครับ สร้างสกิลไม่ได้"
        claude_off = self._forge is not None and self._user is not None and not self._claude_on()
        if claude_off and re.search(r"(สร้าง|อยากได้|ขอ|ทำ|เพิ่ม)(ให้)?สกิล", text.replace(" ", "")):
            return self._start_forge(text)
        from aipc.skills.fileintent import file_intent, file_time
        from aipc.skills.weather import place_in, weather_intent

        if self._weather is not None:
            if self._weather_day is not None:  # ตอบชื่อเมืองที่ถามกลับไป
                day, self._weather_day = self._weather_day, None
                city = place_in(text) or (text.strip() if len(text.strip()) <= 30 else "")
                if city:
                    return self._weather_card(day, city)
            if ask := weather_intent(text):  # อากาศจริง = Open-Meteo โดยตรง ไม่ผ่าน Claude
                if not self._weather_on():
                    return self._weather_off_card()
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
                # มี Claude แต่ปิดสวิตช์ = บอกให้เปิดที่หน้าตั้งค่า (_start_forge) · พบบน Pi 5 2026-10-12:
                # เดิมส่งให้ AI ในเครื่อง → "ไม่รู้ครับ สร้างสกิลไม่ได้" ผู้ใช้ไม่รู้ว่าต้องเปิดสวิตช์
                has_claude = self._forge is not None and self._user is not None
                return (
                    self._start_forge(text)
                    if has_claude
                    else self._card(router.Route("chat"), text)
                )
            return self._card(r, text)
        return self._card(router.route(text, self._skills, self.available()), text)

    def _weather_off_card(self) -> dict:
        return {"kind": "weather-off", "badge": {}, "chips": [], "confirmToken": "", "page": "",
                "title": "ปิดการถามพยากรณ์อากาศอยู่",
                "lines": ["ตอนนี้ไม่ส่งชื่อเมืองไป Open-Meteo ตามที่ตั้งไว้",
                          "เปิดได้ที่หน้าตั้งค่า › ส่งออกนอกเครื่อง"],
                "_outbound": "ไม่มี · ปิดสวิตช์อากาศอยู่"}  # fmt: skip

    def _weather_card(self, day: str, city: str) -> dict:
        from aipc.skills.weather import Ask, answer

        if not self._weather_on():  # ปิดสวิตช์ระหว่างรอผู้ใช้ตอบชื่อเมือง
            return self._weather_off_card()
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
            folder = tr("ไฟล์ของฉัน") + ("" if parent == "." else " / " + parent.replace("/", " / "))
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
            if r.command.plan.action in POWER_ACTIONS:  # การ์ด 0052: ถามทุกครั้ง · ไม่ตอบใน 10 วิ = ยกเลิก
                self._counter += 1
                token = f"c{self._counter}"
                self._pending[token] = r.command.plan
                card.update(
                    title=f"{r.command.plan.summary}เลยไหม?",
                    lines=["ตอบ “ใช่” ภายใน 10 วินาที · ไม่ตอบ = ยกเลิก",
                           "แชทและนัดบันทึกไว้แล้ว · งานในแอปอื่นที่ยังไม่บันทึกจะหาย"],
                    chips=[{"text": risk, "kind": "neutral"}],
                    confirmToken=token,
                    power=True,
                )  # fmt: skip
            elif r.command.needs_confirmation:
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
        elif self._llm_ready() or self._chat_mode() == "work":
            # คุยทั่วไป → LLM ในเครื่อง (การ์ด 0013) · แชทงาน → Claude (การ์ด 0053)
            card.update(kind="chat", llm=True, prompt="")
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
        elif isinstance(plan, tuple) and plan[0] in ("app-install", "app-web"):
            # การ์ด 0054 · ตอบ "ไม่" ไม่ได้แปลว่ายกเลิกทันที แต่ถามข้อถัดไป (เปิดผ่านเว็บ)
            return self._missing_app_answer(plan[0], plan[1], yes)
        elif not yes:
            card["title"] = "ยกเลิกแล้ว ไม่ได้ทำอะไร"
        elif isinstance(plan, tuple) and plan[0] == "tie":
            _, route, text = plan
            card = self._card(route, text)
            if card.get("llm"):
                card["llmText"] = text  # หน้าจอส่งข้อความเดิมให้ AI พร้อม prompt ของสกิลที่ผู้ใช้ยืนยัน
            return card
        elif isinstance(plan, tuple) and plan[0] == "cancel":
            card["kind"] = "reminder"
            try:
                n = sum(self._store.delete(rid, self._now()) for rid in plan[1])
            except (OSError, reminders.Unreadable) as e:
                card["title"] = f"ลบไม่สำเร็จ: {e}"
                return card
            self.remindersChanged.emit()
            card["title"] = f"ลบนัดแล้ว {n} รายการ"
        elif isinstance(plan, tuple) and plan[0] == "steps":
            _, skill, text = plan
            card.update(kind="steps", badge=self._badge(skill, "ยืนยันแล้ว"))
            return self._run_steps(skill, text, card)
        elif isinstance(plan, tuple) and plan[0] == "site":  # การ์ด 0046: หน้าจอสั่งเบราว์เซอร์
            card.update(kind="site-run", title=plan[2], siteRun=plan[1])
        elif isinstance(plan, tuple) and plan[0] == "site-learn":  # การ์ด 0046: ส่งให้ Claude เพิ่มคำสั่ง
            _, site, sid, text = plan
            request = self._site_request(site, text, sid)
            self._voice_forges.add(request)
            if sid:
                return self._start_forge(request, revise_id=sid, feedback=f"เพิ่มคำสั่งเสียง “{text}”")
            return self._start_forge(request)
        elif isinstance(plan, tuple) and plan[0] == "redo":  # การ์ด 0045: ใช่ = หน้าจอสั่งประโยคคำสั่งนั้น
            card.update(kind="redo", title=f"ทำ “{plan[1]}”", redo=plan[1])
        elif isinstance(plan, tuple) and plan[0] == "ask":  # การ์ด 0042 รอบ 3: หน้าจอส่งเข้าแชทเหมือนพิมพ์
            card.update(kind="to-chat", title="ส่งไปที่แชทแล้ว", chatText=plan[1])
        elif isinstance(plan, tuple) and plan[0] == "forge":  # การ์ด 0030: ยืนยันแล้วจึงส่ง Claude
            self._voice_forges.add(plan[1])
            return self._start_forge(plan[1])
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

    แชท 2 แบบ (การ์ด 0053 · Pakon 2026-10-22):
      "general" ทั่วไป = ไฮบริดเดิม (การ์ด 0016/0022): AI ในเครื่องตอบก่อน ไม่รู้ = ส่งต่อ Claude เอง
                 (Pakon 2026-10-22: "บางครั้ง local AI ก็ไม่ฉลาด") · ค่าเริ่มต้นทุกครั้งที่เปิด
      "work"    งาน   = ทุกข้อความไป Claude ด้วยโมเดลที่ผู้ใช้เลือก (haiku/sonnet/opus) · ไม่ผ่าน AI ในเครื่อง
    auto_cloud = เปิดการส่งต่อของแชททั่วไป (แอปจริงเปิด · สวิตช์ Claude ในหน้าตั้งค่ายังปิดได้)
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
    modeChanged = Signal()  # noqa: N815 · แชท 2 แบบ (การ์ด 0053)

    def __init__(self, active: bool = True, target=None, store=None, poll_ms: int = 5000,
                 tools=None, cloud=None, model_name: str = "", forge: bool = False,
                 claude_on=None, meter=None, auto_cloud=False, cloud_model=None,
                 cloud_effort=None):  # fmt: skip
        super().__init__()
        # cloud(คำถาม, บทสนทนา[, model=]) → CloudReply · None = ไม่มี Claude ในเครื่องนี้
        self._cloud = cloud
        self._auto_cloud = auto_cloud
        self._mode = "general"
        self._cloud_model = cloud_model or (lambda: "sonnet")  # โมเดลของแชทงานที่ผู้ใช้เลือก (ค่าตั้ง)
        self._cloud_effort = cloud_effort or (lambda: None)  # ระดับความคิดของแชทงาน · None = ไม่ส่ง
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
        # มิเตอร์พลังงานต่อคำตอบ (ข้อ ค 2026-10-07): factory() → Meter หรือ None ·
        # อ่าน PMIC ไม่ได้ = ไม่แสดง (H5)
        if meter is None:
            from aipc.bench import energy

            meter = energy.meter_factory() if active else (lambda: None)
        self._meter_factory, self._meter = meter, None
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
        return tr(self.STATUS_TEXT[self._status])

    @Property(bool, notify=statusChanged)
    def ready(self) -> bool:
        return self._status == "ready"

    # ---------- แชท 2 แบบ (การ์ด 0053) ----------
    @Property(str, notify=modeChanged)
    def mode(self) -> str:
        return self._mode

    @Property(bool, notify=modeChanged)
    def workReady(self) -> bool:  # noqa: N802
        """แชทงานใช้ได้: มี Claude ในบัญชีนี้ และผู้ใช้เปิดสวิตช์ Claude ไว้."""
        return self._cloud is not None and bool(self._claude_on())

    @Property(str, notify=modeChanged)
    def workBlocked(self) -> str:  # noqa: N802
        """ทำไมแชทงานใช้ไม่ได้ ("" = ใช้ได้) · หน้าจอแสดงตรง ๆ (H5)."""
        if self._cloud is None:
            return "ยังไม่ได้ติดตั้งหรือเข้าสู่ระบบ Claude ในบัญชีนี้"
        if not self._claude_on():
            return "ปิด Claude ไว้ในหน้าตั้งค่า"
        return ""

    @Slot(str, result=bool)
    def setMode(self, mode: str) -> bool:  # noqa: N802
        """สลับแบบแชท = เริ่มบทสนทนาใหม่ของแบบนั้น (ประวัติแยกกัน) · กำลังตอบ/ค่าแปลก/แชทงานใช้ไม่ได้ = False."""
        if mode not in ("general", "work") or self._busy:
            return False
        if mode == "work" and not self.workReady:
            return False
        if mode != self._mode:
            self._mode = mode
            self.newChat(False)
            self.modeChanged.emit()
            if mode == "general" and self._status == "ready":
                self._warm_up()
        return True

    @Slot()
    def claudeChanged(self) -> None:  # noqa: N802
        """สวิตช์ Claude เปลี่ยน · ปิดระหว่างอยู่แชทงาน = กลับแชททั่วไป (ไม่ส่งออกอีก)."""
        if self._mode == "work" and not self.workReady and not self._busy:
            self._mode = "general"
            self.newChat(False)
        self.modeChanged.emit()

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
        """ประวัติของแบบแชทที่เปิดอยู่เท่านั้น · แชทเก่าก่อนการ์ด 0053 (ไม่มี mode) = ทั่วไป."""
        try:
            return [c for c in self._store.list() if c.get("mode", "general") == self._mode]
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

    CLAUDE_HIDDEN = ("[ข้อความนี้ Claude (cloud) ตอบโดยค้นเว็บ · เนื้อหาไม่แสดงให้ AI ในเครื่อง · "
                     "ถ้าผู้ใช้ถามข้อมูลสด หรือถามต่อจากข้อความนี้ {how}]")  # fmt: skip

    def _for_local(self, m: dict) -> dict:
        """คำตอบของ Claude ในประวัติ → ส่งให้ AI ในเครื่องแค่ป้ายที่มา ไม่ส่งเนื้อหา.

        พบ 2026-10-05 บน Pi: ปิดสวิตช์ Claude แล้วถามข่าวซ้ำ · AI ในเครื่องอ้างว่าข่าวที่ Claude ค้นมา
        "เป็นความรู้ ณ เวลาที่ฉันถูกฝึก" (H5) → เดิมใส่ป้ายนำหน้าเนื้อหา · การ์ด 0022 (ชุดพัฒนา D1 Pi 5
        2026-10-12): แม้มีป้าย ยังลอกคำตอบเก่าของ Claude มาตอบเอง หรือแต่งข้อมูลสดใหม่ในรูปเดียวกัน
        ("แก๊สโซฮอล์ 95 … 36.50 บาท") → ไม่ส่งเนื้อหา · คำถามต่อเรื่องนั้นไปที่ Claude ซึ่งเห็นบทสนทนาเต็ม
        (aipc.cloud.ask.build_input) · เก็บในไฟล์แชทตามเดิม เปลี่ยนแค่สิ่งที่ส่ง
        """
        if m.get("by") == "claude":
            from aipc.skills.catalog import ASK_CLOUD

            how = (f"ให้เรียกเครื่องมือ {ASK_CLOUD}" if self._cloud_ok()
                   else "ให้บอกว่าต้องเปิด Claude ในหน้าตั้งค่าก่อน ห้ามเดา")  # fmt: skip
            return {**m, "content": self.CLAUDE_HIDDEN.format(how=how)}
        return m

    def _cloud_ok(self) -> bool:
        """AI ในเครื่องส่งต่อ Claude เองได้ไหม (ไฮบริดของแชททั่วไป) · มี Claude + เปิดสวิตช์ + auto_cloud."""
        return self._auto_cloud and self._cloud is not None and bool(self._claude_on())

    @Slot()
    def claudeSwitched(self) -> None:  # noqa: N802
        """เปิด/ปิด Claude → รายการเครื่องมือและ system prompt เปลี่ยน → อุ่นแคชใหม่ให้ข้อความถัดไปไม่ต้องรอ."""
        if self._status == "ready":
            self._warm_up()

    def _system(self, tools: list, text: str = "") -> str:
        """system prompt ชุดเดียวกับตัววัด (catalog.system_prompt) · มีวันที่ของวันนี้ · ส่งต่อ Claude ได้ถ้ามี ·
        text = ข้อความล่าสุดของผู้ใช้: เป็นภาษาอังกฤษ = ให้ตอบอังกฤษ (การ์ด 0039)."""
        from datetime import date

        from aipc.skills import catalog

        base = catalog.system_prompt(
            date.today(),
            cloud=self._cloud_ok(),
            model=self._model_name,
            forge=self._forge and self._cloud_ok(),
            english=catalog.is_english(text),
        )
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
        if self._mode == "work":
            return self._send_work(text)
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
        self._meter = self._meter_factory()
        if self._meter is not None:
            self._meter.start()
        if prompt:  # สกิล (เช่น แปล): งานเดียวจบ ไม่ต้องใช้บทสนทนาก่อนหน้า
            messages, trimmed = client.fit_context(prompt, self._conv["messages"][-1:])
        else:
            messages, trimmed = client.fit_context(
                self._system(tools, text), self._conv["messages"]
            )
            messages = [self._for_local(m) for m in messages]
        self._trimmed = trimmed and not prompt
        self._busy, self._stream_text = True, ""
        stream = self._stream = client.Stream(self._target, messages, tools=tools)
        self.changed.emit()
        self.streamChanged.emit()
        threading.Thread(
            target=lambda: self._done.emit(stream.run(self._token.emit)), daemon=True
        ).start()
        return True

    def _send_work(self, text: str) -> bool:
        """แชทงาน: ส่งให้ Claude ตรง ๆ ไม่ต้องรอ AI ในเครื่อง · สกิลภาษา (แปล/สรุป) ส่งแค่ข้อความของผู้ใช้."""
        if self._busy or not text.strip() or not self.workReady:
            return False
        self._conv["messages"].append({"role": "user", "content": text})
        self._trace = {"t0": time.monotonic(), "why": "แชทงาน: ทุกข้อความส่งให้ Claude"}
        effort = self._work_effort()
        why = f"โมเดลที่เลือก: {self._work_model()}" + (f" · ความคิด {effort}" if effort else "")
        self._ask_cloud(why)
        return True

    def _work_effort(self) -> str | None:
        from aipc.cloud.ask import EFFORTS

        e = self._cloud_effort()
        return e if e in EFFORTS else None

    def _work_model(self) -> str:
        from aipc.cloud.ask import MODELS

        m = self._cloud_model()
        return m if m in MODELS else "sonnet"

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

    # AI ในเครื่องลอกป้ายที่มาของ Claude (CLAUDE_LABEL ในประวัติ) มาใส่คำตอบตัวเอง
    # (T6 แบบใหม่ Pi 5 2026-10-08)
    _FAKE_LABEL = re.compile(r"\[ข้อความนี้ Claude[^\]\n]*\]\s*")

    NEEDS_CLAUDE = "ข้อนี้ต้องใช้ข้อมูลที่ Claude ค้นจากเว็บ · AI ในเครื่องตอบเองไม่ได้ · เปิด Claude ได้ที่หน้าตั้งค่า"

    @Slot(object)
    def _on_done(self, reply) -> None:
        parroted = False  # ตอบมาแค่ป้ายที่มาของ Claude ที่ลอกจากประวัติ (การ์ด 0022 ชุดพัฒนา D1)
        if not getattr(reply, "cloud", False) and reply.text:
            text = self._FAKE_LABEL.sub("", reply.text)  # ป้ายที่มาจริงอยู่ใน "ทำไมได้คำตอบนี้"
            parroted = not text.strip() and not reply.tool_call and not reply.reason
            reply.text = text
        self._busy, self._stream = False, None
        if self._meter is not None:  # ไฟที่บอร์ดใช้ระหว่าง AI ในเครื่องตอบ (รอบที่ส่งต่อ Claude ไม่แสดง)
            self._trace["energy"] = self._meter.stop()
            self._meter = None
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
            if not reply.tool_call and (parroted or local_gave_up(reply.text)):
                self._ask_cloud("AI ในเครื่องตอบว่าไม่รู้ จึงถาม Claude แทน")
                return
        if parroted:  # ส่งต่อไม่ได้ (ปิด Claude / ถามเกี่ยวกับไฟล์) · ไม่แสดงคำตอบว่าง
            reply.text = self.NEEDS_CLAUDE
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
            if self._mode == "work":
                used = getattr(reply, "model", "") or "ไม่ทราบโมเดล"
                note = f"แชทงาน · ตอบโดย Claude ({used}) · ส่งออกนอกเครื่อง"
        elif self._switched_off_gave_up(reply, with_file):
            note = self.CLAUDE_OFF_NOTE
        if reply.text:
            msg = {"role": "assistant", "content": reply.text}
            if getattr(reply, "cloud", False):
                msg["by"] = "claude"  # ส่งให้ AI ในเครื่องครั้งหน้าพร้อมป้ายที่มา (_for_local)
                if getattr(reply, "model", ""):
                    msg["model"] = reply.model
            self._conv["messages"].append(msg)
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
    # มี Claude แต่ผู้ใช้ปิดสวิตช์ แล้ว AI ในเครื่องตอบว่าไม่รู้ (พบบน Pi 5 2026-10-12: "ไม่มีข้อมูลสด" เฉย ๆ
    # ผู้ใช้ไม่รู้ว่าเปิด Claude ได้) · บอกเท่านั้น ไม่ส่งอะไรออก
    CLAUDE_OFF_NOTE = "ปิด Claude ไว้ · ข้อนี้ Claude ช่วยค้นจากเว็บได้ เปิดได้ที่หน้าตั้งค่า"

    def _switched_off_gave_up(self, reply, with_file: bool) -> bool:
        from aipc.cloud.ask import local_gave_up

        off = self._cloud is not None and not self._claude_on() and not with_file
        return off and not reply.reason and not reply.tool_call and local_gave_up(reply.text)

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
            if getattr(reply, "model", ""):
                who += f" · {reply.model}"
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
        e = t.get("energy")
        if e and not cloud:
            used = f"≈ {e['joules']:.0f} J ({e['seconds']:.1f} วิ · เฉลี่ย {e['mean_w']:.1f} W · "
            rows.append({"k": "ไฟที่บอร์ดใช้ระหว่างตอบ", "v": used + "ทั้งบอร์ด ไม่รวมอะแดปเตอร์)"})
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

        work_model = self._work_model() if self._mode == "work" else None
        effort = self._work_effort() if work_model else None
        if work_model:
            how = work_model + (f" · ความคิด {effort}" if effort else "")
            self._stream_text = f"กำลังถาม Claude ({how}) · แชทงาน…"

        def work():
            if work_model:
                extra = {"effort": effort} if effort else {}
                c = self._cloud(question, history, model=work_model, **extra)
            else:
                c = self._cloud(question, history)
            reply = client.Reply(text=c.text if c.ok else "", reason="" if c.ok else "error",
                                 detail="" if c.ok else c.error)  # fmt: skip
            reply.cloud = c.ok  # type: ignore[attr-defined]
            reply.model = getattr(c, "model", "") or ""  # type: ignore[attr-defined]
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

        if self._mode == "work":  # การ์ด 0053 ข้อ 7: แชทงานส่งทุกอย่างออกนอกเครื่อง → ไม่รับไฟล์
            return "แนบไฟล์ได้เฉพาะแชททั่วไป (เนื้อหาไฟล์ไม่ออกนอกเครื่อง)"
        try:
            text = files_qa.extract(Path(path))
        except files_qa.Unsupported as e:
            # แนบไม่สำเร็จ = เลิกแนบไฟล์เดิมด้วย (พบบน Pi 5 2026-10-12: กดถามไฟล์ใหม่ที่อ่านไม่ได้
            # แล้วถาม "ไฟล์นี้มีอะไร" ได้คำตอบของไฟล์ก่อนหน้า)
            if self._file is not None:
                self._file = None
                self.changed.emit()
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
        self._conv["mode"] = self._mode
        # ไฟล์ที่แนบเป็นของแชทเดิม (สำรวจบน Pi 5 2026-10-12: แชทใหม่ยังแนบอยู่ → "ปรับเสียงเป็น 40" ถูกถามไฟล์แทน)
        self._file = None
        self.changed.emit()

    @Slot(str, result="QVariantList")
    def openChat(self, cid: str) -> list:  # noqa: N802
        conv = self._store.load(cid)
        if conv is None or self._busy:
            return []
        mode = conv.get("mode", "general")
        if mode == "work" and not self.workReady:
            return []  # เปิดแชทงานเก่าตอนปิด Claude ไว้ = ถามต่อไม่ได้ · ไม่สลับ
        if mode != self._mode:
            self._mode = mode
            self.modeChanged.emit()
        self._conv, self._temporary, self._trimmed = conv, False, False
        self._file = None
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
        if self._meter is not None:
            self._meter.stop()
            self._meter = None
