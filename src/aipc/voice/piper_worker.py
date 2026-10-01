"""ตัวสังเคราะห์เสียงที่เปิดค้าง (การ์ด 0019) · รันด้วย python ของ /opt/aipc-voice/venv ไม่ใช่ของแอป.

เปิดค้างเพราะวัดบน Pi 5 แล้ว: เปิดใหม่ทุกครั้ง 6.3 วิ · โหลดค้างไว้ 0.4–0.8 วิต่อประโยค
ไฟล์นี้ต้องไม่ import อะไรจาก aipc (venv ของเสียงไม่มีแพ็กเกจแอป)

รับคำสั่งทาง stdin บรรทัดละ JSON:
  {"cmd": "say", "id": 3, "chunks": ["...", "..."], "dir": "/run/user/1001/aipc-tts"}
  {"cmd": "cancel", "id": 3}
ตอบทาง stdout: {"ready": true} · {"id": 3, "i": 0, "path": ".../3-0.wav", "last": false}
  · {"id": 3, "error": "..."}
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import wave


def main() -> int:
    from piper import PiperVoice

    voice = PiperVoice.load(sys.argv[1])
    out = sys.stdout
    jobs: queue.Queue = queue.Queue()
    cancelled: set[int] = set()

    def read() -> None:
        for line in sys.stdin:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("cmd") == "cancel":
                cancelled.add(int(msg["id"]))
            elif msg.get("cmd") == "say":
                jobs.put(msg)
        jobs.put(None)  # stdin ปิด = แอปปิด

    threading.Thread(target=read, daemon=True).start()
    print(json.dumps({"ready": True}), file=out, flush=True)
    while (job := jobs.get()) is not None:
        jid, chunks = int(job["id"]), job["chunks"]
        for i, text in enumerate(chunks):
            if jid in cancelled:
                break
            path = os.path.join(job["dir"], f"{jid}-{i}.wav")
            try:
                with wave.open(path, "wb") as w:
                    voice.synthesize_wav(text, w)
            except Exception as e:  # noqa: BLE001 · บอกแอปแทนการตายเงียบ
                print(
                    json.dumps({"id": jid, "error": f"{type(e).__name__}: {e}"}),
                    file=out,
                    flush=True,
                )
                break
            msg = {"id": jid, "i": i, "path": path, "last": i == len(chunks) - 1}
            print(json.dumps(msg), file=out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
