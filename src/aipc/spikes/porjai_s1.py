"""การ์ด 0082 S1 ชุด P: ต่อเสียงสั้นจากชุดเสียงสาธารณะ Porjai เป็นไฟล์ยาวไฟล์เดียว + เฉลย.

ชุดเสียง: CMKL Porjai (CC BY-SA 4.0) · Pakon ตัดสิน 2026-11-22: ใช้ชุดสาธารณะแทนการอัดเอง ·
รันบน Pi (ต้องมีเน็ตและ ffmpeg) · ไฟล์เสียงอยู่นอก git เสมอ (กฎเหล็กข้อ 4):

    python -m aipc.spikes.porjai_s1 --out ~/s1-porjai
    python -m aipc.spikes.meeting_s1 run --audio ~/s1-porjai/porjai-s1.wav
        --ref ~/s1-porjai/porjai-s1.txt --label P1 --out ~/s1-p1.json

ดึงแถวผ่าน API ของ Hugging Face (datasets-server · ไม่ต้องลงไลบรารีอ่าน parquet) ·
เลือกแถวตายตัว กระจายทั้งชุด (หลายคนพูด) · ffmpeg แปลง mp3 → 16 kHz 16 bit mono ·
คั่นแต่ละประโยคด้วยความเงียบ GAP_S วินาที (ให้ตัวตัดท่อนของ S1 ตัดที่ช่วงเงียบได้)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path

RATE = 16000
GAP_S = 0.4
DATASET = "CMKL/Porjai-Thai-voice-dataset-central"
TOTAL = 335674  # แถวทั้งหมดของ split train (API ตอบ num_rows_total 2026-11-22)
LICENSE = "CC BY-SA 4.0 · Porjai Thai voice dataset (CMKL) · Suwanbandit et al., INTERSPEECH 2023"
API = "https://datasets-server.huggingface.co/rows"
AGENT = "aipc-bench"  # ชื่อกลาง ๆ ไม่มีข้อมูลผู้ใช้


def offsets(total: int = TOTAL, groups: int = 30, per_group: int = 10) -> list[int]:
    """จุดเริ่มของแต่ละกลุ่ม (แถวติดกัน per_group แถว) · ห่างเท่ากันทั้งชุด · ได้ชุดเดิมทุกครั้ง (ประกาศก่อนวัดได้)."""
    step = (total - per_group) // groups
    return [i * step for i in range(groups)]


def fetch_rows(offset: int, length: int) -> list[dict]:
    """แถวจาก API · คืน [{sentence, utterance, src}] · src = ลิงก์ mp3 ชั่วคราวของ API."""
    q = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "train",
                                "offset": offset, "length": length})  # fmt: skip
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    out = []
    for item in data["rows"]:
        row = item["row"]
        audio = row["audio"][0] if isinstance(row["audio"], list) else row["audio"]
        out.append(
            {"sentence": row["sentence"], "utterance": row["utterance"], "src": audio["src"]}
        )
    return out


def convert_ffmpeg(src: str, dest: Path) -> None:
    """ดาวน์โหลด mp3 แล้วแปลงเป็น wav 16 kHz mono 16 bit · ffmpeg อ่านไฟล์ชั่วคราว (ไม่ต่อเน็ตเอง)."""
    req = urllib.request.Request(src, headers={"User-Agent": AGENT})
    with (
        urllib.request.urlopen(req, timeout=60) as r,
        tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f,
    ):
        f.write(r.read())
        mp3 = Path(f.name)
    try:
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(mp3),
               "-ar", str(RATE), "-ac", "1", "-sample_fmt", "s16", str(dest)]  # fmt: skip
        subprocess.run(cmd, check=True, timeout=60)
    finally:
        mp3.unlink(missing_ok=True)


def build(starts: list[int], *, per_group: int, out: Path,
          fetch: Callable[[int, int], list[dict]] = fetch_rows,
          convert: Callable[[str, Path], None] = convert_ffmpeg) -> dict:  # fmt: skip
    """ต่อเสียงทุกประโยคเป็น porjai-s1.wav · เฉลย porjai-s1.txt (บรรทัดละประโยค) · ที่มา porjai-s1.json ·
    ประโยคที่โหลด/แปลงไม่ได้ = ข้าม และจดไว้ (ไม่ทำให้ทั้งชุดล้ม)."""
    out.mkdir(parents=True, exist_ok=True)
    gap = b"\x00\x00" * int(RATE * GAP_S)
    sentences, ids, skipped = [], [], []
    with wave.open(str(out / "porjai-s1.wav"), "wb") as w, tempfile.TemporaryDirectory() as tmp:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        for start in starts:
            for row in fetch(start, per_group):
                clip = Path(tmp) / "clip.wav"
                try:
                    convert(row["src"], clip)
                    with wave.open(str(clip), "rb") as c:
                        if (c.getframerate(), c.getnchannels(), c.getsampwidth()) != (RATE, 1, 2):
                            raise ValueError("รูปแบบเสียงไม่ใช่ 16 kHz mono 16 bit")
                        frames = c.readframes(c.getnframes())
                except Exception:  # noqa: BLE001 · ประโยคเดียวพัง = ข้าม (จดชื่อ)
                    skipped.append(row["utterance"])
                    continue
                w.writeframes(frames + gap)
                sentences.append(row["sentence"].strip())
                ids.append(row["utterance"])
    (out / "porjai-s1.txt").write_text("\n".join(sentences), encoding="utf-8", newline="\n")
    meta = {"dataset": DATASET, "license": LICENSE, "starts": starts, "per_group": per_group,
            "utterances": ids, "skipped": skipped, "gap_s": GAP_S}  # fmt: skip
    (out / "porjai-s1.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return {"count": len(ids), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.porjai_s1")
    p.add_argument("--out", required=True)
    p.add_argument("--groups", type=int, default=30)
    p.add_argument("--per-group", type=int, default=10)
    a = p.parse_args(argv)
    info = build(offsets(groups=a.groups, per_group=a.per_group), per_group=a.per_group,
                 out=Path(a.out).expanduser())  # fmt: skip
    print(json.dumps(info, ensure_ascii=False))
    return 0 if info["count"] else 1


if __name__ == "__main__":
    sys.exit(main())
