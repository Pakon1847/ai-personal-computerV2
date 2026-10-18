"""ค่าหน้าจอที่ผู้ใช้ตั้งเอง (ธีม ขนาดตัวอักษร) และการบันทึกลงไฟล์.

บันทึกแบบ atomic ตาม BRIEF 5.9 ข้อ 9: เขียนไฟล์ชั่วคราว → fsync → rename ทับของเดิม
ถ้าไฟดับกลางคัน จะเหลือไฟล์เก่าครบหรือไฟล์ใหม่ครบอย่างใดอย่างหนึ่ง ไม่มีครึ่ง ๆ
เพราะ rename บน Linux เป็นการสลับชื่อครั้งเดียวจบ (atomic)

ไฟล์อยู่ใน home ของผู้ใช้ (~/.config/aipc/ui.json) ซึ่งเข้ารหัสและเป็นของผู้ใช้คนนั้น
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

THEMES = ("light", "dark")
LANGS = ("th", "en")  # ภาษาของหน้าจอ (การ์ด 0039) · ค่าเริ่มต้นไทย
FONT_SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)  # BRIEF 5.7: 100–200%
# ล็อกเมื่อไม่ได้ใช้เครื่อง (ขั้น A · 2026-10-06): นาทีที่ไม่มีคีย์บอร์ด/เมาส์ก่อนล็อก (0 = ปิด)
# และนาทีหลังล็อกก่อนออกจากระบบเอง
LOCK_CHOICES = (0, 1, 5, 10, 15)
LOGOUT_CHOICES = (5, 10, 30)
# ขั้น C (aipc.ui.presence): กล้องตรวจว่าเจ้าของยังอยู่ · วินาทีที่ไม่เห็นเจ้าของก่อนล็อก และหลังล็อกก่อนออก
PRESENCE_CHOICES = (30, 60, 120)
# เตือนนัดจากปฏิทิน Google ล่วงหน้ากี่นาที (การ์ด 0032 · 0 = ไม่เตือน)
GCAL_ALERT_CHOICES = (0, 5, 10, 30)


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "aipc" / "ui.json"


@dataclass
class UiPrefs:
    theme: str = "light"
    font_scale: float = 1.0
    onboarded: bool = False  # เห็นหน้าแนะนำการใช้งานครั้งแรกแล้ว (ฟีเจอร์ข้อ 8)
    # อ่านคำตอบ AI ออกเสียงเองเมื่อตอบจบ (การ์ด 0019) · Pakon: ค่าเริ่มต้นเปิด ปิดได้จากปุ่มในหน้าแชท
    # (ชื่อใหม่แทน auto_speak ที่ค่าเริ่มต้นปิด · ไฟล์เก่าที่มี auto_speak: false จึงไม่ทำให้เสียงปิด)
    speak_answers: bool = True
    # ถึงเวลานัด = อ่านออกเสียงด้วย · ค่าเริ่มต้นปิด
    speak_reminders: bool = False
    # ส่งคำถามที่ยาก/ต้องใช้ข้อมูลสด และคำขอสร้างสกิลให้ Claude (การ์ด 0016/0017) · Pakon: ค่าเริ่มต้นเปิด
    use_claude: bool = True
    # ถามอากาศ = ส่งชื่อเมือง/พิกัดไป Open-Meteo · ปิดได้ (แผงความเป็นส่วนตัว 2026-10-07) · ค่าเริ่มต้นเปิดเหมือนเดิม
    use_weather: bool = True
    # ลืมออกจากระบบแล้วลุกไป = คนต่อไปเห็นงาน แชท และ Gmail ที่ login ค้าง → ล็อกแล้วออกเอง · ค่าเริ่มต้นเปิด
    lock_min: int = 5
    logout_min: int = 10
    # กล้องช่วยดูว่าเจ้าของยังอยู่ (ขั้น C) · ต้องเปิดเอง (กล้องเปิดตอนไม่ได้แตะเครื่อง) · ค่า 30/30 ตามที่ Pakon เสนอ
    presence: bool = False
    presence_lock_s: int = 30
    presence_logout_s: int = 30
    # เตือนนัดจากปฏิทิน Google ก่อนเวลานัด (การ์ด 0032) · ค่าเริ่มต้น 10 นาที
    gcal_alert_min: int = 10
    language: str = "th"  # การ์ด 0039

    def cleaned(self) -> UiPrefs:
        """ค่าที่อ่านจากไฟล์อาจถูกแก้มือหรือเสีย → ถอยไปค่าเริ่มต้นแทนการ crash."""
        theme = self.theme if self.theme in THEMES else "light"
        scale = self.font_scale if self.font_scale in FONT_SCALES else 1.0
        return UiPrefs(
            theme=theme,
            font_scale=scale,
            onboarded=self.onboarded is True,
            speak_answers=self.speak_answers is not False,
            speak_reminders=self.speak_reminders is True,
            use_claude=self.use_claude is not False,
            use_weather=self.use_weather is not False,
            lock_min=self.lock_min
            if self.lock_min in LOCK_CHOICES and type(self.lock_min) is int
            else 5,
            logout_min=self.logout_min
            if self.logout_min in LOGOUT_CHOICES and type(self.logout_min) is int
            else 10,
            presence=self.presence is True,
            presence_lock_s=self.presence_lock_s
            if self.presence_lock_s in PRESENCE_CHOICES and type(self.presence_lock_s) is int
            else 30,
            presence_logout_s=self.presence_logout_s
            if self.presence_logout_s in PRESENCE_CHOICES and type(self.presence_logout_s) is int
            else 30,
            gcal_alert_min=self.gcal_alert_min
            if self.gcal_alert_min in GCAL_ALERT_CHOICES and type(self.gcal_alert_min) is int
            else 10,
            language=self.language if self.language in LANGS else "th",
        )


def load(path: Path | None = None) -> UiPrefs:
    path = path or default_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UiPrefs(
            theme=str(data.get("theme", "light")),
            font_scale=float(data.get("font_scale", 1.0)),
            onboarded=data.get("onboarded") is True,
            speak_answers=data.get("speak_answers", True) is not False,
            speak_reminders=data.get("speak_reminders") is True,
            use_claude=data.get("use_claude", True) is not False,
            use_weather=data.get("use_weather", True) is not False,
            lock_min=data.get("lock_min", 5),
            logout_min=data.get("logout_min", 10),
            presence=data.get("presence") is True,
            presence_lock_s=data.get("presence_lock_s", 30),
            presence_logout_s=data.get("presence_logout_s", 30),
            gcal_alert_min=data.get("gcal_alert_min", 10),
            language=str(data.get("language", "th")),
        ).cleaned()
    except (OSError, ValueError, TypeError, AttributeError):
        return UiPrefs()


def save(prefs: UiPrefs, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(asdict(prefs.cleaned()), f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())  # บังคับให้ข้อมูลลงการ์ดจริงก่อน rename
    os.replace(tmp, path)  # os.replace = rename ที่เขียนทับได้ทั้งบน Linux และวินโดวส์
