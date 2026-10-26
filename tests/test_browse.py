"""ตัวแปลคำสั่งเว็บด้วยเสียง (การ์ด 0024)."""

import json
import unittest
from pathlib import Path

from aipc.skills import browse

DATA = Path(__file__).parent / "data"


def parsed(text):
    return [c.as_dict() for c in browse.parse(text)]


class BrowseParseTest(unittest.TestCase):
    def test_pakon_example(self):
        # ตัวอย่างของ Pakon 2026-10-13: "ค้นหาราคาทองหน่อยเข้าลิ้งค์แรก" · "ย้อนกลับ"
        want = [{"kind": "search", "query": "ราคาทอง"}, {"kind": "open", "n": 1}]
        self.assertEqual(parsed("ค้นหาราคาทองหน่อยเข้าลิ้งค์แรก"), want)
        self.assertEqual(parsed("ย้อนกลับ"), [{"kind": "back"}])

    def test_numbers_and_spellings(self):
        for text, n in [("เข้าลิงก์ที่สอง", 2), ("เปิดลิงค์ที่ 3", 3), ("คลิกอันที่สี่", 4),
                        ("เข้าลิ้งแรก", 1), ("เปิดเว็บที่สิบ", 10)]:  # fmt: skip
            self.assertEqual(parsed(text), [{"kind": "open", "n": n}], text)

    def test_whisper_style_text(self):
        # whisper ถอดมามีวรรคตอน/คำลงท้าย/ตัวพิมพ์ใหญ่
        self.assertEqual(
            parsed("ค้นหา Raspberry Pi 5 ครับ."), [{"kind": "search", "query": "raspberry pi 5"}]
        )
        self.assertEqual(parsed(" เลื่อนลงหน่อยค่ะ "), [{"kind": "scroll", "direction": "down"}])

    def test_find_price_is_web_search(self):
        # "หาราคา…" เคยถูกกันเพราะกฎ "หาร" (หารเลข) · การ์ด 0026 ชุด H
        self.assertEqual(parsed("หาราคาทอง"), [{"kind": "search", "query": "ราคาทอง"}])
        self.assertEqual(parsed("หาราคารถมือสอง"), [{"kind": "search", "query": "ราคารถมือสอง"}])
        self.assertEqual(parsed("หาร 10 ด้วย 2"), [])
        self.assertEqual(parsed("หารสองได้เท่าไหร่"), [])

    def test_dev_phrasings_round2(self):
        # การ์ด 0026 รอบ 2: ถ้อยคำจากชุดพัฒนา D (ไม่ใช่ชุดทดสอบ)
        self.assertEqual(parsed("เลื่อนลงไปดูต่อ"), [{"kind": "scroll", "direction": "down"}])
        self.assertEqual(parsed("เลื่อนกลับขึ้นไปข้างบนหน่อย"), [{"kind": "scroll", "direction": "up"}])
        self.assertEqual(parsed("ปิดแท็บนี้ไปเลย"), [{"kind": "close"}])
        self.assertEqual(parsed("ไปหน้าถัดไปหน่อย"), [{"kind": "forward"}])
        self.assertEqual(parsed("ราคาน้ำมันพรุ่งนี้ ช่วยหาให้หน่อย"),
                         [{"kind": "search", "query": "ราคาน้ำมันพรุ่งนี้"}])  # fmt: skip
        # กริยาท้ายประโยคแต่เป็นงานในเครื่อง / "หา" เดี่ยวท้ายประโยค = ไม่ใช่ค้นเว็บ
        self.assertEqual(parsed("ผลของการประชุมครั้งก่อนสรุปไว้ในไฟล์ไหน ช่วยหาให้หน่อย"), [])
        self.assertEqual(parsed("ของที่ต้องหา"), [])
        self.assertEqual(parsed("เลื่อนนัดไปพรุ่งนี้"), [])

    def test_heard_fixes_round2(self):
        # ตัวถอดเสียงได้ยินเพี้ยน (ชุดพัฒนา V1 V2 D เสียง Piper)
        self.assertEqual(parsed("เปิดกู้เกิน"), [{"kind": "site", "site": "google"}])
        self.assertEqual(parsed("กฎลิงที่สาม"), [{"kind": "open", "n": 3}])
        self.assertEqual(parsed("ยานกลับไปหน้าที่แล้ว"), [{"kind": "back"}])
        self.assertEqual(parsed("ถอยกลับไปนะก่อนหน้า"), [{"kind": "back"}])
        self.assertEqual(parsed("รีโลด"), [{"kind": "reload"}])
        self.assertEqual(parsed("ยานพาหนะกลับบ้าน"), [])

    def test_natural_phrasings_round3(self):
        # การ์ด 0026 รอบ 3: สำนวนจากชุด H2 (ใช้แล้ว = ชุดพัฒนา) · กฎทั่วไป ไม่ใช่ทีละประโยค
        cases = {
            "ขอกลับไปหน้าที่แล้วค่ะ": [{"kind": "back"}],
            "กดย้อนกลับให้หน่อย": [{"kind": "back"}],
            "กดปุ่มไปข้างหน้าให้หน่อยค่ะ": [{"kind": "forward"}],
            "หน้านี้ค้าง ช่วยโหลดใหม่ให้หน่อยค่ะ": [{"kind": "reload"}],
            "สกรอลล์ลงอีกนิด": [{"kind": "scroll", "direction": "down"}],
            "ขอดูผลที่หกหน่อย": [{"kind": "open", "n": 6}],
            "เข้าไปดูเว็บลำดับที่หนึ่งค่ะ": [{"kind": "open", "n": 1}],
            "สลับไปหน้าต่างผู้ช่วยค่ะ": [{"kind": "app"}],
            "เข้ากูเกิลหน่อยครับ": [{"kind": "site", "site": "google"}],
            "ช่วยเปิดแผนที่กูเกิลให้ทีครับ": [{"kind": "site", "site": "maps"}],
            "ไปที่วิกิพีเดียให้หน่อย": [{"kind": "site", "site": "wikipedia"}],
            "ปิดแท็บนี้แล้วกลับไปหน้าผู้ช่วยครับ": [{"kind": "close"}, {"kind": "app"}],
            "ย้อนกลับแล้วเปิดลิงก์ที่สามแทน": [{"kind": "back"}, {"kind": "open", "n": 3}],
            "ราคาน้ำมันวันนี้ ลองกูเกิลดูหน่อย": [{"kind": "search", "query": "ราคาน้ำมันวันนี้"}],
            "ข่าวเศรษฐกิจวันนี้ หาให้หน่อยสิ": [{"kind": "search", "query": "ข่าวเศรษฐกิจวันนี้"}],
        }
        for text, want in cases.items():
            self.assertEqual(parsed(text), want, text)
        # ไม่ใช่ค้นเว็บ: ของหาย · หาเพื่อนคุย · "กูเกิล" ท้ายประโยคที่ไม่มี "ดู"
        for text in ["หาแว่นตาไม่เจอเลย วางไว้ไหนนะ", "หาเพื่อนคุยหน่อย เหงาจัง", "ของที่ต้องหา"]:
            self.assertEqual(parsed(text), [], text)
        self.assertEqual(parsed("ช่วยเปิดกูเกิลให้หน่อย"), [{"kind": "site", "site": "google"}])

    def test_local_work_is_not_web(self):
        # หาไฟล์/โน้ตในเครื่อง · เลื่อนนัด · ย้อนงานเดิม · ต้นคำ "หา" อื่น ๆ = ไปทางเดิมของแอป
        for text in ["ค้นหาไฟล์รายงาน", "หาโน้ตที่จดไว้วันนี้ให้หน่อย", "หาใบเสร็จค่าซ่อมรถ",
                     "เลื่อนนัดประชุมไปพรุ่งนี้", "ย้อนกลับเมื่อกี้ที่ปรับเสียง", "หากต้องการสอบถาม",
                     "หาดใหญ่", "หาค่าเฉลี่ยของ 4 6 8", "กูเกิลก่อตั้งปีไหน", "ปิดเสียง", ""]:  # fmt: skip
            self.assertEqual(parsed(text), [], text)

    def test_v1_dev_set(self):
        items = json.loads((DATA / "browse_v1.json").read_text(encoding="utf-8"))["items"]
        wrong = [it["text"] for it in items if parsed(it["text"]) != it["expect"]]
        # 1 ข้อที่ยอมพลาด: "กูเกิลวิธีทำไข่เจียว" (กูเกิล + คำค้นตรง ๆ ชนกับ "กูเกิลก่อตั้งปีไหน" ในชุดเดิม)
        self.assertEqual(wrong, ["กูเกิลวิธีทำไข่เจียว"])

    def test_v2_non_commands_never_caught(self):
        items = json.loads((DATA / "browse_v2.json").read_text(encoding="utf-8"))["items"]
        caught = [it["text"] for it in items if not it["expect"] and parsed(it["text"])]
        self.assertEqual(caught, [])


class PoliteTailTest(unittest.TestCase):
    """ตรวจทั้งระบบ 2026-10-18 ข้อ 2.4 2.5 2.11 · ประโยคไม่ซ้ำกับชุดวัด."""

    def test_word_final_syllables_stay_in_query(self):
        # พยางค์ท้ายที่หน้าตาเหมือนคำลงท้าย (คะ นะ ที แทน เลย) แต่เป็นส่วนของคำค้น
        for text, query in [("ค้นหาท่าโยคะ", "ท่าโยคะ"), ("ค้นหาทีมไหนชนะ", "ทีมไหนชนะ"),
                            ("ค้นหาทัศนะ", "ทัศนะ"), ("ค้นหาต้มไข่กี่นาที", "ต้มไข่กี่นาที"),
                            ("ค้นหาบริษัทไอที", "บริษัทไอที"),
                            ("ค้นหาที่เที่ยวจังหวัดเลย", "ที่เที่ยวจังหวัดเลย"),
                            ("ค้นหาตัวแทนประกัน", "ตัวแทนประกัน"),
                            ("ค้นหาพลังงานทดแทน", "พลังงานทดแทน")]:  # fmt: skip
            self.assertEqual(parsed(text), [{"kind": "search", "query": query}], text)

    def test_polite_words_still_removed(self):
        # คำที่ไม่มีทางเป็นท้ายคำ (ครับ ค่ะ หน่อย ให้ที) ตัดเสมอ · คำที่อาจเป็นพยางค์ ตัดเมื่อตามหลังคำกลุ่มแรก
        for text in ["ค้นหาราคาข้าวสารหน่อยนะ", "ค้นหาราคาข้าวสารให้หน่อยครับ", "ค้นหาราคาข้าวสารให้ที",
                     "ช่วยค้นหาราคาข้าวสารด้วยนะคะ", "ราคาข้าวสาร ช่วยค้นหาให้หน่อยค่ะ"]:  # fmt: skip
            self.assertEqual(parsed(text), [{"kind": "search", "query": "ราคาข้าวสาร"}], text)
        self.assertEqual(parsed("ย้อนกลับเลยนะ"), [{"kind": "back"}])  # คำสั่งตายตัว: ตัดได้ทุกคำลงท้าย
        self.assertEqual(parsed("เลื่อนลงทีสิ"), [{"kind": "scroll", "direction": "down"}])

    def test_no_freeze_on_repeated_polite_words(self):
        # เดิม regex ลองแบ่ง "ให้หน่อย" ได้หลายแบบ → 20 ครั้ง ~1.3 วิ และเพิ่มเท่าตัวทุกคำ (จอค้าง)
        import time

        start = time.perf_counter()
        browse.parse("ค้นหา" + "ให้หน่อย" * 2000 + "ก")
        self.assertLess(time.perf_counter() - start, 0.5)

    def test_search_verb_without_query_is_not_sent(self):
        # เดิมได้คำค้น "หา" แล้วส่งออก · "หา + เปิดลิงก์" = เปิดลิงก์ ไม่ส่งคำสั่งไปเป็นคำค้น
        for text in ["ค้นหาหน่อยครับ", "ช่วยค้นหาอีกที", "เสิร์ชเลย"]:
            self.assertEqual(parsed(text), [], text)
        self.assertEqual(parsed("ค้นหา คลิกลิงก์ที่สอง"), [{"kind": "open", "n": 2}])


class LoginParseTest(unittest.TestCase):
    """เข้าสู่ระบบ Google ด้วยเสียง (การ์ด 0064): Google ไม่ให้กรอกรหัสในเบราว์เซอร์ที่ถูกคุม → หน้าต่างแบบไม่คุม."""

    def test_login_phrasings(self):
        for text in ["เข้าสู่ระบบยูทูบ", "ล็อกอินยูทูบ", "ล็อคอินยูทูป", "login youtube",
                     "เข้าสู่ระบบ youtube ให้หน่อย", "ลงชื่อเข้าใช้ยูทูบ", "เข้าสู่ระบบกูเกิล",
                     "ล็อกอินเข้ายูทูบ", "เข้าสู่ระบบจีเมล", "ล็อกอิน gmail"]:  # fmt: skip
            self.assertEqual(parsed(text), [{"kind": "login", "site": "google"}], text)

    def test_not_login(self):
        # ไม่บอกเว็บ = ไม่รู้ว่าเข้าอะไร (อาจหมายถึงบัญชีเครื่อง) · เว็บที่ไม่ใช่บัญชี Google ไม่ใช่คำสั่งนี้
        for text in ["เข้าสู่ระบบ", "ล็อกอินเฟซบุ๊ก"]:
            self.assertEqual(parsed(text), [], text)
        self.assertEqual(parsed("เปิดยูทูบ"), [{"kind": "site", "site": "youtube"}])


if __name__ == "__main__":
    unittest.main()
