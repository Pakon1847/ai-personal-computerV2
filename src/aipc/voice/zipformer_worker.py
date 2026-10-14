"""ตัวถอดเสียง Zipformer ไทยที่เปิดค้าง (การ์ด 0026) · รันด้วย python ของ venv ตัวถอด ไม่ใช่ของแอป.

venv อยู่ที่ /opt/aipc-voice/zipformer/venv

เปิดค้างเพราะโหลดโมเดล 3.7 วิ แต่ถอดประโยคละ ~0.16 วิ (Pi 5 · docs/benchmarks/2026-10-14-voice-models)
ไฟล์นี้ต้องไม่ import อะไรจาก aipc (venv ของตัวถอดไม่มีแพ็กเกจแอป)

    python zipformer_worker.py <โฟลเดอร์โมเดล> <ไฟล์ hotwords หรือ -> <น้ำหนัก hotwords> <จำนวนเธรด>

รับคำสั่งทาง stdin บรรทัดละ JSON: {"id": 3, "wav": "/run/user/1001/aipc-stt/rec-….wav"}
ตอบทาง stdout: {"ready": true, "load_s": 3.7} · {"id": 3, "text": "…", "s": 0.16}
  · {"id": 3, "error": "…"}
"""

from __future__ import annotations

import array
import json
import sys
import time
import wave

RATE = 16000


def read_wav(path: str) -> list[float]:
    """WAV 16-bit mono 16 kHz (ตัวอัดของแอปตั้งไว้แบบนี้) → ตัวเลข -1..1 ที่ sherpa-onnx รับ."""
    with wave.open(path) as w:
        if (w.getsampwidth(), w.getnchannels(), w.getframerate()) != (2, 1, RATE):
            raise ValueError("ต้องเป็น 16-bit mono 16 kHz")
        a = array.array("h", w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        a.byteswap()
    return [x / 32768.0 for x in a]


def load(model_dir: str, hotwords: str, score: float, threads: int):
    import sherpa_onnx

    kw = {}
    if hotwords != "-":
        # hotwords = บอกตัวถอดว่าคำพวกนี้มีโอกาสถูกพูด → ได้ยินไม่ชัดก็เอนไปทางคำสั่ง (ไม่บังคับเหมือน grammar)
        kw = dict(decoding_method="modified_beam_search", hotwords_file=hotwords,
                  hotwords_score=score, modeling_unit="bpe",
                  bpe_vocab=f"{model_dir}/unigram_2000.vocab")  # fmt: skip
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{model_dir}/encoder-epoch-12-avg-5.int8.onnx",
        decoder=f"{model_dir}/decoder-epoch-12-avg-5.onnx",
        joiner=f"{model_dir}/joiner-epoch-12-avg-5.int8.onnx",
        tokens=f"{model_dir}/tokens.txt",
        num_threads=threads,
        **kw,
    )


def main() -> int:
    model_dir, hotwords = sys.argv[1], sys.argv[2]
    score, threads = float(sys.argv[3]), int(sys.argv[4])
    t0 = time.monotonic()
    rec = load(model_dir, hotwords, score, threads)
    out = sys.stdout
    ready = {"ready": True, "load_s": round(time.monotonic() - t0, 2)}
    print(json.dumps(ready), file=out, flush=True)
    for line in sys.stdin:  # stdin ปิด = แอปปิด
        try:
            msg = json.loads(line)
            jid = int(msg["id"])
        except (ValueError, KeyError, TypeError):
            continue
        t1 = time.monotonic()
        try:
            s = rec.create_stream()
            s.accept_waveform(RATE, read_wav(msg["wav"]))
            rec.decode_stream(s)
            reply = {"id": jid, "text": s.result.text.strip(), "s": round(time.monotonic() - t1, 3)}
        except Exception as e:  # noqa: BLE001 · บอกแอปแทนการตายเงียบ
            reply = {"id": jid, "error": f"{type(e).__name__}: {e}"}
        print(json.dumps(reply, ensure_ascii=True), file=out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
