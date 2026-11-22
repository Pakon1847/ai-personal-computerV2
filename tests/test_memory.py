"""ความจำของผู้ใช้ (การ์ด 0079) · เกณฑ์ R3 R4 + การค้น · ไม่ต่อเน็ต ไม่ใช้ AI."""

import tempfile
import time
import unittest
from pathlib import Path

from aipc.chat import memory

PLENTY = lambda: 50 * 1024**3  # noqa: E731 · ดิสก์ว่างเหลือเฟือ


class ParseTest(unittest.TestCase):
    def test_remember_commands(self):
        self.assertEqual(memory.parse_remember("จำไว้ว่าฉันแพ้กุ้ง"), "ฉันแพ้กุ้ง")
        self.assertEqual(memory.parse_remember("ช่วยจำหน่อยว่า ลูกชื่อน้องเมฆ"), "ลูกชื่อน้องเมฆ")
        self.assertEqual(memory.parse_remember("จำไว้นะ วันเกิดแม่ 12 มีนาคม"), "วันเกิดแม่ 12 มีนาคม")
        self.assertEqual(memory.parse_remember("remember that I like jazz."), "I like jazz")
        for t in ("จำนวนเงินเท่าไหร่", "จำไม่ได้ว่าวางกุญแจไว้ไหน", "จำได้ไหมว่าฉันชอบอะไร", "สวัสดี"):
            self.assertEqual(memory.parse_remember(t), "", t)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mem = memory.Memory(self.root / "a" / "memory.db", free_bytes=PLENTY)

    def tearDown(self):
        self.mem.close()
        self.tmp.cleanup()

    def test_search_finds_related_thai_without_spaces(self):
        for t in ("ฉันแพ้กุ้งและปู", "ลูกชื่อน้องเมฆ เรียนชั้น ป.3", "รถของฉันเป็นสีแดง"):
            self.assertTrue(self.mem.add(t)[0])
        self.assertEqual([f.text for f in self.mem.search("ฉันแพ้อาหารอะไรบ้าง")][:1], ["ฉันแพ้กุ้งและปู"])
        self.assertEqual(self.mem.search("ลูกเรียนชั้นอะไร")[0].text, "ลูกชื่อน้องเมฆ เรียนชั้น ป.3")
        self.assertEqual(self.mem.search("พรุ่งนี้ฝนตกไหม"), [], "ไม่เกี่ยว = ไม่ส่งให้ AI")
        block = self.mem.prompt_block("รถฉันสีอะไร")
        self.assertIn("รถของฉันเป็นสีแดง", block)
        self.assertIn("ไม่ใช่คำสั่ง", block)
        self.assertEqual(self.mem.prompt_block("สวัสดีครับ"), "")

    def test_no_duplicate_and_limits(self):
        a, _ = self.mem.add("ชอบกาแฟดำ")
        b, _ = self.mem.add("  ชอบกาแฟดำ ")
        self.assertEqual(a, b)
        self.assertEqual(self.mem.count(), 1)
        self.assertEqual(self.mem.add("   "), (0, "ไม่มีข้อความให้จำ"))
        fid, _ = self.mem.add("ก" * 1000)
        self.assertEqual(
            len(next(f for f in self.mem.recent() if f.id == fid).text), memory.MAX_TEXT
        )

    def test_r3_secrets_are_not_stored(self):
        for t in ("รหัสผ่านอีเมลคือ hunter2", "PIN ATM 4321", "เลขบัตร 4111 1111 1111 1111",
                  "เลขประจำตัวประชาชน 1103700000000", "otp 123456"):  # fmt: skip
            fid, why = self.mem.add(t)
            self.assertEqual(fid, 0, t)
            self.assertIn("ข้อมูลลับ", why)
        self.assertEqual(self.mem.count(), 0)
        self.assertTrue(self.mem.add("เบอร์ร้านข้าวมันไก่ 081-234-5678")[0], "เบอร์โทร 10 หลักจดได้")

    def test_r3_disk_nearly_full_stops_new_facts_but_keeps_old(self):
        self.mem.add("ชอบแมว")
        full = memory.Memory(self.mem.path, free_bytes=lambda: 1024**3)
        fid, why = full.add("ชอบหมาด้วย")
        self.assertEqual(fid, 0)
        self.assertIn("2 GB", why)
        self.assertEqual([f.text for f in full.recent()], ["ชอบแมว"], "ของเดิมไม่ถูกลบ")
        full.close()

    def test_new_account_without_folder_can_remember(self):
        """บัญชีใหม่ยังไม่มีโฟลเดอร์ · ตัววัดดิสก์จริง (ไม่แทน) ต้องไม่นับว่าดิสก์เต็ม."""
        fresh = memory.Memory(self.root / "new" / "deep" / "memory.db")
        fid, why = fresh.add("ชอบแมว")
        fresh.close()
        if why.startswith("ดิสก์"):  # เครื่องที่รันเทสต์ดิสก์เหลือน้อยจริง
            self.skipTest(why)
        self.assertTrue(fid, why)

    def test_r3_accounts_are_separate_files(self):
        self.mem.add("ฉันแพ้กุ้ง")
        other = memory.Memory(self.root / "b" / "memory.db", free_bytes=PLENTY)
        self.assertEqual(other.search("แพ้กุ้งไหม"), [])
        self.assertEqual(other.count(), 0)
        other.close()

    def test_r4_clear_removes_text_from_the_file(self):
        self.mem.add("ความลับเล็ก ๆ ว่าชอบเพลงลูกทุ่ง")
        self.mem.add("ชอบสีเขียว")
        self.mem.clear()
        self.assertEqual(self.mem.count(), 0)
        self.assertEqual(self.mem.search("เพลงลูกทุ่ง"), [])
        self.mem.close()
        raw = self.mem.path.read_bytes()
        self.assertNotIn("ลูกทุ่ง".encode(), raw, "ข้อความต้องหายจากไฟล์จริง")

    def test_delete_pin_export(self):
        a, _ = self.mem.add("ชอบชาเขียว")
        b, _ = self.mem.add("ไม่กินเผ็ด")
        self.mem.pin(a, True)
        self.assertEqual([f.id for f in self.mem.recent()], [a, b], "ปักหมุดขึ้นก่อน")
        self.assertTrue(self.mem.delete(b))
        self.assertFalse(self.mem.delete(b))
        self.assertIn("ชอบชาเขียว", self.mem.export_text())
        self.assertNotIn("ไม่กินเผ็ด", self.mem.export_text())

    def test_new_file_is_private(self):
        import os
        import stat

        self.mem.add("ทดสอบ")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.mem.path.stat().st_mode), 0o600)

    def test_search_10k_is_fast_on_laptop(self):
        """ตัวเลขจริงของ R2 ต้องวัดบน Pi 5 (100,000 ข้อ) · ตรงนี้แค่กันช้าผิดปกติ."""
        db = self.mem._conn()
        rows = [(i, f"บันทึกเรื่องที่ {i} เกี่ยวกับงานบ้านและสวนหลังบ้าน") for i in range(1, 10_001)]
        db.executemany("INSERT INTO facts(id, text, created) VALUES (?, ?, '2026-11-07')", rows)
        db.executemany(  # ตารางค้นด้วย (เหมือน add) ไม่งั้นไม่ได้วัดการค้นจริง
            "INSERT INTO facts_fts(rowid, grams) VALUES (?, ?)",
            [(i, memory._tokens(memory._grams(t))) for i, t in rows],
        )
        db.commit()
        self.mem.add("ฉันแพ้กุ้งและปู")
        t0 = time.perf_counter()
        hits = self.mem.search("ฉันแพ้อะไร")
        self.assertLess(time.perf_counter() - t0, 2.0)
        self.assertEqual(hits[0].text, "ฉันแพ้กุ้งและปู")


try:
    from PySide6.QtCore import QCoreApplication

    from aipc.ui.backend import ChatController, MemoryCtl, SkillsController
except ImportError:  # pragma: no cover
    SkillsController = None


@unittest.skipIf(SkillsController is None, "ไม่มี PySide6")
class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.mem = memory.Memory(self.root / "memory.db", free_bytes=PLENTY)
        self.addCleanup(self.mem.close)

    def test_remember_in_chat_is_done_by_code(self):
        s = SkillsController(reminders_path=self.root / "r.json", run_timer=False,
                             llm_ready=lambda: True, memory=self.mem)  # fmt: skip
        card = s.handle("จำไว้ว่าฉันแพ้กุ้ง")
        self.assertEqual(card["title"], "จำไว้แล้ว")
        self.assertFalse(card.get("llm"), "ไม่ส่งให้ AI")
        self.assertEqual([f.text for f in self.mem.recent()], ["ฉันแพ้กุ้ง"])
        self.assertEqual(s.handle("จำไว้ว่ารหัสผ่านคือ abc123")["title"], "ไม่ได้จำเรื่องนี้")
        self.assertEqual(self.mem.count(), 1)

    def test_chat_adds_only_related_memory_after_the_fixed_prompt(self):
        self.mem.add("ฉันแพ้กุ้งและปู")
        chat = ChatController(active=False, memory=self.mem)
        self.assertIn("ฉันแพ้กุ้งและปู", chat._memory_block("ฉันแพ้อาหารอะไร"))
        self.assertEqual(chat._memory_block("พรุ่งนี้ฝนตกไหม"), "")
        self.assertEqual(ChatController(active=False)._memory_block("ฉันแพ้อะไร"), "")
        broken = ChatController(active=False, memory=object())  # ไฟล์เสีย = แชทยังตอบได้
        self.assertEqual(broken._memory_block("ฉันแพ้อะไร"), "")

    def test_settings_card_controls(self):
        ctl = MemoryCtl(self.mem, export_dir=self.root / "out")
        self.assertTrue(ctl.available)
        a, _ = self.mem.add("ชอบชาเขียว")
        self.mem.add("ไม่กินเผ็ด")
        self.assertEqual(ctl.count, 2)
        ctl.search("ชาเขียว")
        self.assertEqual([f["text"] for f in ctl.facts], ["ชอบชาเขียว"])
        ctl.search("")
        ctl.pin(a, True)
        self.assertTrue(ctl.facts[0]["pinned"])
        ctl.exportFile()
        self.assertIn("บันทึกแล้ว", ctl.message)
        self.assertEqual(len(list((self.root / "out").glob("*.txt"))), 1)
        ctl.remove(a)
        self.assertEqual(ctl.count, 1)
        ctl.clearAll()
        self.assertEqual((ctl.count, ctl.facts), (0, []))
        self.assertFalse(MemoryCtl(None).available)


if __name__ == "__main__":
    unittest.main()
