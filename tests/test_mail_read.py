"""การ์ด 0071: อ่านกล่องจดหมาย Gmail ด้วยเสียง · เกณฑ์ R1 (หน้า Gmail จำลอง · ไม่มีเบราว์เซอร์จริง)."""

import time
import unittest

from aipc.browser import control
from aipc.browser.control import BrowserControl, Result
from aipc.skills import mailread
from aipc.skills.browse import BrowseCommand

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.handsfree import BrowserController
except ImportError:  # pragma: no cover
    BrowserController = None

INBOX = "https://mail.google.com/mail/u/0/#inbox"
ROWS = [
    {"unread": True, "sender": "อ.กิตติกร", "email": "kittikorn@example.ac.th",
     "subject": "นัดสอบ 50%", "time": "10:15"},
    {"unread": False, "sender": "Google", "email": "no-reply@accounts.google.com",
     "subject": "การแจ้งเตือนความปลอดภัย", "time": "09:02"},
    {"unread": True, "sender": "ธนาคาร", "email": "info@bank.example", "subject": "",
     "time": "27 ต.ค."},
]  # fmt: skip


class ParseTest(unittest.TestCase):
    def test_reading_sentences(self):
        cases = {
            "อ่านเมลล่าสุด": ("latest", ""), "อ่านอีเมลล่าสุดให้ฟังหน่อย": ("latest", ""),
            "เมลล่าสุดมีอะไรบ้าง": ("latest", ""), "ช่วยอ่านเมลหน่อย": ("latest", ""),
            "มีเมลใหม่ไหม": ("unread", ""), "มีอีเมลใหม่หรือเปล่าครับ": ("unread", ""),
            "เมลที่ยังไม่ได้อ่าน": ("unread", ""), "เช็คเมลใหม่": ("unread", ""),
            "มีเมลจากอาจารย์ไหม": ("from", "อาจารย์"), "อ่านอีเมลจากธนาคาร": ("from", "ธนาคาร"),
        }  # fmt: skip
        for text, want in cases.items():
            self.assertEqual(mailread.parse(text), want, text)

    def test_other_mail_commands_are_not_reading(self):
        """ทางเดิมต้องไม่ถูกแย่ง: เปิด Gmail · ค้นใน Gmail · ร่างจดหมาย (AI ในเครื่อง) · ส่งเมล (ไม่มีคำสั่ง)."""
        for text in ("เช็คเมล", "เปิดจีเมล", "เปิดอีเมล", "ค้นในจีเมลว่าอาจารย์", "ร่างอีเมลลาป่วยถึงอาจารย์",
                     "ส่งอีเมลหาอาจารย์", "อ่านเมลนี้แล้วสรุป", "เขียนอีเมลขอบคุณ", "เมล"):  # fmt: skip
            self.assertIsNone(mailread.parse(text), text)


class AnswerTest(unittest.TestCase):
    def test_unread_latest_and_from(self):
        say = mailread.answer("unread", "", ROWS)
        self.assertTrue(say.startswith("เมลยังไม่อ่าน 2 ฉบับ (ในหน้าแรกของกล่องจดหมาย)"), say)
        self.assertIn("1. จาก อ.กิตติกร เรื่อง นัดสอบ 50% (10:15)", say)
        self.assertIn("2. จาก ธนาคาร เรื่อง (ไม่มีหัวเรื่อง)", say)
        self.assertNotIn("Google", say)
        latest = mailread.answer("latest", "", ROWS)
        self.assertIn("1. จาก อ.กิตติกร เรื่อง นัดสอบ 50% (10:15) · ยังไม่อ่าน", latest)
        self.assertIn("2. จาก Google", latest)
        self.assertIn("เมลจาก ธนาคาร 1 ฉบับ", mailread.answer("from", "ธนาคาร", ROWS))
        by_mail = mailread.answer("from", "kittikorn", ROWS)  # ตรงอีเมลก็ได้
        self.assertIn("เมลจาก kittikorn 1 ฉบับ", by_mail)
        self.assertIn("ไม่เห็นเมลจาก “สมชาย”", mailread.answer("from", "สมชาย", ROWS))

    def test_says_only_what_is_on_the_page(self):
        """H5: ไม่มีแถว = บอกว่าไม่เห็น ไม่แต่ง · อ่านแล้วทั้งหมด = บอกตรง ๆ · เกิน 3 ฉบับ = บอกว่ามีอีก."""
        self.assertIn("ไม่เห็นรายการเมล", mailread.answer("latest", "", []))
        read = [dict(r, unread=False) for r in ROWS]
        self.assertIn("อ่านแล้วทั้งหมด", mailread.answer("unread", "", read))
        many = [dict(ROWS[0], subject=f"เรื่อง {i}") for i in range(5)]
        self.assertIn("และอีก 2 ฉบับ", mailread.answer("latest", "", many))


class FakeProc:
    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class FakeCdp:
    """หน้า Gmail จำลอง · rows = แถวที่ INBOX_JS จะเห็น (None = ไม่ใช่หน้า Gmail)."""

    def __init__(self, url, rows):
        self.url, self.rows, self.hash_set, self.closed = url, rows, [], False

    def call(self, method, params=None, session="", timeout=15.0):
        if method == "Target.getTargets":
            return {"targetInfos": [{"type": "page", "targetId": "T1"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Browser.getWindowForTarget":
            return {"windowId": 1}
        if method == "Runtime.evaluate":
            return {"result": {"value": self.evaluate(params["expression"])}}
        return {}

    def evaluate(self, js):
        if js == "location.href":
            return self.url
        if js == control.INBOX_JS:
            return self.rows if "mail.google.com" in self.url else None
        if js.startswith("location.hash"):
            self.hash_set.append(js)
            self.url = INBOX
            return "#inbox"
        if js.startswith("window.__aipcOld"):
            return self.url
        return None

    def close(self):
        pass


def browser(url, rows):
    cdp = FakeCdp(url, rows)
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    bc._mail_wait = 0.2
    bc._start("about:blank")
    return bc, cdp


class ControlTest(unittest.TestCase):
    def test_reads_the_inbox_on_gmail(self):
        bc, _ = browser(INBOX, ROWS)
        r = bc.run(BrowseCommand("mail_read", query="unread"))
        self.assertTrue(r.ok, r.say)
        self.assertIn("เมลยังไม่อ่าน 2 ฉบับ", r.say)

    def test_not_gmail_reads_nothing(self):
        bc, _ = browser("https://www.youtube.com/", ROWS)
        r = bc.run(BrowseCommand("mail_read", query="latest"))
        self.assertFalse(r.ok)
        self.assertIn("ไม่ได้เปิด Gmail", r.say)
        bc, _ = browser("https://accounts.google.com/v3/signin/identifier", ROWS)
        self.assertIn("เข้าสู่ระบบจีเมล", bc.run(BrowseCommand("mail_read", query="latest")).say)

    def test_open_mail_goes_back_to_the_inbox_first(self):
        bc, cdp = browser("https://mail.google.com/mail/u/0/#inbox/FMfcgzQ", ROWS)
        r = bc.run(BrowseCommand("mail_read", query="latest"))
        self.assertEqual(cdp.hash_set, ["location.hash = '#inbox'"])
        self.assertTrue(r.ok, r.say)

    def test_no_rows_waits_then_says_so(self):
        bc, _ = browser(INBOX, [])
        t0 = time.monotonic()
        r = bc.run(BrowseCommand("mail_read", query="latest"))
        self.assertGreaterEqual(time.monotonic() - t0, 0.2)
        self.assertFalse(r.ok)
        self.assertIn("ไม่เห็นรายการเมล", r.say)


class FakeControl:
    running = True

    def __init__(self, url):
        self.url, self.ran = url, []

    def current(self):
        return {"url": self.url}

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        return Result(True, "อ่านแล้ว")

    def close(self):
        self.running = False


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class VoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def run_voice(self, url, text):
        ctl = FakeControl(url)
        b = BrowserController(control=ctl)
        done = []
        b.finished.connect(lambda say, ok: done.append(ok))
        started = b.mailRead(text)
        if started:
            pump(lambda: done)
        return started, ctl.ran

    def test_opens_gmail_first_when_needed(self):
        started, ran = self.run_voice("https://www.youtube.com/", "มีเมลใหม่ไหม")
        self.assertTrue(started)
        opened = [{"kind": "site", "site": "gmail"}, {"kind": "mail_read", "query": "unread"}]
        self.assertEqual(ran, opened)
        _, ran = self.run_voice(INBOX, "มีเมลจากอาจารย์ไหม")
        self.assertEqual(ran, [{"kind": "mail_read", "query": "from", "direction": "อาจารย์"}])

    def test_other_sentences_are_left_alone(self):
        self.assertEqual(self.run_voice(INBOX, "ร่างอีเมลลาป่วย"), (False, []))
        self.assertEqual(self.run_voice(INBOX, "เปิดยูทูบ"), (False, []))
