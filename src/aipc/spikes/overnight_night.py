"""ตัวรันงานข้ามคืนแบบไม่มีหน้าจอ (การ์ด 0081 · วัด J1 J6 J7 บน Pi 5 กับ AI จริง).

    python -m aipc.spikes.overnight_night --folder <โฟลเดอร์เอกสาร> --out <โฟลเดอร์ผล>

ใช้ `Plan` `Job` `Runner` `LocalAi` ตัวเดียวกับแอป · ต่างจากแอปแค่ไม่มีหน้าจอ:
- ไม่มีแชทแทรก (J3 วัดแยกที่จอ) · ไม่มีปุ่ม "ทำต่อ" → รันซ้ำคำสั่งเดิม = ทำต่อจากงานที่ค้าง (find_open)
- ได้ SIGTERM (เช่น มีคนเข้าระบบที่จอ) → pause() → job.json เป็น "paused" ทำต่อได้

ไฟล์ผลใน --out:
- events.csv  ทุกครั้งที่สถานะเปลี่ยน/จบ 1 ชิ้น: เวลา · สถานะ · หมายเหตุ · ก้อนที่ทำแล้ว · ก้อนทั้งหมด · °C
- result.json สรุปตรวจ J1 (ทุกไฟล์ done · ก้อนสรุปครบเท่าจำนวนก้อน ไม่ขาดไม่เกิน · ไม่มีก้อนว่าง) + เวลา + พัก
- summaries/  ไฟล์สรุปที่งานเขียนออก (ทางเดียวกับแอป)
"""

from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from aipc.bench.machine import cpu_temp_c
from aipc.jobs import overnight


def check_j1(data: dict) -> dict:
    """J1: ทำครบทุกไฟล์ · ก้อนไม่ซ้ำไม่หาย = จำนวนสรุปก้อน == จำนวนก้อน และไม่มีก้อนว่าง."""
    files = []
    for f in data["files"]:
        level0 = f["levels"][0] if f["levels"] else []
        files.append({
            "name": f["name"], "state": f["state"], "chunks": f["chunks"],
            "summaries": len(level0), "empty": sum(1 for t in level0 if not t.strip()),
            "failed": f["failed"], "note": f["note"],
        })  # fmt: skip
    ok = [x for x in files if x["state"] == "done" and x["summaries"] == x["chunks"]]
    ok = [x for x in ok if not x["empty"]]
    return {"files": files, "complete": len(ok), "total": len(files),
            "overall_done": data["overall"]["state"] == "done"}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default="ทดสอบข้ามคืน")
    args = ap.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    root = out / "jobs"  # สถานะงานแยกจากของผู้ใช้จริง (~/.local/share/aipc/jobs)
    summaries = out / "summaries"

    job = overnight.find_open(root, summaries)
    if job is None or job.data["state"] == "done":
        plan = overnight.plan_folder(args.folder)
        if plan.problem:
            print(f"แผนไม่ผ่าน: {plan.problem}", file=sys.stderr)
            return 2
        job = overnight.Job.create(root, args.name, plan, summaries)
        n_files, n_skip = len(plan.files), len(plan.skipped)
        print(f"งานใหม่ {job.data['id']} · {n_files} ไฟล์ · {plan.chunks} ก้อน · ข้าม {n_skip}")
    else:
        print(f"ทำต่อจากงาน {job.data['id']} · {job.counts()}")

    events = out / "events.csv"
    new = not events.exists()
    fh = events.open("a", encoding="utf-8", newline="")
    writer = csv.writer(fh)
    if new:
        writer.writerow(["time", "status", "note", "done", "total", "temp_c"])

    runner = None

    def on_change():
        done, total = job.counts()
        writer.writerow([datetime.now().isoformat(timespec="seconds"), runner.status, runner.note,
                         done, total, cpu_temp_c()])  # fmt: skip
        fh.flush()

    runner = overnight.Runner(job, overnight.LocalAi(), temp=cpu_temp_c, on_change=on_change)

    def stop(_sig, _frame):
        runner.pause()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    t0 = time.monotonic()
    started = datetime.now().isoformat(timespec="seconds")
    job.data["state"] = "running"
    job.save()
    runner.run()  # เธรดหลัก · จบเมื่อ done หรือ pause
    on_change()
    fh.close()

    result = {"started": started, "ended": datetime.now().isoformat(timespec="seconds"),
              "seconds": round(time.monotonic() - t0), "job_id": job.data["id"],
              "state": job.data["state"], "status": runner.status, "note": runner.note,
              "retries": job.data["retries"], "rest_seconds": job.data["rest_seconds"],
              "skipped": job.data["skipped"], "result_file": job.data["result"],
              "j1": check_j1(job.data)}  # fmt: skip
    # รันหลายช่วง (ถูกหยุดแล้วทำต่อ) → เก็บทุกช่วง ไม่เขียนทับ
    path = out / "result.json"
    runs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    runs.append(result)
    path.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("state", "status", "seconds")}, ensure_ascii=False))
    print(f"J1 {result['j1']['complete']}/{result['j1']['total']}")
    return 0 if job.data["state"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
