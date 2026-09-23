"""ประเมินการจับคู่ใบหน้าจากโฟลเดอร์ภาพ → FAR, FRR, EER, threshold ที่ FAR 0.1%, ROC (การ์ด 0005 ข้อ 9).

    python -m aipc.vision.evaluate <โฟลเดอร์> --out <โฟลเดอร์ผล> [--name LFW]

โครงโฟลเดอร์: <โฟลเดอร์>/<ชื่อคน>/<ภาพ>.jpg (แบบ LFW) · ต้องมีอย่างน้อย 2 คน และบางคนมี ≥ 2 ภาพ
ขั้นต่อภาพ: YuNet (หน้าใหญ่สุด) → align → SFace · ไม่ผ่าน quality gate ของการใช้งานจริง
(ภาพชุดสาธารณะมักเล็กกว่า 112 px จึงรายงานอัตราผ่าน gate แยกไว้ ไม่ตัดทิ้ง)

ผลลัพธ์ (ไม่มีภาพ ไม่มี embedding · มีแค่ชื่อไฟล์และคะแนน):
- metrics.json  ตัวเลขทั้งหมด + commit + sha256 โมเดล + จำนวนคู่ + เวลาต่อภาพ
- scores.csv    ค่าดิบทุกคู่ (label, score, ภาพ a, ภาพ b) → คำนวณซ้ำได้
- roc.png       กราฟ ROC แกน FAR แบบ log
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np

from aipc.vision import align, config, matching, metrics, models, quality

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp"}


def list_people(root: Path) -> dict[str, list[Path]]:
    people = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        files = sorted(f for f in d.iterdir() if f.suffix.lower() in IMAGE_TYPES)
        if files:
            people[d.name] = files
    return people


def make_pairs(ids: dict[str, list[int]], max_genuine: int, max_impostor: int, seed: int):
    """คู่ genuine ทุกคู่ภายในคนเดียวกัน (สุ่มลดถ้าเกิน) + คู่ impostor สุ่มข้ามคน · seed คงที่ = ทำซ้ำได้."""
    rng = np.random.default_rng(seed)
    genuine = [p for idx in ids.values() for p in combinations(idx, 2)]
    if len(genuine) > max_genuine:
        genuine = [genuine[k] for k in sorted(rng.choice(len(genuine), max_genuine, replace=False))]
    owner = {i: name for name, idx in ids.items() for i in idx}
    allidx = np.array(sorted(owner))
    impostor, seen = [], set()
    tries = 0
    while len(impostor) < max_impostor and tries < max_impostor * 20:
        tries += 1
        a, b = (int(x) for x in rng.choice(allidx, 2, replace=False))
        key = (min(a, b), max(a, b))
        if owner[a] != owner[b] and key not in seen:
            seen.add(key)
            impostor.append(key)
    return genuine, impostor


def git_commit() -> str:
    try:
        # --dirty = โค้ดที่รันมีส่วนที่ยังไม่ commit → ตัวเลขนี้ทำซ้ำจาก commit นั้นตรง ๆ ไม่ได้
        cmd = ["git", "describe", "--always", "--dirty"]
        here = Path(__file__).parent
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=here, timeout=5)
        return out.stdout.strip() or "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def roc_png(c: metrics.Curve, eer_rate: float, path: Path, title: str) -> None:
    """วาด ROC ด้วย OpenCV (ไม่เพิ่ม matplotlib) · แกน x = FAR แบบ log 1e-4 … 1 · แกน y = TAR."""
    import cv2

    w, h, m = 900, 640, 80
    font, ink = cv2.FONT_HERSHEY_SIMPLEX, (0, 0, 0)
    img = np.full((h, w, 3), 255, np.uint8)
    lo, hi = -4.0, 0.0

    def xy(far, tar):
        lf = np.log10(np.clip(far, 10**lo, 1.0))
        return int(m + (lf - lo) / (hi - lo) * (w - 2 * m)), int(h - m - tar * (h - 2 * m))

    grid = (220, 220, 220)
    for e in range(int(lo), int(hi) + 1):
        x, _ = xy(10.0**e, 0)
        cv2.line(img, (x, m), (x, h - m), grid, 1)
        cv2.putText(img, f"1e{e}", (x - 18, h - m + 25), font, 0.5, ink, 1)
    for k in range(11):
        _, y = xy(1, k / 10)
        cv2.line(img, (m, y), (w - m, y), grid, 1)
        cv2.putText(img, f"{k / 10:.1f}", (m - 40, y + 5), font, 0.5, ink, 1)
    pts = np.array([xy(f, t) for f, t in zip(c.far, c.tar, strict=True)], np.int32)
    cv2.polylines(img, [pts], False, (180, 60, 40), 2, cv2.LINE_AA)
    cv2.rectangle(img, (m, m), (w - m, h - m), ink, 1)
    cv2.putText(img, "FAR (log)", (w // 2 - 40, h - 25), font, 0.6, ink, 1)
    cv2.putText(img, "TAR", (15, h // 2), font, 0.6, ink, 1)
    cv2.putText(img, f"{title}  EER={eer_rate * 100:.2f}%", (m, 50), font, 0.7, ink, 2)
    cv2.imwrite(str(path), img)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.vision.evaluate")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default="", help="ชื่อชุดข้อมูลในรายงาน เช่น LFW")
    ap.add_argument("--config", type=Path, help="ไฟล์ค่าตั้งใบหน้า (threshold ที่จะรายงาน FAR/FRR)")
    ap.add_argument("--max-genuine", type=int, default=20000)
    ap.add_argument("--max-impostor", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit-people", type=int, default=0, help="ใช้แค่ N คนแรก (ทดลองเร็ว ๆ)")
    a = ap.parse_args(argv)
    # คอนโซลวินโดวส์ภาษาไทยใช้ cp874 ที่ไม่มีบางตัวอักษร (เช่น ·) → พิมพ์เป็น UTF-8 แทนการล่มตอนท้าย
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    import cv2

    cfg = config.load(a.config)
    people = list_people(a.folder)
    if a.limit_people:
        people = dict(list(people.items())[: a.limit_people])
    det, emb = models.Detector(cfg.min_detect_score), models.Embedder()

    files, vecs, ids, per_image_ms = [], [], {}, []
    no_face = gate_pass = total = 0
    for name, paths in people.items():
        for p in paths:
            total += 1
            img = cv2.imread(str(p))
            t0 = time.perf_counter()
            faces = det.detect(img) if img is not None else []
            if not faces:
                no_face += 1
                continue
            f = quality.Face.from_yunet(faces[0])
            gate_pass += quality.check(img, f, cfg).ok
            v = matching.l2_normalize(emb.embed(align.crop(img, f.landmarks)))
            per_image_ms.append((time.perf_counter() - t0) * 1000)
            ids.setdefault(name, []).append(len(files))
            files.append(p.relative_to(a.folder).as_posix())
            vecs.append(v)
        print(f"\r{total} ภาพ", end="", file=sys.stderr)
    print(file=sys.stderr)

    genuine, impostor = make_pairs(ids, a.max_genuine, a.max_impostor, a.seed)
    if not genuine or not impostor:
        print("ข้อมูลไม่พอ: ต้องมีคนที่มี ≥ 2 ภาพ และมี ≥ 2 คน", file=sys.stderr)
        return 1
    V = np.stack(vecs)
    g_scores = np.array([float(V[i] @ V[j]) for i, j in genuine])
    i_scores = np.array([float(V[i] @ V[j]) for i, j in impostor])

    c = metrics.curve(g_scores, i_scores)
    eer_rate, eer_t = metrics.eer(c)
    t01, far01, frr01 = metrics.at_far(c, 0.001)
    far_cfg, frr_cfg = metrics.rates_at(g_scores, i_scores, cfg.match_threshold)

    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "scores.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["label", "score", "a", "b"])
        for lab, pairs, sc in (("genuine", genuine, g_scores), ("impostor", impostor, i_scores)):
            for (i, j), s in zip(pairs, sc, strict=True):
                wr.writerow([lab, f"{s:.6f}", files[i], files[j]])
    result = {
        "dataset": a.name or a.folder.name,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "machine": f"{sys.platform} · Python {sys.version.split()[0]} · OpenCV {cv2.__version__}",
        "models_sha256": {m.name: m.sha256 for m in (models.YUNET, models.SFACE)},
        "people": len(ids), "images": total, "images_used": len(files),
        "failure_to_acquire": round(no_face / total, 4) if total else None,
        "quality_gate_pass_rate": round(gate_pass / len(files), 4) if files else None,
        "pairs": {"genuine": len(genuine), "impostor": len(impostor), "seed": a.seed},
        "eer": round(eer_rate, 5), "eer_threshold": round(eer_t, 4),
        "at_far_0.1%": {"threshold": round(t01, 4), "far": round(far01, 5), "frr": round(frr01, 5)},
        "at_config_threshold": {"threshold": cfg.match_threshold, "far": round(far_cfg, 5),
                                "frr": round(frr_cfg, 5)},
        "per_image_ms": {"median": round(statistics.median(per_image_ms), 1),
                         "p95": round(float(np.percentile(per_image_ms, 95)), 1)},
        "note": "เวลาต่อภาพ = ตรวจหน้า + align + embedding บนเครื่องที่รัน · ไม่ใช่ตัวเลขของ Pi 5 "
                "เว้นแต่ machine ระบุว่ารันบน Pi 5",
    }  # fmt: skip
    text = json.dumps(result, ensure_ascii=False, indent=2)
    (a.out / "metrics.json").write_text(text, encoding="utf-8")
    roc_png(c, eer_rate, a.out / "roc.png", result["dataset"])
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
