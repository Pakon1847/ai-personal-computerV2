"""การ์ด 0024 เกณฑ์ข้อ 5 + ทั้งสายในแอปจริง: สคริปต์คีย์ลัด F9 → FIFO → ฟัง → ถอดเสียง → หน้าจอ → Chromium.

แทนไมค์ด้วยเสียง Piper (ถอดด้วย whisper ตัวเดียวกับแอป) · ปิดลำโพง (ตัวอ่านออกเสียงจดข้อความแทน) ·
หน้าจอ offscreen แต่ Chromium ขึ้นบน Wayland จริง (WAYLAND_DISPLAY) ·
python -m aipc.spikes.handsfree_app_e2e ผล.json
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="hf-"))
# XDG_RUNTIME_DIR เดิม: Chromium หาช่องจอ Wayland จากที่นี่ (เปลี่ยนแล้วเปิดไม่ขึ้น · พบ 2026-10-13)
os.environ.update(QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(tmp / "data"))

from PySide6.QtCore import QEventLoop, QObject, QTimer  # noqa: E402

from aipc.spikes.voice_loop_eval import SYNTH  # noqa: E402
from aipc.ui import app as uiapp  # noqa: E402
from aipc.ui.handsfree import HotkeyListener  # noqa: E402
from aipc.voice import stt, tts  # noqa: E402

SAY = ["ค้นหาราคาทองหน่อย", "เข้าลิงก์แรก", "ย้อนกลับ", "เข้าลิงก์ที่สอง", "เลื่อนลง", "ย้อนกลับ",
       "กลับไปแอป"]  # fmt: skip


def settle(ms=100):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class Mic:  # แทน pw-record: ฟังได้ทันที
    available, listening = True, False

    def start(self):
        self.listening = True
        return ""

    def stop(self):
        self.listening = False


class Mute:  # แทนลำโพง: จดว่าจะพูดอะไร
    available, current = True, -1

    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)
        self.current = len(self.said)
        return self.current

    def stop(self):
        pass

    def idle_check(self):
        pass


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    # เสียงทั้งหมดสังเคราะห์ก่อน (ไม่นับเวลา) แล้วถอดตอนทดสอบ (นับเวลา)
    (tmp / "say.json").write_text(json.dumps(SAY, ensure_ascii=False), encoding="utf-8")
    py, model = str(stt.VOICE_DIR / "venv/bin/python"), str(stt.VOICE_DIR / tts.MODEL)
    subprocess.run([py, "-c", SYNTH, model, str(tmp / "say.json"), str(tmp)], check=True,
                   capture_output=True)  # fmt: skip
    opts = uiapp.Options(
        screen="shell", page="workspace", software=True, settings_path=tmp / "ui.json"
    )
    app, engine, warnings = uiapp.build(opts)
    win = engine.rootObjects()[0]
    ctx = engine.rootContext()
    voice, browser = ctx.contextProperty("voice"), ctx.contextProperty("browser")
    voice._listener, voice._speaker = Mic(), Mute()
    page = [o for o in win.findChildren(QObject) if o.objectName() == "workspace"][0]
    hot = HotkeyListener()  # FIFO ใน $XDG_RUNTIME_DIR/aipc/voice-key แบบเซสชันจริง
    hot.pressed.connect(voice.toggleHandsFree)
    key = Path(__file__).parents[3] / "scripts" / "pi" / "session" / "aipc-voice-key"
    whisper = [str(stt.VOICE_DIR / stt.WHISPER), "-m", str(stt.VOICE_DIR / stt.MODEL), "-l", "th",
               "-t", "4", "-nt", "-ac", "512", "-f"]  # fmt: skip
    rows = []
    for i, said in enumerate(SAY):
        subprocess.run(["sh", str(key)], check=True, timeout=5)  # = กด F9
        t_key = time.monotonic()
        while not voice.listening and time.monotonic() - t_key < 3:
            settle(20)
        key_ms = round((time.monotonic() - t_key) * 1000)
        wav = tmp / f"{i:02d}-16k.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / f"{i:02d}.wav"),
                        "-ar", "16000", "-ac", "1", str(wav)], check=True)  # fmt: skip
        voice._listener.listening = False  # พูดจบ (ตัวจับเงียบหยุดอัด)
        t0 = time.monotonic()  # เริ่มนับ "หลังพูดจบ"
        heard = stt.clean(
            subprocess.run([*whisper, str(wav)], capture_output=True, text=True).stdout
        )
        stt_s = time.monotonic() - t0
        voice._heard.emit(heard, "", stt_s)
        settle(150)
        while browser.busy:
            settle(50)
        total = round(time.monotonic() - t0, 2)
        ctl = browser._control
        url = ctl._url() if ctl is not None and ctl.running else ""
        items = page.property("items")
        items = items.toVariant() if hasattr(items, "toVariant") else items
        last = items[-1] if items else {}
        shown = last.get("text") or (last.get("card") or {}).get("title") or ""
        rows.append({"said": said, "heard": heard, "key_ms": key_ms, "stt_s": round(stt_s, 2),
                     "total_s": total, "shown": shown, "spoken": voice._speaker.said[-1:],
                     "url": url})  # fmt: skip
        print(f"{i + 1}. F9 {key_ms}ms · «{heard}» · ถอด {stt_s:.1f}s · รวม {total:.1f}s · "
              f"{shown[:70]} · {url[:60]}", flush=True)  # fmt: skip
    ledger = json.loads((tmp / "data" / "aipc" / "outbound.json").read_text(encoding="utf-8"))
    res = {"rows": rows, "median_total_s": statistics.median(r["total_s"] for r in rows),
           "outbound": ledger["items"], "qml_warnings": list(warnings)}  # fmt: skip
    print("มัธยฐานหลังพูดจบ → หน้าเว็บเปลี่ยน:", res["median_total_s"], "วิ · บันทึกส่งออก:",
          [e["sent"] for e in ledger["items"]])  # fmt: skip
    browser.close()
    hot.close()
    if argv:
        Path(argv[0]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
