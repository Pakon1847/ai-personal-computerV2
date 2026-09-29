"""กราฟสรุป "ใครเขียนสกิล .md ได้" จากผลของ aipc.spikes.skill_author (route-*.json).

    python docs/benchmarks/2026-09-30-skill-author/charts.py <โฟลเดอร์ที่มี route-*.json>

ใช้ matplotlib (ไม่ได้อยู่ใน constraints ของแอป · ติดตั้งแยกบนเครื่องที่ทำกราฟ) · ฟอนต์ IBM Plex Sans Thai ที่มากับแอป ·
สีผู้เขียนคงที่ตามลำดับ (ผ่านตัวตรวจสี dataviz: CVD ΔE ≥ 9.1) · ทุกแท่งมีตัวเลขกำกับ ไม่พึ่งสีอย่างเดียว
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FONTS = REPO / "src" / "aipc" / "ui" / "fonts"
ORDER = ["claude", "typhoon25-4b", "qwen3-4b-2507", "gemma4-e2b", "qwen3-0.6b"]
NAMES = {
    "claude": "Claude (claude -p)",
    "typhoon25-4b": "Typhoon2.5 4B",
    "qwen3-4b-2507": "Qwen3 4B 2507",
    "gemma4-e2b": "Gemma 4 E2B",
    "qwen3-0.6b": "Qwen3 0.6B",
}
COLORS = {
    "claude": "#2a78d6",
    "typhoon25-4b": "#eb6834",
    "qwen3-4b-2507": "#1baf7a",
    "gemma4-e2b": "#eda100",
    "qwen3-0.6b": "#e87ba4",
}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def setup_font() -> None:
    for f in FONTS.glob("IBMPlexSansThai-*.ttf"):
        font_manager.fontManager.addfont(str(f))
    plt.rcParams.update({
        "font.family": "IBM Plex Sans Thai", "font.size": 11, "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    })  # fmt: skip


def load(folder: Path) -> dict:
    """รวมผู้เขียนจาก route-*.json ทุกไฟล์ · ผู้เขียนซ้ำ = ใช้ไฟล์หลังสุด."""
    authors = {}
    for f in sorted(folder.glob("route-*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        authors.update(data["authors"])
        crit = data["criteria"]
    return {"authors": authors, "criteria": crit}


def bars(ax, labels, values, colors, *, title, fmt, limit=None, target=None, better="high"):
    y = range(len(labels))
    ax.barh(y, values, color=colors, height=0.56, edgecolor=SURFACE, linewidth=2)
    ax.set_yticks(list(y), labels)
    ax.invert_yaxis()
    if target is not None:
        title += f" · เกณฑ์ {'≥' if better == 'high' else '≤'} {fmt(target)}"
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    top = limit or max(values) * 1.18 or 1
    ax.set_xlim(0, top)
    for i, v in enumerate(values):
        ax.text(v + top * 0.015, i, fmt(v), va="center", fontsize=10, color=INK, zorder=3,
                bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5})
    if target is not None:
        ax.axvline(target, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, zorder=2)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else HERE
    setup_font()
    d = load(folder)
    crit, A = d["criteria"], d["authors"]
    keys = [k for k in ORDER if k in A] + [k for k in A if k not in ORDER]
    labels = [NAMES.get(k, k) for k in keys]
    colors = [COLORS.get(k, "#8a8984") for k in keys]

    def pct(v):
        return f"{v:.0%}"

    rows = [
        ("ผ่านตัวตรวจไฟล์สกิล", [A[k]["author"]["valid"] / A[k]["author"]["n"] for k in keys],
         crit["valid_min"], "high"),
        ("ขั้นตอน/ชนิดสกิลถูกตามคำขอ", [A[k]["author"]["structure"] / A[k]["author"]["n"] for k in keys],
         crit["structure_min"], "high"),
        ("ควรเรียก และเรียกถูก",
         [A[k]["route"]["should_hit"] / A[k]["route"]["should_total"] for k in keys],
         crit["should_hit_min"], "high"),
        ("ไม่ควรเรียก แต่เรียกผิด",
         [A[k]["route"]["should_not_false"] / A[k]["route"]["should_not_total"] for k in keys],
         crit["should_not_false_max"], "low"),
    ]  # fmt: skip
    fig, axes = plt.subplots(2, 2, figsize=(12, 3.2 + 0.9 * len(keys)))
    for ax, (title, vals, target, better) in zip(axes.flat, rows, strict=True):
        bars(ax, labels, vals, colors, title=title, fmt=pct, limit=1.12, target=target,
             better=better)  # fmt: skip
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    fig.suptitle("ใครเขียนสกิล .md ให้ AI ในเครื่องได้ · คำขอ 10 ข้อ · ตัดสินด้วยตัวเลือกสกิลของแอปบน Pi 5",
                 x=0.01, ha="left", fontsize=14, color=INK)  # fmt: skip
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(folder / "quality.png", dpi=150)

    fig, ax = plt.subplots(figsize=(9, 1.4 + 0.6 * len(keys)))
    secs = [A[k]["author"]["seconds_median"] for k in keys]
    bars(ax, labels, secs, colors, title="เวลาเขียน 1 สกิล (มัธยฐาน · รวมรอบแก้) · วินาที",
         fmt=lambda v: f"{v:,.0f} วิ" if v < 120 else f"{v:,.0f} วิ ({v / 60:.1f} นาที)")  # fmt: skip
    fig.tight_layout()
    fig.savefig(folder / "time.png", dpi=150)
    print("บันทึก quality.png และ time.png ใน", folder)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
