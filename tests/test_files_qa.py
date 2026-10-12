"""ถาม AI ในเครื่องเกี่ยวกับไฟล์ของฉัน (ฟีเจอร์ข้อ 4) · ไม่ต่อเน็ต."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from aipc import files_qa


class ExtractTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def test_text_and_thai_legacy_encoding(self):
        (self.dir / "a.txt").write_text("สวัสดี", encoding="utf-8")
        (self.dir / "b.txt").write_bytes("ประชุม".encode("cp874"))
        self.assertEqual(files_qa.extract(self.dir / "a.txt"), "สวัสดี")
        self.assertEqual(files_qa.extract(self.dir / "b.txt"), "ประชุม")

    def test_unsupported_and_scanned_pdf_say_why(self):
        (self.dir / "x.docx").write_bytes(b"PK")
        with self.assertRaises(files_qa.Unsupported):
            files_qa.extract(self.dir / "x.docx")
        (self.dir / "scan.pdf").write_bytes(b"%PDF-1.4")

        def runner(args, **kw):
            return subprocess.CompletedProcess(args, 0, b"  \n", b"")

        with self.assertRaises(files_qa.Unsupported) as e:
            files_qa.extract(self.dir / "scan.pdf", runner=runner)
        self.assertIn("ภาพสแกน", str(e.exception))

    def test_unreadable_file_is_unsupported_not_a_crash(self):
        # พบ 2026-10-12: ไฟล์ที่เปิดอ่านไม่ได้ทำให้ "ไฟล์ที่ทำสัปดาห์นี้" ล่มทั้งการ์ด (PermissionError)
        from unittest import mock

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ล็อก.txt"
            f.write_text("x", encoding="utf-8")
            with mock.patch.object(
                Path, "read_bytes", side_effect=PermissionError(13, "Permission denied")
            ):
                with self.assertRaises(files_qa.Unsupported) as e:
                    files_qa.extract(f)
            self.assertIn("เปิดไฟล์ไม่ได้", str(e.exception))

    def test_pdf_text_via_pdftotext(self):
        (self.dir / "r.pdf").write_bytes(b"%PDF-1.4")
        seen = []

        def runner(args, **kw):
            seen.append(args)
            return subprocess.CompletedProcess(args, 0, "รายงานประจำเดือน".encode(), b"")

        self.assertEqual(files_qa.extract(self.dir / "r.pdf", runner=runner), "รายงานประจำเดือน")
        self.assertEqual(seen[0][0], "pdftotext")


class ExcerptTest(unittest.TestCase):
    def test_short_file_sent_whole_long_file_relevant_parts(self):
        self.assertEqual(files_qa.excerpt("สั้น", "อะไร"), ("สั้น", False))
        filler = "\n\n".join(
            f"ย่อหน้าที่ {i} พูดเรื่องทั่วไปของบริษัท การประชุม และการเดินทาง" * 3 for i in range(40)
        )
        text = filler + "\n\nงบประมาณโครงการปีนี้คือ 250,000 บาท อนุมัติโดยคณะกรรมการ\n\n" + filler
        part, cut = files_qa.excerpt(text, "งบประมาณโครงการเท่าไร")
        self.assertTrue(cut)
        self.assertIn("250,000", part)
        self.assertLessEqual(len(part), files_qa.EXCERPT_CHARS + 50)

    def test_message_tells_ai_to_answer_from_file_only(self):
        msg = files_qa.build_message("r.txt", "ข้อมูล", "สรุปให้หน่อย")
        self.assertIn("r.txt", msg)
        self.assertIn("ตอบจากเนื้อหาข้างบนเท่านั้น", msg)
        self.assertTrue(msg.endswith("คำถาม: สรุปให้หน่อย"))


try:
    try:
        from test_chat import FakeLlama, ServerCase, pump
    except ImportError:
        from tests.test_chat import FakeLlama, ServerCase, pump
    from PySide6.QtGui import QGuiApplication
except ImportError:  # pragma: no cover
    ServerCase = None


@unittest.skipIf(ServerCase is None, "ไม่มี PySide6")
class ChatFileTest(ServerCase or unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_file_question_has_no_tools_and_never_goes_to_claude(self):
        from aipc.chat import store
        from aipc.cloud.ask import CloudReply
        from aipc.ui.backend import ChatController

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        f = Path(d.name) / "ลับ.txt"
        f.write_text("รหัสตู้เซฟคือ 4821", encoding="utf-8")
        asked = []
        c = ChatController(
            target=self.target,
            store=store.ChatStore(Path(d.name) / "c"),
            poll_ms=100000,
            cloud=lambda q, h: asked.append(q) or CloudReply(True, "x"),
        )
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        self.assertEqual(c.attachFile(str(f)), "")
        self.assertEqual(c.attachedFile, "ลับ.txt")
        FakeLlama.mode = "dunno"  # AI ตอบ "ไม่รู้" ปกติจะส่งต่อ Claude
        done = []
        c.finished.connect(lambda t, n: done.append(t))
        FakeLlama.seen.clear()
        self.assertTrue(c.send("รหัสตู้เซฟคืออะไร", "", False))
        pump(lambda: done)
        body = [b for b in FakeLlama.seen if b.get("stream") is not False][-1]
        self.assertNotIn("tools", body)
        self.assertIn("4821", body["messages"][-1]["content"])
        self.assertEqual(asked, [], "เนื้อหาไฟล์ห้ามออกนอกเครื่อง")
        self.assertEqual(c._conv["messages"][0]["shown"], "รหัสตู้เซฟคืออะไร")
        c.detachFile()
        self.assertEqual(c.attachedFile, "")
        # สำรวจบน Pi 5 2026-10-12: แชทใหม่ยังแนบไฟล์เดิม → คำสั่งในแชทใหม่ถูกถามไฟล์แทน
        c.attachFile(str(f))
        c.newChat(False)
        self.assertEqual(c.attachedFile, "")
        # แนบไฟล์ใหม่ไม่สำเร็จ = ไม่ค้างไฟล์เดิม (พบ 2026-10-12: ถามต่อแล้วได้คำตอบของไฟล์ก่อนหน้า)
        c.attachFile(str(f))
        img = Path(d.name) / "รูป.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        self.assertNotEqual(c.attachFile(str(img)), "")
        self.assertEqual(c.attachedFile, "")


if __name__ == "__main__":
    unittest.main()
