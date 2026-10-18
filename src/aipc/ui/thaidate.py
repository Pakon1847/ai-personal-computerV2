"""วันที่แบบไทยสำหรับแถบสถานะและหน้า Login · เขียนเองแทนการพึ่ง locale ของ OS
เพราะ Raspberry Pi OS ที่ลงใหม่มักไม่มี locale ไทย และผลจะต่างกันไปแต่ละเครื่อง.

ภาษาอังกฤษ (การ์ด 0039): ฟังก์ชันที่แสดงบนจอดูภาษาจาก aipc.i18n · อังกฤษใช้ ค.ศ. และชื่อเดือนอังกฤษ ·
ข้อความวันที่ที่ส่งให้ AI (cloud/ask.py · catalog.py) ใช้ DAYS/MONTHS ภาษาไทยตรง ๆ ไม่เปลี่ยน"""

from __future__ import annotations

from datetime import datetime

DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
DAYS_SHORT = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]
MONTHS = [
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
]
MONTHS_SHORT = [
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
]
BE_OFFSET = 543  # พ.ศ. = ค.ศ. + 543
EN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]  # fmt: skip


def _en() -> bool:
    from aipc import i18n

    return i18n.lang() == "en"


def year(dt) -> int:
    """ปีที่แสดงบนจอ: ไทย = พ.ศ. · อังกฤษ = ค.ศ. · รับวันที่หรือเลขปี ค.ศ."""
    y = dt if isinstance(dt, int) else dt.year
    return y if _en() else y + BE_OFFSET


def month_name(month: int) -> str:
    return EN_MONTHS[month - 1] if _en() else MONTHS[month - 1]


def month_short(month: int) -> str:
    return EN_MONTHS[month - 1][:3] if _en() else MONTHS_SHORT[month - 1]


def clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def greeting(dt: datetime) -> str:
    """คำทักตามช่วงเวลา: เช้า 05–11 · บ่าย 12–16 · เย็น 17–19 · ค่ำ 20–04."""
    h = dt.hour
    if _en():
        return (
            "Good morning" if 5 <= h < 12 else "Good afternoon" if 12 <= h < 17 else "Good evening"
        )
    if 5 <= h < 12:
        return "สวัสดีตอนเช้า"
    if 12 <= h < 17:
        return "สวัสดีตอนบ่าย"
    if 17 <= h < 20:
        return "สวัสดีตอนเย็น"
    return "สวัสดีตอนค่ำ"


def long_date(dt: datetime) -> str:
    """เช่น 'วันพุธที่ 23 กันยายน 2569' · อังกฤษ 'Wednesday, 23 September 2026'."""
    if _en():
        return f"{EN_DAYS[dt.weekday()]}, {dt.day} {EN_MONTHS[dt.month - 1]} {dt.year}"
    return f"วัน{DAYS[dt.weekday()]}ที่ {dt.day} {MONTHS[dt.month - 1]} {dt.year + BE_OFFSET}"


def short_date(dt: datetime) -> str:
    """เช่น 'พ. 23 ก.ย.' สำหรับแถบสถานะที่พื้นที่น้อย · อังกฤษ 'Wed 23 Sep'."""
    if _en():
        return f"{EN_DAYS[dt.weekday()][:3]} {dt.day} {EN_MONTHS[dt.month - 1][:3]}"
    return f"{DAYS_SHORT[dt.weekday()]} {dt.day} {MONTHS_SHORT[dt.month - 1]}"
