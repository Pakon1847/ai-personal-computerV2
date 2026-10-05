"""รันงานซ้ำตามกติกาการวัดของ BRIEF หัวข้อ 9 แล้วเขียนผลลง docs/benchmarks/.

กติกาที่ไฟล์นี้บังคับด้วยโค้ด (ไม่ใช่แค่เขียนไว้ในเอกสาร):
1. warm-up อย่างน้อย 1 รอบ และไม่นับรอบนั้น — รอบแรกมักช้าเพราะต้องโหลดไฟล์เข้า cache
2. วัดจริงอย่างน้อย 5 รอบ — น้อยกว่านี้ median กับ p95 ไม่มีความหมาย
3. เก็บอุณหภูมิและ get_throttled ทุกรอบ — ถ้าเครื่องร้อนเกินหรือไฟตกระหว่างวัด
   ผลชุดนั้นถูกติดป้าย "ใช้ไม่ได้" ไม่ใช่ถูกลบทิ้งเงียบ ๆ
4. เก็บค่าดิบทุกรอบเป็น CSV — คนอื่นคำนวณ median ซ้ำเองได้
5. บอกชัดว่าผลนี้เป็นหลักฐานระดับ 4 ได้ไหม (ได้เฉพาะวัดบน Pi 5)
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from aipc.bench import machine
from aipc.bench.stats import Summary, summarize

MIN_WARMUP = 1
MIN_RUNS = 5

# บิต 0–3 ของ get_throttled = ปัญหาที่ "กำลังเกิดตอนนี้"
# บิต 16–19 = "เคยเกิดตั้งแต่บูต" ซึ่งติดค้างจนรีบูต
NOW_MASK = 0x0000F
SINCE_BOOT_MASK = 0xF0000


@dataclass
class RunRecord:
    index: int
    phase: str  # "warmup" หรือ "measured"
    seconds: float
    temp_before_c: float | None
    temp_after_c: float | None
    throttled_after: int | None
    # ค่าที่งานรายงานเอง นอกจากเวลา เช่น tok/s ของ llama-bench · งานที่ไม่รายงานอะไรก็ว่างไว้
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class Sampler:
    """ตัวอ่านสภาพเครื่องระหว่างวัด · แยกออกมาเพื่อให้เทสต์ใส่ค่าปลอมได้."""

    temp: Callable[[], float | None] = machine.cpu_temp_c
    throttled: Callable[[], int | None] = machine.throttled_raw
    clock: Callable[[], float] = time.perf_counter


def throttled_during(before: int | None, after: int | None) -> bool:
    """ระหว่างวัดมีการไฟตก/ร้อนเกินเกิดขึ้นไหม.

    ดูสองอย่าง: บิต "ตอนนี้" ติดอยู่หลังรอบนั้น หรือบิต "เคยเกิด" เพิ่งติดขึ้นใหม่
    (ถ้าบิต "เคยเกิด" ติดมาก่อนเริ่มวัดแล้ว แปลว่าเกิดก่อนหน้า ไม่ใช่ระหว่างวัด)
    อ่านค่าไม่ได้ (เช่นบนวินโดวส์) → False เพราะไม่มีหลักฐานว่าเกิด
    แต่รายงานจะเขียนแยกว่า "ตรวจไม่ได้" ไม่ใช่ "ไม่มีปัญหา"
    """
    if after is None:
        return False
    if after & NOW_MASK:
        return True
    old = before or 0
    return bool(after & SINCE_BOOT_MASK & ~old)


Task = Callable[[], "dict[str, float] | None"]


def measure(
    task: Task,
    *,
    warmup: int = MIN_WARMUP,
    runs: int = MIN_RUNS,
    sampler: Sampler | None = None,
) -> list[RunRecord]:
    if warmup < MIN_WARMUP:
        raise ValueError(f"BRIEF หัวข้อ 9: warm-up อย่างน้อย {MIN_WARMUP} รอบ")
    if runs < MIN_RUNS:
        raise ValueError(f"BRIEF หัวข้อ 9: วัดจริงอย่างน้อย {MIN_RUNS} รอบ")
    s = sampler or Sampler()
    records: list[RunRecord] = []
    for i in range(warmup + runs):
        temp_before = s.temp()
        start = s.clock()
        metrics = task() or {}
        elapsed = s.clock() - start
        records.append(
            RunRecord(
                index=i,
                phase="warmup" if i < warmup else "measured",
                seconds=elapsed,
                temp_before_c=temp_before,
                temp_after_c=s.temp(),
                throttled_after=s.throttled(),
                metrics=dict(metrics),
            )
        )
    return records


def command_task(args: list[str], parse: Callable[[str], dict[str, float]] | None = None) -> Task:
    """ทำให้คำสั่งภายนอก (เช่น llama-bench) กลายเป็นงานที่ measure() จับเวลาได้.

    parse = ฟังก์ชันแปลงข้อความที่โปรแกรมพิมพ์ออกมาเป็นตัวเลข (เช่น tok/s)
    ไม่ใส่ = วัดแค่เวลา และทิ้งข้อความที่พิมพ์ออกมา
    คำสั่งล้ม → หยุดทั้งชุด เพราะเวลาของคำสั่งที่ล้มไม่ใช่เวลาของงานที่ตั้งใจวัด
    """

    def task() -> dict[str, float] | None:
        if parse is None:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
            return None
        done = subprocess.run(args, check=True, capture_output=True, text=True)
        return parse(done.stdout)

    return task


def sha256_file(path: Path) -> str:
    """ลายนิ้วมือของไฟล์ (เช่น ไฟล์โมเดล) · ชื่อไฟล์เหมือนกันแต่เนื้อต่างกันจะได้ค่าต่างกัน."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Verdict:
    """สรุปว่าผลชุดนี้เชื่อได้แค่ไหน · อยู่หัวรายงานเสมอ."""

    evidence_level4: bool
    throttled_runs: list[int]
    throttle_unknown: bool
    warnings: list[str]


def judge(info: machine.MachineInfo, records: list[RunRecord], before: int | None) -> Verdict:
    warnings: list[str] = []
    level4 = info.board_class == "pi5"
    if not level4:
        warnings.append(
            f"วัดบน {info.board_model or info.os} ไม่ใช่ Pi 5 — "
            "ใช้เป็นหลักฐานระดับ 4 ไม่ได้ และตัวเลขความเร็ว/RAM ห้ามเข้าบทที่ 4"
        )
    bad = [r.index for r in records if throttled_during(before, r.throttled_after)]
    if bad:
        warnings.append(f"ไฟตกหรือร้อนเกินระหว่างรอบ {bad} — ผลชุดนี้ใช้ไม่ได้ ต้องวัดใหม่")
    # บิต "เคยเกิด" ติดมาก่อนวัด = throttle ที่เกิดแล้วหายระหว่างรอบตรวจไม่ได้ (audit 2026-09-30 evidence-1)
    sticky = before is not None and bool(before & SINCE_BOOT_MASK)
    if sticky:
        warnings.append(
            f"get_throttled ก่อนวัด = {before:#x} (เคยลดความเร็วตั้งแต่บูต) — ตรวจไม่ได้ว่าเกิดซ้ำระหว่างวัดไหม · "
            "ไม่นับเป็นระดับ 4 · รีบูตแล้ววัดใหม่"
        )
    unknown = all(r.throttled_after is None for r in records)
    if unknown:
        warnings.append("อ่าน get_throttled ไม่ได้ — ไม่รู้ว่าเครื่องถูกลดความเร็วไหม")
    if info.git_dirty:
        warnings.append("มีไฟล์ที่ยังไม่ commit ตอนวัด — ผลนี้ไม่ได้ผูกกับ commit ใดจริง")
    if info.git_commit is None:
        warnings.append("ไม่รู้ commit ที่วัด")
    return Verdict(
        evidence_level4=level4 and not bad and not sticky and not unknown and info.git_dirty is False,
        throttled_runs=bad,
        throttle_unknown=unknown,
        warnings=warnings,
    )


def write_report(
    out_dir: Path,
    name: str,
    info: machine.MachineInfo,
    records: list[RunRecord],
    throttled_before: int | None,
    meta: dict[str, str],
    files: dict[str, str],
    command: list[str] | None = None,
) -> dict[str, Path]:
    """เขียนสามไฟล์: <name>.csv (ค่าดิบ), <name>.json (ทุกอย่างแบบเครื่องอ่าน), <name>.md (สรุปให้คนอ่าน).

    ไม่เขียนทับไฟล์เดิม — ผลเก่าคือหลักฐาน ถ้าชื่อซ้ำให้ตั้งชื่อใหม่
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {ext: out_dir / f"{name}.{ext}" for ext in ("csv", "json", "md")}
    for p in paths.values():
        if p.exists():
            raise FileExistsError(f"{p} มีอยู่แล้ว — ผลเก่าคือหลักฐาน ห้ามเขียนทับ")

    measured = [r for r in records if r.phase == "measured"]
    summary = summarize([r.seconds for r in measured])
    metric_names = sorted({k for r in measured for k in r.metrics})
    metric_summaries = {
        k: summarize([r.metrics[k] for r in measured if k in r.metrics]) for k in metric_names
    }
    verdict = judge(info, records, throttled_before)

    # CSV แบนเป็นคอลัมน์เดียวต่อค่า เปิดด้วย Excel/LibreOffice ได้ตรง ๆ
    with paths["csv"].open("w", newline="", encoding="utf-8") as f:
        base = [k for k in asdict(records[0]) if k != "metrics"]
        all_metrics = sorted({k for r in records for k in r.metrics})  # รวม warm-up ด้วย
        writer = csv.DictWriter(f, fieldnames=base + all_metrics)
        writer.writeheader()
        for r in records:
            row = {k: v for k, v in asdict(r).items() if k != "metrics"}
            row.update(r.metrics)
            writer.writerow(row)

    payload = {
        "name": name,
        "command": command,
        "meta": meta,
        "files_sha256": files,
        "machine": info.to_dict(),
        "throttled_before": throttled_before,
        "summary_seconds": asdict(summary),
        "summary_metrics": {k: asdict(v) for k, v in metric_summaries.items()},
        "verdict": asdict(verdict),
    }
    paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["md"].write_text(
        render_markdown(name, info, summary, verdict, meta, files, command, metric_summaries),
        encoding="utf-8",
    )
    return paths


def render_markdown(
    name: str,
    info: machine.MachineInfo,
    summary: Summary,
    verdict: Verdict,
    meta: dict[str, str],
    files: dict[str, str],
    command: list[str] | None,
    metric_summaries: dict[str, Summary] | None = None,
) -> str:
    lines = [f"# {name}", ""]
    if verdict.evidence_level4:
        lines.append("**ใช้เป็นหลักฐานระดับ 4 ได้** (Pi 5, ไม่ throttle, ผูกกับ commit)")
    else:
        lines.append("**ยังใช้เป็นหลักฐานระดับ 4 ไม่ได้**")
    lines += [""] + [f"- คำเตือน: {w}" for w in verdict.warnings] + [""]
    lines += [
        "## ผล (วินาที ไม่รวม warm-up)",
        "",
        "| n | median | p95 | min | max |",
        "|---|---|---|---|---|",
        f"| {summary.n} | {summary.median:.4f} | {summary.p95:.4f} "
        f"| {summary.minimum:.4f} | {summary.maximum:.4f} |",
        "",
        f"p95 คำนวณแบบ nearest-rank · เมื่อ n = {summary.n} p95 คือลำดับที่ "
        f"{-(-95 * summary.n // 100)} จาก {summary.n} ของค่าที่เรียงแล้ว",
        "",
    ]
    if metric_summaries:
        lines += [
            "## ค่าที่โปรแกรมรายงาน (ไม่รวม warm-up)",
            "",
            "| ค่า | n | median | p95 | min | max |",
            "|---|---|---|---|---|---|",
        ]
        for k, m in metric_summaries.items():
            nums = (m.median, m.p95, m.minimum, m.maximum)
            lines.append(f"| {k} | {m.n} | " + " | ".join(f"{x:.4g}" for x in nums) + " |")
        lines += [
            "",
            'ค่าที่ "ยิ่งสูงยิ่งดี" (เช่น tok/s) ให้ดู min แทน p95 — p95 ของ tok/s คือรอบที่เร็ว ไม่ใช่รอบที่แย่',
            "",
        ]
    lines += [
        "## เครื่อง",
        "",
        f"- บอร์ด: {info.board_model or '—'} ({info.board_class})",
        f"- RAM: {info.ram_total_mb or '—'} MB",
        f"- OS: {info.os} · kernel {info.kernel} · Python {info.python}",
        f"- commit: {info.git_commit or '—'} (มีไฟล์ค้างแก้: {info.git_dirty})",
        f"- อุณหภูมิตอนเริ่ม: {info.cpu_temp_c if info.cpu_temp_c is not None else '—'} °C",
        "",
    ]
    if command:
        lines += ["## คำสั่งที่วัด", "", "```", " ".join(command), "```", ""]
    if meta:
        lines += ["## ค่าที่ตั้ง", ""] + [f"- {k}: {v}" for k, v in meta.items()] + [""]
    if files:
        lines += ["## ไฟล์ที่ใช้ (sha256)", ""] + [f"- `{k}` {v}" for k, v in files.items()] + [""]
    lines += ["## หมายเหตุของผู้วัด", "", "(เขียนเพิ่มเองด้วยมือ: ไฟ, cooler, รุ่น SD/SSD, สิ่งที่เห็นผิดปกติ)", ""]
    return "\n".join(lines)
