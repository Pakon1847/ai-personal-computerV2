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


class FakeLlama(BaseHTTPRequestHandler):
    mode = "ok"  # ok | slow | crash | loading | tool (AI เลือกสกิล machine-status)
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        self.send_response(503 if self.mode == "loading" else 200)
        self.end_headers()

    def do_POST(self):  # noqa: N802
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
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if self.mode == "tool":  # รูปแบบ OpenAI ที่ llama-server ส่ง: ชื่อก่อน แล้วอาร์กิวเมนต์ทีละส่วน
            call = {"index": 0, "id": "c1", "type": "function",
                    "function": {"name": "machine-status", "arguments": ""}}  # fmt: skip
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
        tokens = ["สวัส", "ดี", "ครับ"] if self.mode != "slow" else ["ช้า"] * 40
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
        FakeLlama.mode, FakeLlama.seen = "ok", []
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLlama)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.target = client.Target(url=f"http://127.0.0.1:{self.srv.server_port}")


class ClientTest(ServerCase):
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
        pump(lambda: picked)
        self.assertEqual(picked, [("machine-status", "คอมหน่วงมาก เป็นอะไร")])
        body = FakeLlama.seen[-1]
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

    def test_not_ready_refuses(self):
        c = ChatController(target=client.Target(), poll_ms=100000)
        self.addCleanup(c.shutdown)
        self.assertFalse(c.send("x", ""))
        self.assertEqual(ChatController(active=False).status, "off")


if __name__ == "__main__":
    unittest.main()
