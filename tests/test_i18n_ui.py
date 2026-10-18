"""การ์ด 0039 เกณฑ์ A1: สลับเป็นอังกฤษจากหน้าตั้งค่าแล้วเปิดทุกหน้าในระบบ = ไม่มีข้อความไทยค้าง ·
สลับกลับไทย = ข้อความเหมือนเดิมทุกตัวอักษร · ไม่มี warning ของ QML."""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    from aipc import i18n
    from aipc.ui import app as uiapp
except ImportError:  # pragma: no cover
    uiapp = None

THAI = re.compile(r"[฀-๿]")
PAGES = ("workspace", "calendar", "files", "health", "settings", "skills")
# ตั้งใจเป็นไทยในทุกภาษา: ปุ่มเลือกภาษาเขียนด้วยภาษานั้นเอง (คนอ่านไทยไม่ออกก็หาเจอ)
ALLOWED = {"ภาษา · Language", "ไทย"}


def settle(ms=150):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


# นาฬิกาและอุณหภูมิบนแถบสถานะเปลี่ยนระหว่างเทสต์ได้ (เจอบน Pi) → ไม่เอามาเทียบ
CLOCK = re.compile(r"^\d\d:\d\d · |°C$")


def visible_texts(item, out):
    if item.property("visible") is False:
        return out
    for prop in ("text", "placeholderText", "title", "subtitle"):
        v = item.property(prop)
        if isinstance(v, str) and v and not CLOCK.match(v):
            out.append(v)
    for c in item.childItems():
        visible_texts(c, out)
    return out


@unittest.skipIf(uiapp is None, "ไม่มี PySide6")
class EnglishPagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aipc-i18n-")
        self.old = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME")}
        os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = self.tmp

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        i18n.set_lang("th")
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_page(self, page):
        opts = uiapp.Options(screen="shell", page=page, software=True,
                             settings_path=Path(self.tmp) / "ui.json")  # fmt: skip
        app, engine, warnings = uiapp.build(opts)
        settle(300)
        win = engine.rootObjects()[0]

        def close():
            win.close()
            uiapp.shutdown(engine)
            QCoreApplication.processEvents()

        self.addCleanup(close)
        return engine, win, warnings

    def test_switch_to_english_and_back(self):
        for page in PAGES:
            with self.subTest(page=page):
                engine, win, warnings = self.open_page(page)
                ui = engine._backends["uiSettings"]
                thai_before = visible_texts(win.contentItem(), [])
                ui.setLanguage("en")
                settle(300)
                left = [
                    t
                    for t in visible_texts(win.contentItem(), [])
                    if THAI.search(t) and t not in ALLOWED
                ]
                self.assertEqual(left, [], f"ยังมีข้อความไทยในหน้า {page}")
                ui.setLanguage("th")
                settle(300)
                self.assertEqual(visible_texts(win.contentItem(), []), thai_before, page)
                self.assertEqual(warnings, [])

    def test_answer_cards_follow_language_and_keep_user_data(self):
        """การ์ดคำตอบ (สร้างตอนทำงาน) แปลตอนแสดง · ชื่อนัดของผู้ใช้คงเดิม · สลับกลับไทย = การ์ดเดิมทุกตัวอักษร."""
        engine, win, warnings = self.open_page("workspace")
        page = [o for o in win.findChildren(object) if o.objectName() == "workspace"][0]
        card = {"kind": "reminder", "badge": {}, "title": "ยังจดนัดนี้ไม่ได้", "page": "",
                "confirmToken": "", "lines": ["ทั้งวัน · ประชุมทีม"],
                "chips": [{"text": "ทำแล้ว", "kind": "ok"}]}  # fmt: skip
        page.setProperty("items", [{"user": False, "card": card}])
        settle(200)
        ui = engine._backends["uiSettings"]
        thai = visible_texts(win.contentItem(), [])
        self.assertIn("ยังจดนัดนี้ไม่ได้", thai)
        ui.setLanguage("en")
        settle(300)
        en = visible_texts(win.contentItem(), [])
        for want in ("Couldn't save this reminder", "All day · ประชุมทีม", "Done"):
            self.assertIn(want, en)
        ui.setLanguage("th")
        settle(300)
        self.assertEqual(visible_texts(win.contentItem(), []), thai)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
