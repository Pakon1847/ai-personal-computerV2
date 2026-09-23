"""ประเมินการจับคู่ใบหน้าจากโฟลเดอร์ภาพ → FAR, FRR, EER, threshold ที่ FAR 0.1%, ROC (การ์ด 0005 ข้อ 9).

    python -m aipc.vision.evaluate <โฟลเดอร์> --out <โฟลเดอร์ผล> [--name LFW]

โครงโฟลเดอร์: <โฟลเดอร์>/<ชื่อคน>/<ภาพ>.jpg (แบบ LFW) · ต้องมีอย่างน้อย 2 คน และบางคนมี ≥ 2 ภาพ
ขั้นต่อภาพ: YuNet (หน้าใหญ่สุด) → align → SFace · ไม่ผ่าน quality gate ของการใช้งานจริง
(ภาพชุดสาธารณะมักเล็กกว่า 112 px จึงรายงานอัตราผ่าน gate แยกไว้ ไม่ตัดทิ้ง)

ผลลัพธ์ (ไม่มีภาพ ไม่มี embedding · มีแค่ชื่อไฟล์และคะแนน):
- metrics.json  ตัวเลขทั้งหมด + commit + sha256 โมเดล + จำนวนคู่ + เวลาต่อภาพ
- scores.csv.gz ค่าดิบทุกคู่ (label, score, ภาพ a, ภาพ b) → คำนวณซ้ำได้
- roc.png       ROC: TAR เทียบ FAR (log) · แกน TAR ซูมตามข้อมูล
- det.png       DET: FRR เทียบ FAR (log ทั้งสองแกน) · กราฟมาตรฐานของงาน biometrics อ่านง่ายกว่า ROC
"""

from __future__ import annotations

import argparse
import csv
import gzip
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


def parse_lfw_pairs(text: str) -> list[tuple[str, str, bool, int]]:
    """pairs.txt ของ LFW → [(ภาพ a, ภาพ b, คนเดียวกันไหม, fold)].

    บรรทัดแรก "10 300" = 10 fold × (คนเดียวกัน 300 คู่ ตามด้วยคนละคน 300 คู่)
    คนเดียวกัน: ชื่อ i j · คนละคน: ชื่อ1 i ชื่อ2 j · ภาพ = ชื่อ/ชื่อ_0001.jpg
    """
    lines = [ln.split() for ln in text.strip().splitlines()]
    n_folds, per = (int(x) for x in lines[0])
    body = lines[1:]
    if len(body) != n_folds * per * 2:
        raise ValueError(f"pairs.txt ควรมี {n_folds * per * 2} คู่ แต่มี {len(body)}")

    def img(name, i):
        return f"{name}/{name}_{int(i):04d}.jpg"

    out = []
    for k, f in enumerate(body):
        fold = k // (per * 2)
        if len(f) == 3:
            out.append((img(f[0], f[1]), img(f[0], f[2]), True, fold))
        elif len(f) == 4:
            out.append((img(f[0], f[1]), img(f[2], f[3]), False, fold))
        else:
            raise ValueError(f"pairs.txt บรรทัด {k + 2} ต้องมี 3 หรือ 4 ช่อง: {' '.join(f)}")
    return out


def run_pairs(a, cfg, det, emb) -> dict:
    """วิธีมาตรฐานของ LFW: 6,000 คู่ 10 fold · หา threshold จาก 9 fold วัดกับ fold ที่เหลือ.

    ภาพที่หาหน้าไม่เจอ → คู่นั้นได้คะแนน −1 (นับเป็นตอบผิดถ้าเป็นคนเดียวกัน · ไม่ตัดทิ้งให้ตัวเลขสวย)
    """
    import cv2

    pairs = parse_lfw_pairs(a.pairs.read_text(encoding="utf-8"))
    cache: dict[str, np.ndarray | None] = {}
    for pa, pb, _, _ in pairs:
        for rel in (pa, pb):
            if rel in cache:
                continue
            img = cv2.imread(str(a.folder / rel))
            faces = det.detect(img) if img is not None else []
            if not faces:
                cache[rel] = None
                continue
            f = quality.Face.from_yunet(faces[0])
            cache[rel] = matching.l2_normalize(emb.embed(align.crop(img, f.landmarks)))

    def score(pa, pb):
        va, vb = cache[pa], cache[pb]
        return float(va @ vb) if va is not None and vb is not None else -1.0

    scores = np.array([score(pa, pb) for pa, pb, _, _ in pairs])
    same = np.array([p[2] for p in pairs])
    folds = np.array([p[3] for p in pairs])
    mean, std, ths = metrics.kfold_accuracy(scores, same, folds)
    c = metrics.curve(scores[same], scores[~same])
    eer_rate, eer_t = metrics.eer(c)
    a.out.mkdir(parents=True, exist_ok=True)
    with gzip.open(a.out / "scores.csv.gz", "wt", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["fold", "label", "score", "a", "b"])
        for (pa, pb, sm, fd), sc in zip(pairs, scores, strict=True):
            wr.writerow([fd, "genuine" if sm else "impostor", f"{sc:.6f}", pa, pb])
    title = f"{a.plot_title}  acc={mean * 100:.2f}%  EER={eer_rate * 100:.2f}%"
    plot(c, a.out / "roc.png", "ROC  " + title, det=False)
    plot(c, a.out / "det.png", "DET  " + title, det=True)
    return {
        "protocol": "LFW pairs.txt · 10-fold · threshold จาก 9 fold ที่เหลือ",
        "pairs": {"genuine": int(same.sum()), "impostor": int((~same).sum()), "folds": 10},
        "images": len(cache), "no_face_images": sum(v is None for v in cache.values()),
        "accuracy_mean": round(mean, 5), "accuracy_std": round(std, 5),
        "fold_thresholds": [round(t, 4) for t in ths],
        "eer": round(eer_rate, 5), "eer_threshold": round(eer_t, 4),
    }


def machine_text(cv2) -> str:
    return f"{sys.platform} · Python {sys.version.split()[0]} · OpenCV {cv2.__version__}"


def git_commit() -> str:
    try:
        # --dirty = โค้ดที่รันมีส่วนที่ยังไม่ commit → ตัวเลขนี้ทำซ้ำจาก commit นั้นตรง ๆ ไม่ได้
        cmd = ["git", "describe", "--always", "--dirty"]
        here = Path(__file__).parent
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=here, timeout=5)
        return out.stdout.strip() or "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def plot(c: metrics.Curve, path: Path, title: str, det: bool) -> None:
    """วาดกราฟด้วย OpenCV (ไม่เพิ่ม matplotlib) · แกน x = FAR แบบ log.

    det=False → ROC: แกน y = TAR เชิงเส้น ซูมตั้งแต่ค่าต่ำสุดของข้อมูล (ไม่งั้นเส้นชิดขอบบนอ่านไม่ออก)
    det=True  → DET: แกน y = FRR แบบ log
    OpenCV วาดได้แต่ตัวอักษร ASCII → ชื่อกราฟต้องเป็นภาษาอังกฤษ
    """
    import cv2

    w, h, m = 900, 640, 90
    font, ink, grid = cv2.FONT_HERSHEY_SIMPLEX, (0, 0, 0), (220, 220, 220)
    img = np.full((h, w, 3), 255, np.uint8)
    n_imp = 1.0 / max(1e-12, np.min(c.far[c.far > 0])) if np.any(c.far > 0) else 1e4
    xlo = float(np.floor(np.log10(1.0 / n_imp)))  # FAR ที่เล็กที่สุดที่วัดได้ = 1/จำนวนคู่ impostor
    if det:
        frr_pos = c.frr[c.frr > 0]
        ylo = float(np.floor(np.log10(frr_pos.min()))) if len(frr_pos) else -4.0
        ys = [10.0**e for e in range(int(ylo), 1)]
    else:
        ylo = float(np.floor(c.tar[c.far >= 10**xlo].min() * 100) / 100)
        ys = list(np.linspace(ylo, 1.0, 6))

    def px(far, y):
        lx = np.log10(np.clip(far, 10**xlo, 1.0))
        fy = (np.log10(np.clip(y, 10**ylo, 1.0)) - ylo) / -ylo if det else (y - ylo) / (1 - ylo)
        fy = min(1.0, max(0.0, fy))  # จุดที่ต่ำกว่าช่วงแกน (FAR เล็กกว่าที่วัดได้) วาดที่ขอบ ไม่หลุดกรอบ
        return int(m + (lx - xlo) / -xlo * (w - 2 * m)), int(h - m - fy * (h - 2 * m))

    for e in range(int(xlo), 1):
        x, _ = px(10.0**e, ys[-1])
        cv2.line(img, (x, m), (x, h - m), grid, 1)
        cv2.putText(img, f"1e{e}", (x - 18, h - m + 25), font, 0.5, ink, 1)
    for v in ys:
        _, y = px(1.0, v)
        cv2.line(img, (m, y), (w - m, y), grid, 1)
        label = f"1e{int(round(np.log10(v)))}" if det else f"{v:.2f}"
        cv2.putText(img, label, (m - 60, y + 5), font, 0.5, ink, 1)
    ycol = c.frr if det else c.tar
    pts = np.array([px(f, v) for f, v in zip(c.far, ycol, strict=True)], np.int32)
    cv2.polylines(img, [pts], False, (180, 60, 40), 2, cv2.LINE_AA)
    cv2.rectangle(img, (m, m), (w - m, h - m), ink, 1)
    cv2.putText(img, "FAR (log)", (w // 2 - 40, h - 30), font, 0.6, ink, 1)
    cv2.putText(img, "FRR (log)" if det else "TAR", (10, m - 15), font, 0.6, ink, 1)
    cv2.putText(img, title, (m, 45), font, 0.7, ink, 2)
    cv2.imwrite(str(path), img)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.vision.evaluate")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default="", help="ชื่อชุดข้อมูลในรายงาน เช่น LFW")
    ap.add_argument("--plot-title", default="face matching", help="ชื่อบนกราฟ (ASCII เท่านั้น)")
    ap.add_argument("--config", type=Path, help="ไฟล์ค่าตั้งใบหน้า (threshold ที่จะรายงาน FAR/FRR)")
    ap.add_argument("--max-genuine", type=int, default=20000)
    ap.add_argument("--max-impostor", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit-people", type=int, default=0, help="ใช้แค่ N คนแรก (ทดลองเร็ว ๆ)")
    ap.add_argument("--pairs", type=Path, help="pairs.txt ของ LFW → ใช้วิธีมาตรฐาน 6,000 คู่ 10 fold")
    a = ap.parse_args(argv)
    # คอนโซลวินโดวส์ภาษาไทยใช้ cp874 ที่ไม่มีบางตัวอักษร (เช่น ·) → พิมพ์เป็น UTF-8 แทนการล่มตอนท้าย
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    import cv2

    cfg = config.load(a.config)
    if a.pairs:
        det, emb = models.Detector(cfg.min_detect_score), models.Embedder()
        res = {"dataset": a.name or a.folder.name, "commit": git_commit(),
               "date": datetime.now().astimezone().isoformat(timespec="seconds"),
               "machine": machine_text(cv2),
               "models_sha256": {m.name: m.sha256 for m in (models.YUNET, models.SFACE)},
               **run_pairs(a, cfg, det, emb)}  # fmt: skip
        text = json.dumps(res, ensure_ascii=False, indent=2)
        (a.out / "metrics.json").write_text(text, encoding="utf-8")
        print(text)
        return 0
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
    with gzip.open(a.out / "scores.csv.gz", "wt", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["label", "score", "a", "b"])
        for lab, pairs, sc in (("genuine", genuine, g_scores), ("impostor", impostor, i_scores)):
            for (i, j), s in zip(pairs, sc, strict=True):
                wr.writerow([lab, f"{s:.6f}", files[i], files[j]])
    result = {
        "dataset": a.name or a.folder.name,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "machine": machine_text(cv2),
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
    title = f"{a.plot_title}  EER={eer_rate * 100:.2f}%  ({len(genuine)} gen / {len(impostor)} imp)"
    plot(c, a.out / "roc.png", "ROC  " + title, det=False)
    plot(c, a.out / "det.png", "DET  " + title, det=True)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
