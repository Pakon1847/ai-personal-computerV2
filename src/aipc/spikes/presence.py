"""ขั้น B: วัดก่อนสร้าง "กล้องรู้ว่าเจ้าของยังนั่งอยู่ไหม" (ล็อก/ออกเองด้วยกล้อง = ขั้น C · ทำเมื่อผ่านเกณฑ์เท่านั้น).

เกณฑ์ประกาศก่อนวัด: docs/benchmarks/2026-10-06-presence-b/README.md

    python -m aipc.spikes.presence record --seconds 1800 --out presence.jsonl     # ทาง SSH · กล้องของเครื่อง
    python -m aipc.spikes.presence analyze presence.jsonl --phases phases.json

record: เปิดกล้อง 640×480 · 2 ภาพ/วิ · YuNet ทุกภาพ · 15 วิแรกเก็บหน้าเจ้าของเป็นเวกเตอร์ในหน่วยความจำ (ไม่เขียนลงดิสก์) ·
  ทุก 2 วิที่เห็นหน้า: SFace เทียบกับเจ้าของ · เขียนแค่ตัวเลข (จำนวนหน้า คะแนน ความคล้าย CPU อุณหภูมิ) **ไม่มีภาพ**
analyze: แบ่งตามช่วงจริง (เจ้าของนั่ง · ลุกไป · คนอื่นมานั่ง · เจ้าของกลับ) แล้วคิดตัวชี้วัด M1–M4
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CAPTURE = (640, 480)
FPS = 2.0
ID_EVERY_S = 2.0
ENROLL_S = 15.0
DETECT_SIDE = 320
OWNER_THRESHOLD = 0.363  # cosine · ค่าเดียวกับการสแกนหน้าเข้าเครื่อง (aipc.vision.config.match_threshold)
GAPS = (10, 20, 30, 60)  # วินาทีที่ไม่เห็นหน้า · ใช้เลือกค่าของขั้น C
ABSENT_S = 30  # ค่าที่ Pakon เสนอ (ไม่เห็นหน้า 30 วิ → ปิดข้อมูล)
STRANGER_RUN = 3  # ไม่ใช่เจ้าของติดกันกี่ครั้งถึงนับว่ามีคนอื่น


def _temp_c() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def record(seconds: float, out: Path, clock=time.monotonic, cpu=time.process_time) -> dict:
    import cv2

    from aipc.vision import align, camera, matching, models

    cap = camera.open_camera()
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # อ่านภาพล่าสุด ไม่ใช่ภาพที่ค้างในคิว
    det, emb = models.Detector(max_side=DETECT_SIDE), models.Embedder()
    t0, owner, enroll = clock(), None, []
    last_id, n = -1e9, 0
    meta = {"capture": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))],
            "fps": FPS, "id_every_s": ID_EVERY_S, "detect_side": DETECT_SIDE, "threshold": OWNER_THRESHOLD,
            "start": time.strftime("%Y-%m-%dT%H:%M:%S")}  # fmt: skip
    with out.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"meta": meta}) + "\n")
        nxt = t0
        while clock() - t0 < seconds:
            ok, frame = cap.read()
            t = round(clock() - t0, 2)
            if not ok:
                f.write(json.dumps({"t": t, "error": "no-frame"}) + "\n")
                time.sleep(0.5)
                continue
            faces = det.detect(frame)
            row = {"t": t, "faces": len(faces), "score": round(float(faces[0][14]), 3) if faces else None,
                   "w": int(faces[0][2]) if faces else None, "cpu": round(cpu(), 2), "temp": _temp_c()}  # fmt: skip
            if faces and (t < ENROLL_S or t - last_id >= ID_EVERY_S):
                vec = matching.l2_normalize(emb.embed(align.crop(frame, faces[0][4:14].reshape(5, 2))))
                if t < ENROLL_S:
                    if len(faces) == 1 and faces[0][14] >= 0.9:
                        enroll.append(vec)
                elif owner is not None:
                    row["owner_sim"] = round(matching.cosine(vec, owner), 3)
                    last_id = t
            if owner is None and t >= ENROLL_S:
                if not enroll:
                    raise RuntimeError("15 วิแรกไม่เห็นหน้าเจ้าของชัดพอ · นั่งหน้ากล้องแล้วเริ่มใหม่")
                owner = matching.average(enroll)  # อยู่ในหน่วยความจำเท่านั้น
                f.write(json.dumps({"t": t, "enrolled": len(enroll)}) + "\n")
            f.write(json.dumps(row) + "\n")
            n += 1
            nxt += 1 / FPS
            time.sleep(max(0.0, nxt - clock()))
    cap.release()
    return {"samples": n, "enrolled": len(enroll)}


def load(path: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    meta = lines[0].get("meta", {}) if lines else {}
    return meta, [r for r in lines[1:] if "faces" in r]


def _inside(t: float, span) -> bool:
    return span[0] <= t < span[1]


def gaps(rows: list[dict], span) -> list[float]:
    """ช่วงที่ไม่เห็นหน้าติดกัน (วินาที) ภายในช่วงเวลา span."""
    out, start, prev = [], None, None
    for r in rows:
        if not _inside(r["t"], span):
            continue
        if r["faces"] == 0:
            start = r["t"] if start is None else start
        elif start is not None:
            out.append(round(r["t"] - start, 1))
            start = None
        prev = r["t"]
    if start is not None and prev is not None:
        out.append(round(prev - start, 1))
    return out


def stranger_runs(rows: list[dict], span) -> list[float]:
    """เวลาที่ตรวจพบ "ไม่ใช่เจ้าของ" ติดกัน STRANGER_RUN ครั้ง (นับจากต้นช่วง)."""
    hits, run = [], 0
    for r in rows:
        if not _inside(r["t"], span) or "owner_sim" not in r:
            continue
        run = run + 1 if r["owner_sim"] < OWNER_THRESHOLD else 0
        if run == STRANGER_RUN:
            hits.append(round(r["t"] - span[0], 1))
            run = 0
    return hits


def analyze(rows: list[dict], phases: dict) -> dict:
    present = phases["present"]
    res = {"gaps_present": {}, "max_gap_present": 0.0}
    all_gaps = [g for span in present for g in gaps(rows, span)]
    res["max_gap_present"] = max(all_gaps, default=0.0)
    res["gaps_present"] = {f">={g}s": sum(x >= g for x in all_gaps) for g in GAPS}
    away = phases["away"]
    t_absent = None
    for r in rows:  # ครั้งแรกที่ไม่เห็นหน้าติดกันครบ ABSENT_S วิ หลังลุก
        if not _inside(r["t"], away):
            continue
        g = gaps(rows, (away[0], r["t"] + 0.01))
        if g and g[-1] >= ABSENT_S:
            t_absent = round(r["t"] - away[0], 1)
            break
    res["absent_detected_after_s"] = t_absent
    res["false_stranger_present"] = sum(len(stranger_runs(rows, s)) for s in present)
    st = phases.get("stranger")
    hits = stranger_runs(rows, st) if st else []
    res["stranger_detected_after_s"] = hits[0] if hits else None
    ids = [r for span in present for r in rows if _inside(r["t"], span) and "owner_sim" in r]
    res["owner_checks"] = len(ids)
    res["owner_not_recognized"] = sum(r["owner_sim"] < OWNER_THRESHOLD for r in ids)
    if len(rows) > 1:
        a, b = rows[0], rows[-1]
        res["cpu_pct_one_core"] = round(100 * (b["cpu"] - a["cpu"]) / max(1e-9, b["t"] - a["t"]), 1)
    temps = [r["temp"] for r in rows if r.get("temp") is not None]
    res["temp_c"] = [min(temps), max(temps)] if temps else None
    res["pass"] = {
        "M1_no_gap_30s_while_present": res["gaps_present"][">=30s"] == 0,
        "M2_absent_within_35s": t_absent is not None and t_absent <= ABSENT_S + 5,
        "M3_stranger_within_10s": res["stranger_detected_after_s"] is not None
                                  and res["stranger_detected_after_s"] <= 10,
        "M3_no_false_stranger": res["false_stranger_present"] == 0,
        "M4_cpu_le_10pct": res.get("cpu_pct_one_core", 999) <= 10,
    }  # fmt: skip
    return res


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.presence")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--seconds", type=float, default=1800)
    r.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("data", type=Path)
    a.add_argument("--phases", type=Path, required=True)
    x = p.parse_args(argv)
    if x.cmd == "record":
        print(json.dumps(record(x.seconds, x.out)), file=sys.stderr)
        return 0
    _, rows = load(x.data)
    res = analyze(rows, json.loads(x.phases.read_text(encoding="utf-8")))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if all(res["pass"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
