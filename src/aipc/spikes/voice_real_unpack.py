"""การ์ด 0026: แกะไฟล์ที่หน้าอัดเสียงส่งออก (voice-*.json · เสียงฝังเป็น base64) ให้ตัววัดทุกตัวอ่านได้.

    python -m aipc.spikes.voice_real_unpack <voice-….json ...> <โฟลเดอร์เสียง> [--sets D,H]

ได้ <โฟลเดอร์เสียง>/real_D/NN-16k.wav + <โฟลเดอร์เสียง>/real_D.json
(รูปแบบเดียวกับ tests/data/browse_v*.json)
→ ใช้กับ voice_models_eval / voice_zipformer_eval ได้ทันที (ชื่อชุด = ชื่อไฟล์ .json)

- คำตอบที่ถูก (expect) อ่านจาก tests/data/voice_real_prompts.json ตาม id · ไม่เชื่อค่าในไฟล์ส่งออก (H8)
- id เดียวกันอัดหลายครั้ง (อัดใหม่) = ใช้ครั้งล่าสุดในไฟล์ที่ระบุทีหลัง
- เสียงคนจริง: เก็บนอก git (การ์ด 0026 หัวข้อ 5) · โฟลเดอร์เสียงควรเป็น 0700
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import wave
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[3] / "tests/data/voice_real_prompts.json"


def unpack(exports: list[Path], out: Path, sets: list[str], prompts: Path = PROMPTS) -> dict:
    known = {it["id"]: it for it in json.loads(prompts.read_text(encoding="utf-8"))["items"]}
    latest: dict[str, dict] = {}
    for path in exports:
        for it in json.loads(path.read_text(encoding="utf-8"))["items"]:
            if it.get("id") in known:
                latest[it["id"]] = it
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)
    counts = {}
    for s in sets:
        ids = sorted((i for i in latest if known[i]["set"] == s), key=lambda i: int(i[1:]))
        folder = out / f"real_{s}"
        folder.mkdir(exist_ok=True)
        items = []
        for n, i in enumerate(ids):
            raw = base64.b64decode(latest[i]["wav"])
            with wave.open(io.BytesIO(raw)) as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
                    raise ValueError(f"{i}: ต้องเป็น 16 kHz โมโน 16 บิต")
            (folder / f"{n:02d}-16k.wav").write_bytes(raw)
            p = known[i]
            items.append({"id": i, "text": p["prompt"], "mode": p["mode"], "expect": p["expect"]})
        (out / f"real_{s}.json").write_text(
            json.dumps({"about": f"เสียงคนจริงชุด {s} (แกะจากหน้าอัด)", "items": items},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )  # fmt: skip
        counts[s] = len(items)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("exports", nargs="+")
    ap.add_argument("out")
    ap.add_argument("--sets", default="D")
    a = ap.parse_args()
    counts = unpack([Path(x) for x in a.exports], Path(a.out), a.sets.split(","))
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
