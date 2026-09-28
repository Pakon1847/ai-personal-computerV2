"""ประวัติแชท (การ์ด 0013 ข้อ 4) · 1 ไฟล์ต่อบทสนทนาใน home ของผู้ใช้ · เขียนแบบ atomic."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from aipc import fsutil


def default_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "aipc" / "chats"


def new_conversation() -> dict:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "id": uuid.uuid4().hex[:12],
        "title": "",
        "created": now,
        "updated": now,
        "messages": [],
    }


class ChatStore:
    def __init__(self, folder: Path | None = None):
        self.folder = folder or default_dir()

    def _path(self, cid: str) -> Path:
        if not cid.isalnum():  # id มาจากเราเอง แต่ห้ามให้กลายเป็น path ออกนอกโฟลเดอร์
            raise ValueError(cid)
        return self.folder / f"{cid}.json"

    def save(self, conv: dict) -> None:
        conv["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if not conv["title"]:
            first = next((m["content"] for m in conv["messages"] if m["role"] == "user"), "")
            conv["title"] = first.strip().replace("\n", " ")[:40]
        fsutil.write_json(self._path(conv["id"]), conv)

    def load(self, cid: str) -> dict | None:
        try:
            conv = json.loads(self._path(cid).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return conv if isinstance(conv, dict) and isinstance(conv.get("messages"), list) else None

    def list(self) -> list[dict]:
        out = []
        for p in self.folder.glob("*.json"):
            conv = self.load(p.stem)
            if conv:
                out.append(
                    {
                        "id": conv["id"],
                        "title": conv.get("title", ""),
                        "updated": conv.get("updated", ""),
                    }
                )
        return sorted(out, key=lambda c: c["updated"], reverse=True)

    def delete(self, cid: str) -> None:
        self._path(cid).unlink(missing_ok=True)

    def delete_all(self) -> int:
        n = 0
        for p in self.folder.glob("*.json"):
            p.unlink(missing_ok=True)
            n += 1
        return n
