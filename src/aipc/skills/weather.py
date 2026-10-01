"""สกิลอากาศ: ถามพยากรณ์อากาศจริงจาก Open-Meteo โดยตรง (ไม่ผ่าน Claude).

ผล: docs/benchmarks/2026-10-02-weather

ทำไมเป็นโค้ด: สกิลที่ Claude สร้างเป็นไฟล์ขั้นตอนให้ AI ในเครื่อง ซึ่งต่อเน็ตไม่ได้ · ประตูตรวจห้ามสกิลเรียกเน็ต
Pakon ตัดสิน 2026-10-02: ไม่บอกเมือง = ถามกลับทุกครั้ง · ส่งแค่ชื่อเมือง/พิกัดไป Open-Meteo · บันทึกทุกครั้งที่ส่งออก
แหล่ง: Open-Meteo (ไม่ต้องมีคีย์ · CC BY 4.0 · ฟรีเฉพาะไม่ใช่เชิงพาณิชย์)
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

PROVINCES = """กรุงเทพมหานคร กระบี่ กาญจนบุรี กาฬสินธุ์ กำแพงเพชร ขอนแก่น
จันทบุรี ฉะเชิงเทรา ชลบุรี ชัยนาท ชัยภูมิ ชุมพร เชียงราย
เชียงใหม่ ตรัง ตราด ตาก นครนายก นครปฐม นครพนม นครราชสีมา
นครศรีธรรมราช นครสวรรค์ นนทบุรี นราธิวาส น่าน บึงกาฬ
บุรีรัมย์ ปทุมธานี ประจวบคีรีขันธ์ ปราจีนบุรี ปัตตานี
พระนครศรีอยุธยา พะเยา พังงา พัทลุง พิจิตร พิษณุโลก เพชรบุรี
เพชรบูรณ์ แพร่ ภูเก็ต มหาสารคาม มุกดาหาร แม่ฮ่องสอน ยโสธร
ยะลา ร้อยเอ็ด ระนอง ระยอง ราชบุรี ลพบุรี ลำปาง ลำพูน เลย
ศรีสะเกษ สกลนคร สงขลา สตูล สมุทรปราการ สมุทรสงคราม สมุทรสาคร
สระแก้ว สระบุรี สิงห์บุรี สุโขทัย สุพรรณบุรี สุราษฎร์ธานี
สุรินทร์ หนองคาย หนองบัวลำภู อ่างทอง อำนาจเจริญ อุดรธานี
อุตรดิตถ์ อุทัยธานี อุบลราชธานี""".split()
# ชื่อย่อ/ชื่อเล่น → ชื่อที่ใช้ค้นพิกัด · เมืองดังที่ไม่ใช่ชื่อจังหวัด
ALIASES = {
    "กทม.": "กรุงเทพมหานคร",
    "กทม": "กรุงเทพมหานคร",
    "กรุงเทพฯ": "กรุงเทพมหานคร",
    "กรุงเทพ": "กรุงเทพมหานคร",
    "บางกอก": "กรุงเทพมหานคร",
    "โคราช": "นครราชสีมา",
    "อุบล": "อุบลราชธานี",
    "อุดร": "อุดรธานี",
    "สุราษฎร์": "สุราษฎร์ธานี",
    "อยุธยา": "พระนครศรีอยุธยา",
    "นครศรีฯ": "นครศรีธรรมราช",
    "นครศรี": "นครศรีธรรมราช",
    "ปากน้ำ": "สมุทรปราการ",
    "หาดใหญ่": "หาดใหญ่",
    "พัทยา": "พัทยา",
    "หัวหิน": "หัวหิน",
    "เกาะสมุย": "เกาะสมุย",
    "สมุย": "เกาะสมุย",
    "ปาย": "ปาย",
    "เขาใหญ่": "ปากช่อง",
    "แม่สาย": "แม่สาย",
    "เบตง": "เบตง",
}
PLACES = sorted([*PROVINCES, *ALIASES], key=len, reverse=True)

WEATHER = re.compile(
    r"ฝน|ร้อน|หนาว|อุณหภูมิ|กี่องศา|(?<!บรร)(?<!ปรับ)(?<!ทาง)อากาศ|ร่ม|ฟ้า\S{0,3}(โปร่ง|ครึ้ม|มืด|ใส)|เมฆ|แดด|พายุ|ความชื้น|ลม(แรง)?"
)
TIME = re.compile(r"วันนี้|ตอนนี้|พรุ่งนี้|คืนนี้|เช้านี้|บ่ายนี้|เย็นนี้|ข้างนอก|ขณะนี้|พยากรณ์")
# ความหมายอื่น: เครื่องใช้/อุปกรณ์ · ตั้งเตือน · เพลง/หนัง · ความรู้ทั่วไป
NOT_WEATHER = re.compile(
    r"ตั้ง(เตือน|ปลุก)|เตือน|ปลุก|เพลง|หนัง|นิทาน|หนังสือ|แอร์|คอม|เครื่อง|cpu|ซีพียู|ตู้เย็น|พัดลม|น้ำเย็น|"
    r"ดาวตก|พายุสุริยะ|ทำไม|อธิบาย|คืออะไร|เกิดจาก|ยังไงถึง|ภาวะโลกร้อน|มลพิษ|แปล",
    re.I,
)
NOW = re.compile(r"ตอนนี้|ข้างนอก|ขณะนี้|อยู่ไหม|รึยัง|หรือยัง")


@dataclass
class Ask:
    day: str  # today | now | tomorrow
    city: str  # "" = ไม่ได้บอกเมือง (ถามกลับ)


def place_in(text: str) -> str:
    """ชื่อจังหวัด/เมืองในประโยค (ชื่อเต็มที่ใช้ค้นพิกัด) · ไม่มี = ""."""
    for p in PLACES:
        if p in text:
            return ALIASES.get(p, p)
    return ""


def weather_intent(text: str) -> Ask | None:
    t = text.strip()
    if not t or NOT_WEATHER.search(t) or not WEATHER.search(t) or not TIME.search(t):
        return None
    day = "tomorrow" if "พรุ่งนี้" in t else "now" if NOW.search(t) else "today"
    return Ask(day, place_in(t))


# ---------- Open-Meteo ----------
WMO = {
    0: "ท้องฟ้าแจ่มใส",
    1: "ท้องฟ้าโปร่งเป็นส่วนใหญ่",
    2: "มีเมฆบางส่วน",
    3: "เมฆมาก",
    45: "มีหมอก",
    48: "มีหมอกน้ำค้างแข็ง",
    51: "ฝนปรอยเล็กน้อย",
    53: "ฝนปรอย",
    55: "ฝนปรอยหนาแน่น",
    61: "ฝนตกเล็กน้อย",
    63: "ฝนตกปานกลาง",
    65: "ฝนตกหนัก",
    80: "ฝนตกเป็นช่วง ๆ",
    81: "ฝนตกเป็นช่วง ๆ ปานกลาง",
    82: "ฝนตกเป็นช่วง ๆ หนัก",
    95: "พายุฝนฟ้าคะนอง",
    96: "พายุฝนฟ้าคะนองมีลูกเห็บ",
    99: "พายุฝนฟ้าคะนองมีลูกเห็บหนัก",
}
GEO = "https://geocoding-api.open-meteo.com/v1/search"
CURRENT = "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
DAILY = "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
FORECAST = "https://api.open-meteo.com/v1/forecast"


def _get(url: str, params: dict, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=timeout) as r:
        return json.loads(r.read())


class Weather:
    """ค้นพิกัด + พยากรณ์ · จำผล 15 นาทีต่อเมือง · record(ข้อความที่ส่งออก) = บันทึกสิ่งที่ส่งออกนอกเครื่อง."""

    CACHE_S = 900

    def __init__(self, get=_get, record=lambda sent: None, now=time.time):
        self._get = get
        self._record = record
        self._now = now
        self._cache: dict[str, tuple[float, dict, dict]] = {}

    def lookup(self, city: str) -> tuple[dict, dict]:
        """(สถานที่, พยากรณ์) · ไม่พบเมือง = LookupError · เน็ตไม่ได้ = OSError."""
        hit = self._cache.get(city)
        if hit and self._now() - hit[0] < self.CACHE_S:
            return hit[1], hit[2]
        self._record(f"ค้นพิกัดเมือง: {city}")
        geo = self._get(GEO, {"name": city, "count": 5, "language": "th", "format": "json"})
        places = (
            [p for p in geo.get("results") or [] if p.get("country_code") == "TH"]
            or geo.get("results")
            or []
        )
        if not places:
            raise LookupError(city)
        place = places[0]
        lat, lon = round(place["latitude"], 2), round(place["longitude"], 2)
        self._record(f"ขอพยากรณ์อากาศที่พิกัด {lat}, {lon}")
        fc = self._get(FORECAST, {
            "latitude": lat, "longitude": lon, "timezone": "Asia/Bangkok", "forecast_days": 2,
            "current": CURRENT, "daily": DAILY,
        })  # fmt: skip
        self._cache[city] = (self._now(), place, fc)
        return place, fc


def answer(ask: Ask, place: dict, fc: dict) -> tuple[str, list[str]]:
    """หัวข้อ + บรรทัดรายละเอียดภาษาไทย (ไม่แต่งค่าที่ไม่มี)."""
    name = place.get("name", "")
    daily = fc.get("daily") or {}
    i = 1 if ask.day == "tomorrow" else 0

    def d(key):
        v = daily.get(key) or []
        return v[i] if len(v) > i else None

    lines = []
    if ask.day == "now":
        cur = fc.get("current") or {}
        title = f"{name} ตอนนี้ {WMO.get(cur.get('weather_code'), 'ไม่ทราบสภาพท้องฟ้า')}"
        if cur.get("temperature_2m") is not None:
            rh = cur.get("relative_humidity_2m", "—")
            lines.append(f"อุณหภูมิ {cur['temperature_2m']:.0f}°C · ความชื้น {rh}%")
        if cur.get("precipitation"):
            lines.append(f"ฝนตกอยู่ {cur['precipitation']} มม.")
    else:
        when = "พรุ่งนี้" if ask.day == "tomorrow" else "วันนี้"
        title = f"{name} {when} {WMO.get(d('weather_code'), 'ไม่ทราบสภาพท้องฟ้า')}"
        lo, hi = d("temperature_2m_min"), d("temperature_2m_max")
        if lo is not None and hi is not None:
            lines.append(f"อุณหภูมิ {lo:.0f}–{hi:.0f}°C")
    rain = d("precipitation_probability_max")
    if rain is not None:
        lines.append(f"โอกาสฝนตก {rain}%" + (" · พกร่มไปด้วยดีกว่า" if rain >= 50 else ""))
    lines.append("ข้อมูลจาก Open-Meteo (CC BY 4.0) · ส่งแค่ชื่อเมืองและพิกัดออกนอกเครื่อง")
    return title, lines
