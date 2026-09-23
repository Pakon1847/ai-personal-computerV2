"""วันที่แบบไทยสำหรับแถบสถานะและหน้า Login · เขียนเองแทนการพึ่ง locale ของ OS
เพราะ Raspberry Pi OS ที่ลงใหม่มักไม่มี locale ไทย และผลจะต่างกันไปแต่ละเครื่อง."""

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


def clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def long_date(dt: datetime) -> str:
    """เช่น 'วันพุธที่ 23 กันยายน 2569'."""
    return f"วัน{DAYS[dt.weekday()]}ที่ {dt.day} {MONTHS[dt.month - 1]} {dt.year + BE_OFFSET}"


def short_date(dt: datetime) -> str:
    """เช่น 'พ. 23 ก.ย.' สำหรับแถบสถานะที่พื้นที่น้อย."""
    return f"{DAYS_SHORT[dt.weekday()]} {dt.day} {MONTHS_SHORT[dt.month - 1]}"
