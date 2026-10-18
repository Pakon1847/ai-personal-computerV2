"""ค้นในบริการด้วยเสียง (การ์ด 0036 เกณฑ์ข้อ 1) · เบราว์เซอร์จำลอง (ไม่เปิด Chromium จริง · ไม่ออกเน็ต).

ตรวจ: ทุกบริการ × ทุกรูปประโยค → ลิงก์ถูก · คำค้นเข้ารหัส URL · บันทึกสิ่งที่ส่งออกครบ ·
ประโยคชนกับหาไฟล์ในเครื่องไม่เปลี่ยนทาง
"""

import os
import unittest
from urllib.parse import parse_qs, quote_plus, urlsplit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aipc.browser import control
from aipc.browser.control import BrowserControl, Result
from aipc.skills import browse
from aipc.skills.browse import BrowseCommand
from tests.test_browser_control import FakeCdp, FakeProc

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.handsfree import BROWSER, BrowserController, route
except ImportError:  # pragma: no cover
    BrowserController = None

# ชื่อบริการที่พูด (รวมสะกดที่พบบ่อย) · ไดรฟ์ต้องมีคำว่ากูเกิล
NAMES = {
    "youtube": ["ยูทูบ", "ยูทูป", "youtube"],
    "maps": ["แผนที่", "กูเกิลแมพ", "แผนที่กูเกิล", "google maps"],
    "wikipedia": ["วิกิพีเดีย", "วิกิ", "wikipedia"],
    "facebook": ["เฟซบุ๊ก", "เฟสบุ๊ค", "facebook"],
    "drive": ["กูเกิลไดรฟ์", "กูเกิ้ลไดร์ฟ", "google drive"],
    "gmail": ["จีเมล", "จีเมล์", "อีเมล", "gmail"],
}
SHAPES = [
    "ค้นใน{s}ว่า{q}",
    "ช่วยหาใน{s} {q} หน่อย",
    "ค้นหาคำว่า{q}ใน{s}",
    "เปิด{s}หา{q}",
    "เปิด{s}แล้วค้นหา{q}ครับ",
]


class SiteSearchParseTest(unittest.TestCase):
    def test_every_service_and_shape(self):
        for site, names in NAMES.items():
            for name in names:
                for shape in SHAPES:
                    t = shape.format(s=name, q="ร้านกาแฟ")
                    want = BrowseCommand("site_search", query="ร้านกาแฟ", site=site)
                    with self.subTest(t=t):
                        self.assertEqual(browse.parse(t), [want])

    def test_query_keeps_english_words_and_is_capped(self):
        self.assertEqual(browse.parse("ค้นในยูทูบว่า lofi hip hop")[0].query, "lofi hip hop")
        long = browse.parse("ค้นในยูทูบว่า" + "ก" * 300)[0]
        self.assertEqual(len(long.query), browse.MAX_QUERY)

    def test_no_query_opens_the_service(self):
        self.assertEqual(browse.parse("ค้นในยูทูบ"), [BrowseCommand("site", site="youtube")])

    def test_old_paths_do_not_change(self):
        # ไม่มีชื่อบริการ / Google เอง = ค้นเว็บเดิม
        gold = BrowseCommand("search", query="ราคาทอง")
        self.assertEqual(browse.parse("ค้นหาราคาทอง"), [gold])
        self.assertEqual(browse.parse("ค้นในกูเกิลว่าราคาทอง"), [gold])
        # ไดรฟ์ USB / หาไฟล์ในเครื่อง = สกิลค้นไฟล์ (ไม่ใช่งานเบราว์เซอร์)
        for t in ("หาไฟล์ในไดรฟ์", "หาไฟล์รายงานในไดรฟ์ USB", "หาไฟล์ในแฟลชไดรฟ์", "หาไฟล์รายงานในเครื่อง"):
            with self.subTest(t=t):
                self.assertEqual(browse.parse(t), [])
        # พูดชื่อบริการแต่ไม่ได้สั่งค้น
        for t in ("ยูทูบเปิดไม่ขึ้น", "แผนที่ประเทศไทยมีกี่ภาค", "หายในยูทูบ"):
            with self.subTest(t=t):
                self.assertFalse(any(c.kind == "site_search" for c in browse.parse(t)))

    def test_round1_fixes_are_general_rules(self):
        # เล่าว่าหาไม่เจอ/ไม่พบ = ไม่ใช่สั่งค้น (ประโยคต่างจากชุดวัด)
        for t in ("เปิดยูทูบแล้วหาคลิปที่เคยดูไม่เจอ", "หาโพสต์ของแม่ในเฟซบุ๊กไม่พบ"):
            with self.subTest(t=t):
                self.assertFalse(any(c.kind == "site_search" for c in browse.parse(t)))
        # "อยู่ไหน" ยังเป็นคำค้นแผนที่ได้
        where = BrowseCommand("site_search", query="โรงพยาบาลอยู่ไหน", site="maps")
        self.assertEqual(browse.parse("ค้นในแผนที่ว่าโรงพยาบาลอยู่ไหน"), [where])
        # "หารูป…" กับบริการที่พูดชื่อ = ค้นในบริการ · ไม่มีชื่อบริการ = ทางเดิม (ไม่ใช่ค้นเว็บ)
        trip = BrowseCommand("site_search", query="รูปทริปเชียงใหม่", site="drive")
        self.assertEqual(browse.parse("เปิดกูเกิลไดรฟ์แล้วหารูปทริปเชียงใหม่"), [trip])
        self.assertEqual(browse.parse("หารูปแมวในเฟซบุ๊ก")[0].query, "รูปแมว")
        self.assertEqual(browse.parse("หารูปแมว"), [])

    def test_round2_fix_story_after_service_is_not_a_query(self):
        # ไม่มี "ว่า" + ขึ้นต้นด้วย แล้ว/แต่/ทีไร = เล่าเรื่อง (ประโยคต่างจากชุดวัด)
        for t in ("ค้นในยูทูบแล้วเสียงไม่ออก", "หาในจีเมลแต่โหลดช้ามาก", "ค้นในแผนที่ทีไรก็หลงทุกที"):
            with self.subTest(t=t):
                self.assertFalse(any(c.kind == "site_search" for c in browse.parse(t)))
        # มี "ว่า" = ตั้งใจค้น แม้คำค้นขึ้นต้นด้วยคำเชื่อม
        then = BrowseCommand("site_search", query="แล้วไงต่อ", site="youtube")
        self.assertEqual(browse.parse("ค้นในยูทูบว่าแล้วไงต่อ"), [then])
        # คำค้นที่แค่มีคำเชื่อมอยู่กลางคำยังค้นได้
        self.assertEqual(browse.parse("ค้นในยูทูบเพลงแล้วแต่ใจ")[0].query, "เพลงแล้วแต่ใจ")

    def test_then_open_first_link(self):
        self.assertEqual(browse.parse("ค้นในยูทูบว่าเพลงลูกทุ่งแล้วเข้าลิงก์แรก"),
                         [BrowseCommand("site_search", query="เพลงลูกทุ่ง", site="youtube"),
                          BrowseCommand("open", n=1)])  # fmt: skip


def opened_at(url):
    cdp = FakeCdp({}, "about:blank")
    bc = BrowserControl(launcher=lambda argv: (FakeProc(), cdp), load_timeout=3)
    if url:
        assert bc.run(BrowseCommand("url", query=url)).ok
    return bc, cdp


class SiteSearchControlTest(unittest.TestCase):
    def test_links_are_fixed_and_query_is_encoded(self):
        q = "ส้มตำ & ไก่ย่าง"
        for site, base in control.SITE_SEARCH.items():
            with self.subTest(site=site):
                bc, cdp = opened_at("")
                r = bc.run(BrowseCommand("site_search", query=q, site=site))
                self.assertTrue(r.ok)
                self.assertEqual(cdp.cur.url, base + quote_plus(q))
                self.assertIn(f"ค้นหา {q} ใน ", r.say)
        url = urlsplit(control.SITE_SEARCH["youtube"] + quote_plus(q))
        self.assertEqual(parse_qs(url.query)["search_query"], [q])  # "&" ไม่ตัดคำค้นเป็นสองพารามิเตอร์

    def test_gmail_search_inside_open_gmail(self):
        # จีเมลเปิดอยู่แล้ว = เปลี่ยนแค่หลัง # (ไม่มีเอกสารใหม่ให้รอ) · ต้องไม่รอจนหมดเวลา
        bc, cdp = opened_at("https://mail.google.com/mail/u/0/#inbox")
        r = bc.run(BrowseCommand("site_search", query="ใบแจ้งหนี้", site="gmail"))
        self.assertEqual(r.url, "https://mail.google.com/mail/u/0/#search/" + quote_plus("ใบแจ้งหนี้"))


class FakeControl:
    def __init__(self):
        self.running, self.ran, self.available = False, [], True

    def run(self, cmd):
        self.ran.append(cmd.as_dict())
        self.running = True
        return Result(True, "ค้นแล้ว")

    def close(self):
        self.running = False


class FakeLedger:
    def __init__(self):
        self.rows = []

    def record(self, kind, sent, cost_usd=0.0, ok=True, note=""):
        self.rows.append((kind, sent, ok))


@unittest.skipIf(BrowserController is None, "ไม่มี PySide6")
class SiteSearchLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_query_leaving_the_machine_is_recorded(self):
        ledger, done = FakeLedger(), []
        b = BrowserController(control=FakeControl(), ledger=ledger)
        b.finished.connect(lambda say, ok: done.append(ok))
        self.assertEqual(route("ค้นในยูทูบว่าเพลงลูกทุ่ง", False), BROWSER)  # เปิดเบราว์เซอร์ให้เอง
        self.assertTrue(b.handle("ค้นในยูทูบว่าเพลงลูกทุ่ง"))
        loop, waited = QEventLoop(), 0
        while not done and waited < 3000:
            QTimer.singleShot(20, loop.quit)
            loop.exec()
            waited += 20
        self.assertEqual(ledger.rows, [("web", "ค้นใน YouTube: เพลงลูกทุ่ง", True)])


if __name__ == "__main__":
    unittest.main()
