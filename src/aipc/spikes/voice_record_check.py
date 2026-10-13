"""การ์ด 0026: ตรวจหน้าอัดเสียง (record.html) ด้วย Chromium จริง · ไมค์ปลอมจากไฟล์เสียง.

    WAYLAND_DISPLAY=wayland-0 python -m aipc.spikes.voice_record_check
        <record.html> <เสียง.wav> <โฟลเดอร์ส่งออก>

ขั้นตอนเหมือนคน: ขอใช้ไมค์ → เริ่มอัด → กด Space → (เสียงในไฟล์ = คนพูด แล้วเงียบ) → หน้าหยุดอัดเองและไปข้อถัดไป →
ส่งออก → ตรวจว่าได้ไฟล์ JSON ที่มี WAV 16 kHz ความยาวพอดีกับเสียงพูด
"""

from __future__ import annotations

import base64
import io
import json
import sys
import tempfile
import time
import wave
from pathlib import Path

from aipc.browser.control import BrowserControl


def main() -> int:
    page, audio, out_dir = (
        Path(sys.argv[1]).resolve(),
        Path(sys.argv[2]).resolve(),
        Path(sys.argv[3]),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    bc = BrowserControl(
        profile=Path(tempfile.mkdtemp(prefix="rec-check-")),
        extra_args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={audio}%noloop",
            "--autoplay-policy=no-user-gesture-required",
        ],
    )
    bc._start(page.as_uri())
    bc._page()
    with bc._lock:
        bc._cdp.call(
            "Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(out_dir)}
        )

    def js(expr: str):
        with bc._lock:
            return bc._eval(expr)

    def wait(expr: str, secs: float) -> bool:
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if js(expr):
                return True
            time.sleep(0.2)
        return False

    js("indexedDB.deleteDatabase('aipc-voice-record'); true")
    time.sleep(0.5)
    js("location.reload(); true")
    time.sleep(2)
    js("document.getElementById('perm').click(); true")
    assert wait("!document.getElementById('start').disabled", 10), "ขอใช้ไมค์ไม่สำเร็จ"
    mics = js("[...document.getElementById('mic').options].map(o => o.text)")
    js("document.getElementById('start').click(); true")
    assert wait("!document.getElementById('work').classList.contains('hidden')", 10), "เริ่มไม่ได้"
    first = js("document.getElementById('prompt').textContent")
    js("document.dispatchEvent(new KeyboardEvent('keydown', {code: 'Space'})); true")
    t0 = time.monotonic()
    ok = wait("document.getElementById('state').className === 'done'", 20)
    stopped = round(time.monotonic() - t0, 1)
    state = js("document.getElementById('state').textContent")
    pos = js("document.getElementById('pos').textContent")
    time.sleep(1.0)
    pos_after = js("document.getElementById('pos').textContent")
    js("window.confirm = () => true; document.getElementById('export').click(); true")
    time.sleep(3)
    files = sorted(out_dir.glob("voice-*.json"))
    report = {
        "mics": mics,
        "first_prompt": first,
        "recorded": ok,
        "stop_after_s": stopped,
        "state": state,
        "pos": pos,
        "pos_after_auto_next": pos_after,
        "exported": [f.name for f in files],
    }
    if files:
        d = json.loads(files[-1].read_text(encoding="utf-8"))
        it = d["items"][0]
        with wave.open(io.BytesIO(base64.b64decode(it["wav"]))) as w:
            report["wav"] = {
                "rate": w.getframerate(),
                "channels": w.getnchannels(),
                "secs": round(w.getnframes() / w.getframerate(), 2),
            }
        report["item"] = {k: it[k] for k in ("id", "set", "mode", "prompt", "secs", "peak")}
        (out_dir / "first.wav").write_bytes(base64.b64decode(it["wav"]))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    bc.close()
    return 0 if ok and files else 1


if __name__ == "__main__":
    raise SystemExit(main())
