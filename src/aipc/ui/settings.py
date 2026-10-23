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
CLOUD_MODELS = ("haiku", "sonnet", "opus")  # โมเดลของแชทงาน (การ์ด 0053) · ชุดเดียวกับ ask.MODELS
# ระดับความคิดของแชทงาน · ชุดเดียวกับ ask.EFFORTS
CLOUD_EFFORTS = ("low", "medium", "high", "xhigh", "max")
FONT_SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)  # BRIEF 5.7: 100–200%
# ล็อกเมื่อไม่ได้ใช้เครื่อง (ขั้น A · 2026-10-06): นาทีที่ไม่มีคีย์บอร์ด/เมาส์ก่อนล็อก (0 = ปิด)
# และนาทีหลังล็อกก่อนออกจากระบบเอง (0 = ไม่ออกเอง · ค่าเริ่มต้นตั้งแต่การ์ด 0051)
LOCK_CHOICES = (0, 1, 5, 10, 15)
LOGOUT_CHOICES = (0, 5, 10, 30)
# ขั้น C (aipc.ui.presence): กล้องตรวจว่าเจ้าของยังอยู่ · วินาทีที่ไม่เห็นเจ้าของก่อนล็อก และหลังล็อกก่อนออก
PRESENCE_CHOICES = (30, 60, 120)
PRESENCE_LOGOUT_CHOICES = (0, *PRESENCE_CHOICES)  # 0 = ล็อกอย่างเดียว ไม่ออก (การ์ด 0051)
# รุ่นของกติกาล็อก · ไฟล์ที่ยังไม่มีค่านี้ = เขียนก่อนการ์ด 0051 → ย้ายเป็น "ไม่ออกเอง" ครั้งเดียว
LOCK_POLICY = 1
# เตือนนัดจากปฏิทิน Google ล่วงหน้ากี่นาที (การ์ด 0032 · 0 = ไม่เตือน)
GCAL_ALERT_CHOICES = (0, 5, 10, 30)


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "aipc" / "ui.json"


@dataclass
class UiPrefs:
    # การ์ด 0041: ผู้ใช้ใหม่ได้ธีมดำ · ผู้ใช้เดิมที่มีไฟล์ค่าตั้งแล้วคงค่าเดิม (ทาง ก · ไม่ทับสิ่งที่อาจเลือกเอง)
    theme: str = "dark"
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
    # ลืมออกจากระบบแล้วลุกไป = คนต่อไปเห็นงาน แชท และ Gmail ที่ login ค้าง → ล็อก · ค่าเริ่มต้นเปิด
    # การ์ด 0051 (Pakon 2026-10-22): ไม่มีคน = ล็อกอย่างเดียว ไม่ออกจากระบบเอง
    # (ออก = แอปที่เปิดไว้หายหมด) · ผู้ใช้เปิดการออกเองได้ในหน้าตั้งค่า
    lock_min: int = 5
    logout_min: int = 0
    # กล้องช่วยดูว่าเจ้าของยังอยู่ (ขั้น C) · ต้องเปิดเอง (กล้องเปิดตอนไม่ได้แตะเครื่อง) · ค่า 30/30 ตามที่ Pakon เสนอ
    presence: bool = False
    presence_lock_s: int = 30
    presence_logout_s: int = 0
    # เตือนนัดจากปฏิทิน Google ก่อนเวลานัด (การ์ด 0032) · ค่าเริ่มต้น 10 นาที
    gcal_alert_min: int = 10
    language: str = "th"  # การ์ด 0039
    cloud_model: str = "sonnet"  # แชทงาน (การ์ด 0053) · จำตัวที่เลือกล่าสุด
    # ปลดจอล็อกเองเมื่อเห็นหน้า (การ์ด 0055) · กล้องเปิดตลอดตอนล็อก → ค่าเริ่มต้นปิด (H3)
    face_auto_unlock: bool = False
    # ฟังคำสั่งเสียง (คีย์ลัด) เฉพาะตอนหันหน้าเข้าจอ (การ์ด 0058) · กล้องเปิดระหว่างฟัง → ค่าเริ่มต้นปิด (H3)
    face_to_speak: bool = False
    cloud_effort: str = "medium"  # ระดับความคิดของแชทงาน (Pakon 2026-10-22) · จำตัวที่เลือกล่าสุด
    # ออกจากบัญชีเว็บทุกครั้งที่ออกจากระบบ (การ์ด 0031 รอบ 3) · ค่าเริ่มต้นปิด (ใช้เครื่องคนเดียวยังสะดวก)
    clear_web_on_logout: bool = False
    lock_policy: int = LOCK_POLICY

    def cleaned(self) -> UiPrefs:
        """ค่าที่อ่านจากไฟล์อาจถูกแก้มือหรือเสีย → ถอยไปค่าเริ่มต้นแทนการ crash."""
        theme = self.theme if self.theme in THEMES else "dark"
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
            else 0,
            presence=self.presence is True,
            presence_lock_s=self.presence_lock_s
            if self.presence_lock_s in PRESENCE_CHOICES and type(self.presence_lock_s) is int
            else 30,
            presence_logout_s=self.presence_logout_s
            if self.presence_logout_s in PRESENCE_LOGOUT_CHOICES
            and type(self.presence_logout_s) is int
            else 0,
            gcal_alert_min=self.gcal_alert_min
            if self.gcal_alert_min in GCAL_ALERT_CHOICES and type(self.gcal_alert_min) is int
            else 10,
            language=self.language if self.language in LANGS else "th",
            cloud_model=self.cloud_model if self.cloud_model in CLOUD_MODELS else "sonnet",
            face_auto_unlock=self.face_auto_unlock is True,
            face_to_speak=self.face_to_speak is True,
            cloud_effort=self.cloud_effort if self.cloud_effort in CLOUD_EFFORTS else "medium",
            clear_web_on_logout=self.clear_web_on_logout is True,
            lock_policy=LOCK_POLICY,
        )


def load(path: Path | None = None) -> UiPrefs:
    path = path or default_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # ไฟล์ก่อนการ์ด 0051: ค่าออกเองเดิม (10 นาที · กล้อง 30 วิ) เป็นค่าเริ่มต้นเก่า ไม่ใช่สิ่งที่ผู้ใช้ขอ → ไม่ออกเอง
        if data.get("lock_policy") != LOCK_POLICY:
            data["logout_min"] = data["presence_logout_s"] = 0
        return UiPrefs(
            theme=str(data.get("theme", "dark")),
            font_scale=float(data.get("font_scale", 1.0)),
            onboarded=data.get("onboarded") is True,
            speak_answers=data.get("speak_answers", True) is not False,
            speak_reminders=data.get("speak_reminders") is True,
            use_claude=data.get("use_claude", True) is not False,
            use_weather=data.get("use_weather", True) is not False,
            lock_min=data.get("lock_min", 5),
            logout_min=data.get("logout_min", 0),
            presence=data.get("presence") is True,
            presence_lock_s=data.get("presence_lock_s", 30),
            presence_logout_s=data.get("presence_logout_s", 0),
            gcal_alert_min=data.get("gcal_alert_min", 10),
            language=str(data.get("language", "th")),
            cloud_model=str(data.get("cloud_model", "sonnet")),
            face_auto_unlock=data.get("face_auto_unlock") is True,
            face_to_speak=data.get("face_to_speak") is True,
            cloud_effort=str(data.get("cloud_effort", "medium")),
            clear_web_on_logout=data.get("clear_web_on_logout") is True,
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
