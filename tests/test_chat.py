"""แชทกับ LLM ในเครื่อง (การ์ด 0013 ข้อ 8) · llama-server ปลอม (HTTP + SSE) ไม่ต้องมีโมเดลจริง."""

import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aipc.chat import client, store

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# คำตอบจริงของ AI ในเครื่องบน Pi 5 (T6 แบบใหม่ 2026-10-08): ลอกป้ายที่มาของ Claude จากประวัติมาใส่เอง
LABELED = ["[ข้อความนี้ Claude (cloud) ตอบโดยค้นเว็บ ", "ไม่ใช่ความรู้ของ AI ในเครื่อง]\n",
           "ฉันไม่สามารถให้ \"ข่าวเด่นวันนี้\" ที่เป็นข้อมูลสดได้ เนื่องจากฉันไม่มีข้อมูลสด ณ ขณะนี้"]  # fmt: skip


class FakeLlama(BaseHTTPRequestHandler):
    mode = "ok"  # ok | slow | crash | loading | tool (AI เลือกสกิล tool_name)
    tool_name = "machine-status"
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        self.send_response(503 if self.mode == "loading" else 200)
        self.end_headers()

    slots: list = []  # (action, filename) ของ /slots/0?action=save|restore
    slot_ok = False  # False = เหมือน llama-server ที่ไม่ได้เปิด --slot-save-path

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/slots"):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            FakeLlama.slots.append((self.path.split("action=")[-1], body["filename"]))
            self.send_response(200 if self.slot_ok else 501)
            self.end_headers()
            self.wfile.write(json.dumps({} if self.slot_ok else {"error": {"code": 501}}).encode())
            return
        try:
            self._answer()
        except OSError:  # ผู้ทดสอบตัดการเชื่อมต่อเอง (หยุด) · ไม่ต้องพิมพ์ error
            pass

    def _answer(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLlama.seen.append(body)
        if self.mode == "loading":
            self.send_response(503)
            self.end_headers()
            return
        if body.get("stream") is False:  # การอุ่นแคช (client.warm) ขอแบบไม่ stream
            self.send_response(200)
            self.end_headers()
            reply = {"choices": [{"message": {"content": "ส"}}], "timings": {"prompt_n": 10}}
            self.wfile.write(json.dumps(reply, ensure_ascii=False).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if self.mode == "tool":  # รูปแบบ OpenAI ที่ llama-server ส่ง: ชื่อก่อน แล้วอาร์กิวเมนต์ทีละส่วน
            call = {"index": 0, "id": "c1", "type": "function",
                    "function": {"name": self.tool_name, "arguments": ""}}  # fmt: skip
            for delta in (
                {"tool_calls": [call]},
                {"tool_calls": [{"index": 0, "function": {"arguments": '{"x": "ลบไฟล์"}'}}]},
            ):
                chunk = {"choices": [{"delta": delta}]}
                self.wfile.write(
                    b"data: " + json.dumps(chunk, ensure_ascii=False).encode() + b"\n\n"
                )
            self.wfile.write(b"data: [DONE]\n\n")
            return
        tokens = {"slow": ["ช้า"] * 40, "dunno": ["ไม่", "รู้"], "label": LABELED}.get(
            self.mode, ["สวัส", "ดี", "ครับ"]
        )
        for i, tok in enumerate(tokens):
            chunk = {"choices": [{"delta": {"content": tok}}]}
            self.wfile.write(b"data: " + json.dumps(chunk, ensure_ascii=False).encode() + b"\n\n")
            self.wfile.flush()
            if self.mode == "crash" and i == 1:
                self.connection.shutdown(2)  # ตายกลางคำตอบ
                return
            if self.mode == "slow":
                time.sleep(0.1)
        done = {"choices": [], "timings": {"predicted_per_second": 4.2}}
        self.wfile.write(b"data: " + json.dumps(done).encode() + b"\n\ndata: [DONE]\n\n")


class ServerCase(unittest.TestCase):
    def setUp(self):
        FakeLlama.mode, FakeLlama.seen, FakeLlama.slots, FakeLlama.slot_ok = "ok", [], [], False
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLlama)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.target = client.Target(url=f"http://127.0.0.1:{self.srv.server_port}")


class ClientTest(ServerCase):
    def test_warm_restores_saved_cache_else_warms_and_saves(self):
        tools = [
            {"type": "function", "function": {"name": "x", "description": "d", "parameters": {}}}
        ]
        t = client.warm(self.target, "ระบบ", tools)  # ไม่มีไฟล์ (server ไม่รองรับ) → อุ่นเองแล้วลองบันทึก
        self.assertFalse(t["restored"])
        key = client.warm_key("ระบบ", tools)
        self.assertEqual(FakeLlama.slots, [("restore", key), ("save", key)])
        FakeLlama.slots, FakeLlama.slot_ok = [], True
        self.assertTrue(client.warm(self.target, "ระบบ", tools)["restored"])
        self.assertEqual(FakeLlama.slots, [("restore", key)])  # โหลดคืนได้ = ไม่บันทึกซ้ำ
        self.assertNotEqual(client.warm_key("ระบบ วันใหม่", tools), key)  # prompt เปลี่ยน = ไฟล์ใหม่

    def ask(self):
        tokens = []
        s = client.Stream(self.target, [{"role": "user", "content": "สวัสดี"}])
        return s, tokens, s.run(tokens.append)

    def test_tokens_arrive_one_by_one(self):
        _, tokens, r = self.ask()
        self.assertEqual(tokens, ["สวัส", "ดี", "ครับ"])
        self.assertEqual((r.text, r.reason), ("สวัสดีครับ", ""))
        self.assertEqual(r.timings["predicted_per_second"], 4.2)
        self.assertTrue(FakeLlama.seen[0]["stream"])
        self.assertTrue(FakeLlama.seen[0]["cache_prompt"], "ใช้ prompt cache ของ llama-server")

    def test_crash_mid_answer_keeps_partial_text(self):
        FakeLlama.mode = "crash"
        _, _, r = self.ask()
        self.assertEqual(r.reason, "crashed")
        self.assertEqual(r.text, "สวัสดี")

    def test_stop_closes_the_connection(self):
        FakeLlama.mode = "slow"
        tokens = []
        s = client.Stream(self.target, [{"role": "user", "content": "x"}])
        threading.Timer(0.35, s.abort).start()
        t0 = time.monotonic()
        r = s.run(tokens.append)
        self.assertEqual(r.reason, "stopped")
        self.assertLess(time.monotonic() - t0, 2, "หยุดทันที ไม่รอจนตอบจบ")
        self.assertLess(len(tokens), 40)

    def test_loading_and_down(self):
        FakeLlama.mode = "loading"
        self.assertEqual(client.health(self.target), "loading")
        self.assertEqual(self.ask()[2].reason, "error")
        FakeLlama.mode = "ok"
        self.assertEqual(client.health(self.target), "ready")
        self.assertEqual(client.health(client.Target(url="http://127.0.0.1:9")), "down")
        self.assertEqual(client.health(client.Target()), "down")  # ไม่มีที่อยู่เลย

    def test_fit_context_drops_oldest_first(self):
        history = [{"role": "user", "content": "ก" * 2000} for _ in range(10)]
        history.append({"role": "user", "content": "ล่าสุด"})
        msgs, trimmed = client.fit_context("ระบบ", history, budget_tokens=3000)
        self.assertTrue(trimmed)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[-1]["content"], "ล่าสุด")
        self.assertLessEqual(sum(len(m["content"]) for m in msgs[1:]) // 2, 3000 + 100)
        self.assertFalse(client.fit_context("ระบบ", history[-2:])[1])


class StoreTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.s = store.ChatStore(Path(d.name) / "chats")

    def test_save_list_load_delete(self):
        c = store.new_conversation()
        c["messages"] = [{"role": "user", "content": "ช่วยเขียนอีเมล\nถึงอาจารย์"}]
        self.s.save(c)
        self.assertEqual(self.s.list()[0]["title"], "ช่วยเขียนอีเมล ถึงอาจารย์")
        self.assertEqual(self.s.load(c["id"])["messages"], c["messages"])
        self.assertFalse(list(self.s.folder.glob("*.tmp")))
        self.assertEqual(self.s.delete_all(), 1)
        self.assertEqual(self.s.list(), [])

    def test_ids_cannot_escape_the_folder(self):
        self.assertIsNone(self.s.load("../../etc/passwd"))
        with self.assertRaises(ValueError):
            self.s.delete("../x")

    def test_broken_file_is_skipped(self):
        self.s.folder.mkdir(parents=True)
        (self.s.folder / "abc.json").write_text("[]", encoding="utf-8")
        self.assertEqual(self.s.list(), [])


try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from aipc.ui.backend import ChatController
except ImportError:  # pragma: no cover
    ChatController = None


def pump(until, timeout=5.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


@unittest.skipIf(ChatController is None, "ไม่มี PySide6")
class ControllerTest(ServerCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make(self, folder=None, tools=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        folder = folder or Path(d.name) / "chats"
        c = ChatController(target=self.target, store=store.ChatStore(folder), poll_ms=100000,
                           tools=tools)  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append((text, note)))
        return c, done, folder

    def test_answer_streams_then_is_saved(self):
        c, done, folder = self.make()
        streamed = []
        c.streamChanged.connect(lambda: streamed.append(c.streamText))
        self.assertTrue(c.send("สวัสดี", ""))
        self.assertTrue(c.busy)
        pump(lambda: done)
        self.assertEqual(done[0], ("สวัสดีครับ", ""))
        self.assertIn("สวัสดี", streamed)  # เห็นทีละส่วนก่อนจบ
        self.assertEqual(len(c.history), 1)
        self.assertEqual(FakeLlama.seen[0]["messages"][0]["role"], "system")

    def test_crash_after_ready_says_restarting_then_down_after_grace(self):
        c, _, _ = self.make()
        c._on_health("down")  # T7: kill -9 llama-server หลังพร้อมแล้ว
        self.assertEqual((c.status, c.statusText), ("restarting", "AI กำลังเริ่มใหม่…"))
        c._on_health("loading")  # systemd เปิดใหม่ กำลังโหลดโมเดล
        self.assertEqual(c.status, "restarting")
        c._on_health("ready")
        self.assertTrue(c.ready)
        c._on_health("down")
        c._lost_at -= c.RESTART_GRACE_S  # เกินเวลาที่ควรกลับมาแล้ว → บอกตามจริง
        c._on_health("down")
        self.assertEqual(c.status, "down")

    def test_warm_up_runs_after_ready_so_ai_skills_are_listed(self):
        c = ChatController(target=self.target, store=store.ChatStore(Path(tempfile.mkdtemp())),
                           poll_ms=100000)  # fmt: skip
        self.addCleanup(c.shutdown)
        seen = []
        c._warm_up = lambda: seen.append(c.ready)  # สกิลที่ใช้ AI ดู chat.ready ตอนสร้างรายการ
        c._on_health("ready")
        self.assertEqual(seen, [True])

    def test_first_load_is_not_called_restart(self):
        c = ChatController(target=self.target, store=store.ChatStore(Path(tempfile.mkdtemp())),
                           poll_ms=100000)  # fmt: skip
        self.addCleanup(c.shutdown)
        c._on_health("loading")
        self.assertEqual(c.status, "loading")

    def test_temporary_chat_writes_nothing(self):
        c, done, folder = self.make()
        c.newChat(True)
        c.send("ลับ", "")
        pump(lambda: done)
        self.assertFalse(folder.exists() and any(folder.iterdir()))
        self.assertIn("ชั่วคราว", c.notice)

    def test_skill_prompt_is_single_turn(self):
        c, done, _ = self.make()
        c.send("ข้อความแรก", "")
        pump(lambda: done)
        c.send("แปล: สวัสดี", "แปลข้อความ")
        pump(lambda: len(done) == 2)
        msgs = FakeLlama.seen[-1]["messages"]
        self.assertEqual([m["role"] for m in msgs], ["system", "user"])
        self.assertEqual(msgs[0]["content"], "แปลข้อความ")

    def test_crash_is_told_not_hidden(self):
        c, done, _ = self.make()
        FakeLlama.mode = "crash"
        c.send("x", "")
        pump(lambda: done)
        self.assertIn("ตอบไม่จบ", done[0][1])
        self.assertEqual(done[0][0], "สวัสดี")

    def test_copy_answer_to_clipboard(self):
        # ปุ่ม "คัดลอก" ใต้คำตอบ AI (ข้อเสนอ 2026-09-29 ข้อ ⑤) · เอาจดหมายที่ร่างไปใช้ต่อได้
        c = ChatController(active=False)
        c.copyText("เรียน อาจารย์ ...")
        self.assertEqual(QGuiApplication.clipboard().text(), "เรียน อาจารย์ ...")

    def test_ai_picks_a_skill(self):
        # อาจารย์ขอ (งานข้อ ④): คุยทั่วไปส่งรายการสกิลไปด้วย · AI เลือกสกิล = ส่งสัญญาณให้หน้าจอ ไม่ใช่คำตอบ
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "machine-status",
                    "description": "ถามเครื่อง",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        c, done, folder = self.make(tools=lambda: tools)
        picked = []
        c.skillRequested.connect(lambda sid, text: picked.append((sid, text)))
        FakeLlama.mode = "tool"
        self.assertTrue(c.send("คอมหน่วงมาก เป็นอะไร", ""))
        pump(
            lambda: picked, timeout=20
        )  # ชุดเทสต์เต็มบนเครื่องที่ยุ่ง 5 วิเคยไม่พอ (พลาด 1 ใน ~8 รอบ 2026-10-01)
        self.assertEqual(picked, [("machine-status", "คอมหน่วงมาก เป็นอะไร")])
        # คำขออุ่นแคช (เธรดแยก · stream False) อาจมาถึงหลังคำขอแชท → เลือกคำขอแชทตัวจริง ไม่ใช่ตัวสุดท้าย
        body = [b for b in FakeLlama.seen if b.get("stream") is not False][-1]
        self.assertEqual(body["tools"], tools)
        self.assertEqual(body["tool_choice"], "auto")
        self.assertIn("เครื่องมือ", body["messages"][0]["content"])
        self.assertEqual(done, [], "ไม่ใช่คำตอบ · ไม่มีฟองคำตอบค้าง")
        self.assertEqual(c._conv["messages"], [], "ข้อความของผู้ใช้ไปทางสกิล ไม่ค้างในบทสนทนา")
        self.assertFalse(c.busy)
        # สกิลที่ถูกเลือกแล้ว (มี prompt) ไม่ส่งเครื่องมือ = ไม่วนเลือกซ้ำ
        FakeLlama.mode = "ok"
        c.send("คอมหน่วงมาก เป็นอะไร", "อธิบายสถานะเครื่อง")
        pump(lambda: done)
        self.assertNotIn("tools", FakeLlama.seen[-1])

    def test_warms_the_prompt_cache_when_ai_becomes_ready(self):
        """ข้อความแรกหลัง login ไม่ต้องรออ่านรายการสกิล ~1 นาที (Pi 5 2026-09-30: 68 วิ → 2.4 วิ)."""
        params = {"type": "object", "properties": {}}
        fn = {"name": "machine-status", "description": "x", "parameters": params}
        tools = [{"type": "function", "function": fn}]
        FakeLlama.seen.clear()
        c, done, _ = self.make(tools=lambda: tools)
        pump(lambda: any(b.get("max_tokens") == 1 for b in FakeLlama.seen))
        warm = next(b for b in FakeLlama.seen if b.get("max_tokens") == 1)
        self.assertTrue(warm["cache_prompt"])
        self.assertEqual(warm["tools"], tools)
        c.send("ทำไมเครื่องช้า", "")
        pump(lambda: done)
        real = FakeLlama.seen[-1]
        self.assertEqual(real["messages"][0], warm["messages"][0], "ส่วนต้นตรงกันทุกตัวอักษร แคชจึงใช้ได้")

    def test_hybrid_hands_hard_questions_to_claude(self):
        """การ์ด 0016: AI ในเครื่องเลือก ask-cloud → Claude ตอบ · ป้ายบอกว่าออกนอกเครื่อง · บันทึกเป็นคำตอบ."""
        from aipc.cloud.ask import CloudReply
        from aipc.skills import catalog

        asked = []

        def cloud(question, history):
            asked.append((question, list(history)))
            return CloudReply(True, "กรุงเทพวันนี้ 25–35 องศา")

        FakeLlama.mode, FakeLlama.tool_name = "tool", catalog.ASK_CLOUD
        self.addCleanup(setattr, FakeLlama, "tool_name", "machine-status")
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=cloud)  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done, picked = [], []
        c.finished.connect(lambda text, note: done.append((text, note)))
        c.skillRequested.connect(lambda sid, text: picked.append(sid))
        FakeLlama.seen.clear()
        self.assertTrue(c.send("วันนี้อากาศเป็นไง", ""))
        pump(lambda: done)
        self.assertEqual(done[0], ("กรุงเทพวันนี้ 25–35 องศา", c.CLOUD_NOTE))
        self.assertEqual(picked, [], "ask-cloud ไม่ใช่สกิล")
        self.assertEqual(asked[0][0], "วันนี้อากาศเป็นไง")
        real = [b for b in FakeLlama.seen if b.get("max_tokens") != 1][-1]
        self.assertEqual(real["tools"][0]["function"]["name"], catalog.ASK_CLOUD)
        self.assertIn("ask-cloud", real["messages"][0]["content"])

    def test_local_dont_know_goes_to_claude(self):
        from aipc.cloud.ask import CloudReply

        FakeLlama.mode = "dunno"
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=lambda q, h: CloudReply(True, "ข่าวเด่นวันนี้ …"))  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append((text, note)))
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: done)
        self.assertEqual(done[0], ("ข่าวเด่นวันนี้ …", c.CLOUD_NOTE))

    def test_why_local_answer(self):
        """ทำไมได้คำตอบนี้ (ข้อเสนอ 2026-10-03): สร้างจากสิ่งที่เกิดจริง พร้อมก่อน finished."""
        c, done, _ = self.make()
        seen = []
        c.finished.connect(lambda text, note: seen.append({r["k"]: r["v"] for r in c.lastTrace}))
        c.send("สวัสดี", "")
        pump(lambda: seen)
        r = seen[0]
        self.assertTrue(r["ใครตอบ"].startswith("AI ในเครื่อง"))
        self.assertIn("ไม่ตรงสกิลไหน", r["ทำไมทางนี้"])
        self.assertEqual(r["ข้อมูลออกนอกเครื่อง"], "ไม่มี · ตอบในเครื่องทั้งหมด")
        self.assertIn("วินาที", r["ใช้เวลา"])

    def test_why_claude_answer_counts_what_was_sent(self):
        from aipc.cloud.ask import CloudReply, build_input

        FakeLlama.mode = "dunno"
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=lambda q, h: CloudReply(True, "ข่าวเด่นวันนี้ …"))  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append(text))
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: done)
        r = {x["k"]: x["v"] for x in c.lastTrace}
        self.assertEqual(r["ใครตอบ"], "Claude (cloud)")
        self.assertIn("ตอบว่าไม่รู้", r["ทำไมทางนี้"])
        n = len(build_input("ข่าวเด่นวันนี้มีอะไร", []))
        self.assertIn(f"({n} ตัวอักษร) ไป Claude", r["ข้อมูลออกนอกเครื่อง"])  # ตรงกับที่ ledger บันทึก

    def test_local_dont_know_stays_without_cloud(self):
        FakeLlama.mode = "dunno"
        c, done, _ = self.make()
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: done)
        self.assertEqual(done[0][0], "ไม่รู้")

    def test_claude_switch_off_keeps_everything_local(self):
        """สวิตช์ Claude ในหน้าตั้งค่า (2026-10-05): ปิด = ไม่ส่งคำถามออก ·
        ไม่มี ask-cloud ในเครื่องมือ · ไม่มีใน prompt."""
        from aipc.cloud.ask import CloudReply

        asked = []
        FakeLlama.mode = "dunno"
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        on = [False]
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=lambda q, h: asked.append(q) or CloudReply(True, "จาก Claude"),
                           claude_on=lambda: on[0])  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append(text))
        FakeLlama.seen.clear()
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: done)
        self.assertEqual((done[0], asked), ("ไม่รู้", []))
        real = [b for b in FakeLlama.seen if b.get("max_tokens") != 1][-1]
        names = [t["function"]["name"] for t in real.get("tools", [])]
        self.assertNotIn("ask-cloud", names)
        self.assertNotIn("ask-cloud", real["messages"][0]["content"])
        self.assertFalse(c.askCloudFor("ข่าววันนี้"))
        on[0] = True  # เปิดกลับ = ส่งต่อได้ตามเดิม
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: len(done) > 1)
        self.assertEqual((done[1], asked), ("จาก Claude", ["ข่าวเด่นวันนี้มีอะไร"]))
        # ปิดอีกครั้งแล้วถามต่อ: คำตอบของ Claude ในประวัติต้องมีป้ายที่มาเมื่อส่งให้ AI ในเครื่อง (พบ 2026-10-05)
        on[0] = False
        FakeLlama.seen.clear()
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: len(done) > 2)
        real = [b for b in FakeLlama.seen if b.get("max_tokens") != 1][-1]
        sent = [m["content"] for m in real["messages"] if m["role"] == "assistant"]
        self.assertIn(c.CLAUDE_LABEL + "จาก Claude", sent)
        self.assertIn("ไม่รู้", sent)  # คำตอบของ AI ในเครื่องเองไม่มีป้าย
        self.assertEqual(c._conv["messages"][-3]["content"], "จาก Claude")  # ไฟล์แชทเก็บข้อความเดิม

    def test_local_answer_never_carries_claude_label(self):
        """T6 แบบใหม่ 2026-10-08: AI ในเครื่องลอกป้าย "Claude ตอบ" มาใส่คำตอบตัวเอง.

        ตัดออกก่อนแสดงและบันทึก
        """
        FakeLlama.mode = "label"
        c, done, _ = self.make()
        c.send("ข่าวเด่นวันนี้มีอะไร", "")
        pump(lambda: done)
        self.assertNotIn("ข้อความนี้ Claude", done[0][0])
        self.assertTrue(done[0][0].startswith("ฉันไม่สามารถให้"))
        last = c._conv["messages"][-1]
        self.assertNotIn("ข้อความนี้ Claude", last["content"])
        self.assertNotIn("by", last)  # ไม่ได้มาจาก Claude

    def test_hybrid_offline_is_told(self):
        from aipc.cloud.ask import CloudReply
        from aipc.skills import catalog

        FakeLlama.mode, FakeLlama.tool_name = "tool", catalog.ASK_CLOUD
        self.addCleanup(setattr, FakeLlama, "tool_name", "machine-status")
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        offline = CloudReply(False, error="ติดต่อ Claude ไม่ได้ (ไม่มีอินเทอร์เน็ต?)")
        c = ChatController(target=self.target, store=store.ChatStore(Path(d.name)), poll_ms=100000,
                           cloud=lambda q, h: offline)  # fmt: skip
        self.addCleanup(c.shutdown)
        pump(lambda: c.ready)
        done = []
        c.finished.connect(lambda text, note: done.append((text, note)))
        c.send("ข่าววันนี้มีอะไร", "")
        pump(lambda: done)
        self.assertEqual(done[0][0], "")
        self.assertIn("ไม่มีอินเทอร์เน็ต", done[0][1])

    def test_not_ready_refuses(self):
        c = ChatController(target=client.Target(), poll_ms=100000)
        self.addCleanup(c.shutdown)
        self.assertFalse(c.send("x", ""))
        self.assertEqual(ChatController(active=False).status, "off")


if __name__ == "__main__":
    unittest.main()
