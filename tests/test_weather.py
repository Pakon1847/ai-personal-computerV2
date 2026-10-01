"""สกิลอากาศ (aipc.skills.weather) · Open-Meteo ปลอม ไม่ต่อเน็ต.

ชุดอิสระวัดแยกใน docs/benchmarks/2026-10-02-weather
"""

import json
import unittest
from pathlib import Path

from aipc.skills.weather import Ask, Weather, answer, place_in, weather_intent

DATA = Path(__file__).parent / "data"
GEO = {
    "results": [
        {"name": "Chiang Mai", "country_code": "US", "latitude": 1, "longitude": 2},
        {"name": "เชียงใหม่", "country_code": "TH", "latitude": 18.79038, "longitude": 98.98468},
    ]
}
FC = {
    "current": {
        "temperature_2m": 24.6,
        "relative_humidity_2m": 93,
        "precipitation": 0.0,
        "weather_code": 0,
    },
    "daily": {
        "temperature_2m_max": [31.5, 31.1],
        "temperature_2m_min": [23.7, 23.7],
        "precipitation_probability_max": [36, 59],
        "weather_code": [51, 95],
    },
}


class IntentTest(unittest.TestCase):
    def test_live_weather_questions(self):
        cases = {
            "อากาศวันนี้เป็นยังไงบ้าง": ("today", ""),
            "พรุ่งนี้ กทม. ร้อนไหม": ("tomorrow", "กรุงเทพมหานคร"),
            "ตอนนี้เชียงใหม่อุณหภูมิกี่องศา": ("now", "เชียงใหม่"),
            "วันนี้โคราชต้องพกร่มไหม": ("today", "นครราชสีมา"),
            "พรุ่งนี้ที่ตากฝนตกไหม": ("tomorrow", "ตาก"),
        }
        for text, (day, city) in cases.items():
            with self.subTest(text=text):
                self.assertEqual(weather_intent(text), Ask(day, city))

    def test_knowledge_and_other_meanings_stay_with_ai(self):
        for text in (
            "ทำไมอากาศร้อนขึ้นทุกปี",
            "ฝนเกิดจากอะไร",
            "เครื่องปรับอากาศเสีย ต้องทำยังไง",
            "บรรยากาศวันนี้ดีจัง",
            "วันนี้คอมร้อนมาก",
            "ตั้งเตือนพรุ่งนี้ถ้าฝนตก",
            "ขอเพลงเกี่ยวกับฤดูหนาว",
        ):
            with self.subTest(text=text):
                self.assertIsNone(weather_intent(text))

    def test_drying_clothes_is_not_tak_province(self):
        # พบในชุดอิสระ 2026-10-02 · แก้หลังวัด
        self.assertEqual(place_in("วันนี้เหมาะจะตากผ้าไหม"), "")
        self.assertEqual(place_in("อากาศแม่สอด จังหวัดตาก"), "ตาก")

    def test_dev_set(self):
        # ชุดพัฒนา (ผู้ช่วยเห็นแล้ว) · ตอน commit กฎ 40/40 · ผิด 0/38
        items = json.loads((DATA / "weather_intent_dev.json").read_text("utf-8"))["items"]
        wrong = [
            i["text"]
            for i in items
            if (weather_intent(i["text"]) is not None) != (i["expect"] == "weather")
        ]
        self.assertEqual(wrong, [])


class LookupTest(unittest.TestCase):
    def setUp(self):
        self.calls, self.sent, self.t = [], [], 1000.0

        def get(url, params, timeout=10):
            self.calls.append((url, params))
            return GEO if "geocoding" in url else FC

        self.w = Weather(get=get, record=self.sent.append, now=lambda: self.t)

    def test_prefers_thai_place_and_records_what_leaves(self):
        place, fc = self.w.lookup("เชียงใหม่")
        self.assertEqual(place["name"], "เชียงใหม่")
        self.assertEqual(self.calls[1][1]["latitude"], 18.79)
        self.assertEqual(self.sent, ["ค้นพิกัดเมือง: เชียงใหม่", "ขอพยากรณ์อากาศที่พิกัด 18.79, 98.98"])

    def test_cache_15_minutes(self):
        self.w.lookup("เชียงใหม่")
        self.t += 600
        self.w.lookup("เชียงใหม่")
        self.assertEqual(len(self.calls), 2)  # ไม่ส่งซ้ำ
        self.t += 400
        self.w.lookup("เชียงใหม่")
        self.assertEqual(len(self.calls), 4)

    def test_unknown_city(self):
        w = Weather(get=lambda *a, **k: {"results": []})
        with self.assertRaises(LookupError):
            w.lookup("เมืองไม่มีจริง")

    def test_answer_text(self):
        place = GEO["results"][1]
        title, lines = answer(Ask("tomorrow", "เชียงใหม่"), place, FC)
        self.assertEqual(title, "เชียงใหม่ พรุ่งนี้ พายุฝนฟ้าคะนอง")
        self.assertIn("อุณหภูมิ 24–31°C", lines)
        self.assertIn("โอกาสฝนตก 59% · พกร่มไปด้วยดีกว่า", lines)
        title, lines = answer(Ask("now", "เชียงใหม่"), place, FC)
        self.assertEqual(title, "เชียงใหม่ ตอนนี้ ท้องฟ้าแจ่มใส")
        self.assertIn("อุณหภูมิ 25°C · ความชื้น 93%", lines)


if __name__ == "__main__":
    unittest.main()
