"""สวิตช์ "เข้าเครื่องด้วยใบหน้า" ในหน้าตั้งค่า (การ์ด 0015 ข้อ 2 = ก. เจ้าของบัญชีเลือกเปิดเอง).

คุยกับ visiond ผ่าน aipc.vision.client · เปิด = สแกน 5 ท่าใหม่ผ่าน visiond
(แม่แบบของหน้า Login แยกจากแม่แบบในเซสชัน) ·
ปิด = ลบแม่แบบของหน้า Login · ทั้งสองอย่างต้องใส่รหัสผ่าน (visiond ให้ตัวช่วย root ตรวจ · หน้าจอนี้ไม่ตรวจเอง)
visiond เช็กเองว่าผู้ขอคือเจ้าของบัญชี (uid ของโปรเซส) · หน้าจอส่งได้แค่ชื่อของตัวเอง
"""

from __future__ import annotations

import getpass
import threading
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot


class LoginFaceController(QObject):
    changed = Signal()
    _done = Signal(object)
    _hint = Signal(str)

    def __init__(self, face=None, user: str | None = None):
        super().__init__()
        self._face = face  # face(req, on_progress) → dict · None = ไม่มี visiond
        self._user = user or getpass.getuser()
        self._state = "unavailable"  # unavailable | enabled | disabled
        self._busy = False
        self._message = ""
        self._done.connect(self._on_done)
        self._hint.connect(self._on_hint)
        self.refresh()

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Slot()
    def refresh(self) -> None:
        if self._face is None:
            self._state = "unavailable"
        else:
            r = self._face({"op": "enabled", "username": self._user}, None)
            state = r.get("state")
            self._state = state if state in ("enabled", "disabled") else "unavailable"
        self.changed.emit()

    def _run(self, req: dict) -> bool:
        if self._busy or self._face is None:
            return False
        self._busy, self._message = True, ""
        self.changed.emit()

        def work():
            self._done.emit(self._face(req, lambda m: self._hint.emit(str(m.get("hint", "")))))

        threading.Thread(target=work, daemon=True).start()
        return True

    @Slot(str, result=bool)
    def enable(self, password: str) -> bool:
        """ผู้ใช้ติ๊กยินยอมแล้ว (หน้าจอบังคับ) · สแกน 5 ท่า."""
        consent = datetime.now().astimezone().isoformat(timespec="seconds")
        return self._run({"op": "enroll", "username": self._user, "password": password,
                          "consent_at": consent})  # fmt: skip

    @Slot(str, result=bool)
    def disable(self, password: str) -> bool:
        return self._run({"op": "remove", "username": self._user, "password": password})

    def _on_hint(self, hint: str) -> None:
        if hint and hint != self._message:
            self._message = hint
            self.changed.emit()

    def _on_done(self, res: dict) -> None:
        self._busy = False
        state = res.get("state")
        if state == "saved":
            self._message = "เปิดแล้ว · ครั้งหน้าที่หน้า Login แค่มองกล้องก็เข้าได้"
        elif state == "removed":
            self._message = "ปิดแล้ว · ลบข้อมูลใบหน้าของหน้า Login แล้ว"
        else:
            self._message = str(res.get("message") or "ไม่สำเร็จ · ลองใหม่อีกครั้ง")
        self.refresh()
