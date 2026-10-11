"""ขับ SkillsController + ChatController ตัวจริงของแอป โดยไม่มีหน้าจอ (ตัววัดการ์ด 0022).

ลำดับเดียวกับ WorkspacePage.qml: skills.handle(ข้อความ) → การ์ด → งานของ AI = chat.send ·
AI เลือกสกิล (skillRequested) → skills.handleAs → ทำซ้ำ · Claude สร้างสกิลเสร็จ (forgeDone) → ทำงานนั้นต่อ ·
สร้างไม่สำเร็จ = askCloudFor · การ์ดที่ต้องยืนยัน (ขั้นตอนของสกิล) = กด "ใช่" ให้เมื่อ auto_confirm

AI ในเครื่อง = llama-server ที่ server (เช่น Pi 5 ผ่าน SSH tunnel) · Claude = cloud(คำถาม, บทสนทนา)
(ตัวจริง = aipc.ui.app._cloud_client · ตัวปลอม = ไม่เสียเงิน ใช้ตอนปรับกฎด้วยชุดพัฒนา)
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer, Slot


@dataclass
class Turn:
    route: str = ""  # local · cloud · skill:<id> · rule:<kind> · create · error
    text: str = ""  # คำตอบสุดท้ายที่ผู้ใช้เห็น (หรือหัวการ์ด)
    local_text: str = ""  # คำตอบของ AI ในเครื่อง (ก่อนส่งต่อ ถ้ามี)
    local_tool: str = ""
    raw: str = ""  # token ที่ AI ในเครื่องส่งมาจริง (ก่อนแอปตัดป้ายปลอม)
    forwarded: str = ""  # "" = ไม่ส่งต่อ · เหตุผลที่ส่ง (จาก trace ของแอป)
    note: str = ""
    seconds: float = 0.0
    cards: list = field(default_factory=list)  # การ์ดทุกใบที่หน้าจอจะแสดง
    plans: list = field(default_factory=list)  # คำสั่งเครื่องที่ถูกสั่งจริง [action, params]
    skill_prompt: str = ""  # prompt ของสกิลที่ส่งให้ AI (สกิลงานภาษา)


class RecExecutor:
    """แทน actions.Executor: จดคำสั่งเครื่องที่ถูกสั่ง ไม่ทำจริง."""

    dry_run = True

    def __init__(self):
        self.plans: list = []

    def execute(self, plan):
        from aipc.skills.actions import Outcome

        self.plans.append([plan.action, dict(plan.params)])
        return Outcome(True, plan.summary, simulated=True)


class AppDriver(QObject):
    def __init__(self, server: str, cloud=None, forge=None, user_skills=None, model_name: str = "",
                 workdir: Path | None = None):  # fmt: skip
        super().__init__()
        self.app = QCoreApplication.instance() or QCoreApplication([])
        from aipc.chat import client
        from aipc.chat.store import ChatStore
        from aipc.ui.backend import ChatController, SkillsController

        work = Path(workdir) if workdir else Path(".")
        self.exec = RecExecutor()
        holder: dict = {}
        self.chat = ChatController(
            active=True, target=client.Target(url=server), store=ChatStore(work / "chats"),
            tools=lambda text="": holder["skills"].tool_catalog(text), cloud=cloud,
            model_name=model_name, forge=forge is not None, claude_on=lambda: True,
            meter=lambda: None,
        )  # fmt: skip
        self.skills = SkillsController(
            executor=self.exec, reminders_path=work / "reminders.json", run_timer=False,
            llm_ready=lambda: self.chat.ready, forge=forge, user_skills=user_skills,
            claude_on=lambda: True, weather=None,
        )  # fmt: skip
        holder["skills"] = self.skills
        self.chat.statusChanged.connect(self.skills.skillsChanged)
        self.chat.finished.connect(self._on_finished)
        self.chat.skillRequested.connect(self._on_skill)
        self.chat._done.connect(self._on_reply)
        self.chat._token.connect(self._on_token)
        self.skills.forgeDone.connect(self._on_forged)
        self._turn: Turn | None = None
        self._waiting = 0
        self._loop: QEventLoop | None = None
        self.auto_confirm = True

    # ---------- รอ ----------
    def _spin(self, done, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while not done():
            if time.monotonic() > end:
                return False
            loop = QEventLoop()
            QTimer.singleShot(50, loop.quit)
            loop.exec()
        return True

    def wait_ready(self, timeout: float = 600) -> bool:
        return self._spin(lambda: self.chat.ready, timeout)

    # ---------- หนึ่งข้อความ ----------
    def say(self, text: str, history: list[dict] | None = None, timeout: float = 600) -> Turn:
        """ข้อความเดียวในแชทใหม่ที่มี history ก่อนหน้า (แบบเดียวกับเปิดแชทเก่าแล้วพิมพ์ต่อ)."""
        from aipc.chat import store

        # tunnel หลุดระหว่างข้อ (2026-10-12: IP วินโดวส์เปลี่ยน) = รอต่อใหม่ · ไม่กลับ = ข้อนี้เป็นความผิดของตัววัด
        if not self.wait_ready(300):
            return Turn(route="infra", note="AI ในเครื่องไม่พร้อมก่อนเริ่มข้อ (ตัววัด)")
        self.chat.newChat(True)  # แชทชั่วคราว: ไม่เขียนประวัติ
        conv = store.new_conversation()
        conv["messages"] = copy.deepcopy(history or [])
        self.chat._conv = conv
        self.exec.plans = []
        self._turn = Turn()
        self._waiting = 0
        t0 = time.monotonic()
        self._dispatch(self.skills.handle(text), text)
        ok = self._spin(lambda: self._waiting == 0, timeout)
        t = self._turn
        t.seconds = round(time.monotonic() - t0, 2)
        t.plans = list(self.exec.plans)
        if not ok:
            t.route, t.note = "error", f"หมดเวลา {timeout} วิ"
        trace = self.chat._trace
        if trace.get("cloud"):
            t.forwarded = trace["cloud"]["why"]
        self._turn = None
        return t

    def _dispatch(self, card: dict, text: str) -> None:
        t = self._turn
        card = dict(card)
        t.cards.append(card)
        if card.get("kind") == "forging":
            t.route = "create"
            self._waiting += 1  # รอ forgeDone
            return
        if card.get("confirmToken") and self.auto_confirm and card.get("kind") == "steps":
            card = dict(self.skills.confirm(card["confirmToken"], True))
            t.cards.append(card)
        to_ai = bool(card.get("llm")) and self.chat.send(
            card.get("llmText") or text, card.get("prompt") or "", card.get("tools") is not False
        )
        if to_ai:
            name = (card.get("badge") or {}).get("name")
            if not t.route.startswith("skill:"):  # กฎเลือกสกิลงานภาษา (แปล/สรุป) หรือคุยทั่วไป
                t.route = f"rule:{card.get('kind', '')}:{name}" if name else "local"
            t.skill_prompt = card.get("prompt") or ""
            self._waiting += 1
            return
        if not t.route or t.route == "create":
            badge = card.get("badge") or {}
            t.route = f"rule:{card.get('kind', '')}" + (f":{badge.get('name')}" if badge else "")
        t.text = card.get("title", "")

    @Slot(str)
    def _on_token(self, token: str) -> None:
        if self._turn is not None:
            self._turn.raw += token

    @Slot(object)
    def _on_reply(self, reply) -> None:
        t = self._turn
        if t is not None and not getattr(reply, "cloud", False) and not t.local_text:
            t.local_text, t.local_tool = reply.text, reply.tool_call

    @Slot(str, str)
    def _on_finished(self, text: str, note: str) -> None:
        t = self._turn
        if t is None:
            return
        t.text, t.note = text, note
        if self.chat._trace.get("cloud"):
            t.route = "cloud"
        self._waiting -= 1

    @Slot(str, str)
    def _on_skill(self, skill_id: str, text: str) -> None:
        t = self._turn
        if t is None:
            return
        self._waiting -= 1
        t.route = f"skill:{skill_id}"
        self._dispatch(self.skills.handleAs(skill_id, text), text)

    @Slot("QVariantMap", str)
    def _on_forged(self, card: dict, text: str) -> None:
        t = self._turn
        if t is None:
            return
        self._waiting -= 1
        if card.get("fallback"):
            t.cards.append(dict(card))
            if self.chat.askCloudFor(text):
                self._waiting += 1
            return
        t.route = "create"
        self._dispatch(card, text)

    def close(self) -> None:
        self.chat.shutdown()
