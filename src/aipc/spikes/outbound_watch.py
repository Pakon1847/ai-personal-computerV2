"""T6 แบบใหม่: บันทึกการเชื่อมต่อขาออกระหว่างใช้งาน แล้วเทียบกับบันทึกส่งออก (outbound.json) ของผู้ใช้.

เกณฑ์: docs/reviews/2026-10-05-claims-hybrid.md หัวข้อ 4 (ประกาศก่อนวัด) · audit 2026-09-30 gaps-1

    sudo python -m aipc.spikes.outbound_watch record --seconds 1800 --out watch.jsonl
    python -m aipc.spikes.outbound_watch check watch.jsonl --ledger outbound.json
        --canary CANARY-7Q4X

record ต้องรันด้วย root (ss เห็นชื่อโปรเซสของทุกผู้ใช้) · อ่านอย่างเดียว ไม่แตะอะไรในเครื่อง
ตัดสินจากชื่อโปรเซส: โปรแกรมของเรา (python / llama-server) ออกได้เฉพาะ Open-Meteo ·
claude = Anthropic (รายงานทุกปลายทาง)
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

OPEN_METEO = ("api.open-meteo.com", "geocoding-api.open-meteo.com")
OURS = {"python", "python3", "llama-server", "whisper-cli"}  # โปรเซสของแอป (หน้าจอ · AI · ถอดเสียง)
# เบราว์เซอร์ของผู้ช่วย: รายงานปลายทางแยก ไม่ใช่เกณฑ์ข้อ 1 (เว็บที่ผู้ใช้เปิดเอง · THREAT_MODEL ทางที่ 5–6)
BROWSER = {"chromium", "chrome"}
CLAUDE = {"claude"}
_PROC = re.compile(r'\("([^"]+)",pid=(\d+)')


def _host(addr: str) -> str:
    """'172.20.10.2:22' / '[2001:db8::1]:443' → ส่วนที่อยู่ (ไม่มีพอร์ต)."""
    return addr.rsplit(":", 1)[0].strip("[]")


def parse_ss(text: str) -> list[dict]:
    """ผลของ `ss -tunpH state established` → [{proto, local, peer, procs: [ชื่อ, ...]}]."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] not in ("tcp", "udp"):
            continue
        procs = sorted({m.group(1) for m in _PROC.finditer(line)})
        rows.append({"proto": parts[0], "local": parts[3], "peer": parts[4], "procs": procs})
    return rows


def external(row: dict) -> bool:
    peer = _host(row["peer"])
    return not (
        peer.startswith("127.") or peer in ("::1", "localhost") or peer.startswith("::ffff:127.")
    )


def resolve(hosts=OPEN_METEO, lookup=socket.getaddrinfo) -> dict[str, list[str]]:
    out = {}
    for h in hosts:
        try:
            out[h] = sorted({ai[4][0] for ai in lookup(h, 443)})
        except OSError:
            out[h] = []
    return out


def record(
    seconds: float, interval: float, out: Path, run=None, clock=time.time, sleep=time.sleep
) -> int:
    """สุ่ม ss ทุก interval วิ นาน seconds วิ → JSONL (บรรทัดแรก = ข้อมูลการวัด) · คืนจำนวนแถวที่ออกนอกเครื่อง."""
    run = run or (
        lambda: (
            subprocess.run(
                ["ss", "-tunpH", "state", "established"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        )
    )
    n = 0
    end = clock() + seconds
    with out.open("w", encoding="utf-8") as f:
        head = {
            "meta": {
                "start": datetime.now().isoformat(timespec="seconds"),
                "interval_s": interval,
                "open_meteo_ips": resolve(),
            }
        }
        f.write(json.dumps(head, ensure_ascii=False) + "\n")
        while clock() < end:
            t = clock()
            for row in parse_ss(run()):
                if external(row):
                    f.write(json.dumps({"t": round(t, 1), **row}, ensure_ascii=False) + "\n")
                    n += 1
            f.flush()
            sleep(interval)
    return n


def check(rows: list[dict], meta: dict, ledger: list[dict], canary: str = "") -> dict:
    """เทียบตามเกณฑ์ T6 แบบใหม่ · คืนผลรายข้อ + รายการปลายทางทั้งหมด."""
    meteo = {ip for ips in meta.get("open_meteo_ips", {}).values() for ip in ips}
    by_proc: dict[str, set[str]] = {}
    bad = []
    for r in rows:
        names = r["procs"] or ["(ไม่รู้ชื่อ · ระบบ)"]
        for name in names:
            by_proc.setdefault(name, set()).add(r["peer"])
        if set(r["procs"]) & OURS and _host(r["peer"]) not in meteo:
            bad.append(r)
    claude_seen = any(set(r["procs"]) & CLAUDE for r in rows)
    kinds = [e.get("kind") for e in ledger]
    sent = [str(e.get("sent", "")) for e in ledger]
    res = {
        "1_ours_only_to_declared": not bad,
        "2_claude_has_ledger": (not claude_seen) or any(k in ("ask", "skill") for k in kinds),
        "3_canary_not_sent": bool(canary) and not any(canary in s for s in sent),
        "claude_connected": claude_seen,
        "browser_destinations": sorted({r["peer"] for r in rows if set(r["procs"]) & BROWSER}),
        "ledger_kinds": {k: kinds.count(k) for k in sorted(set(kinds))},
        "undeclared": bad[:20],
        "destinations": {k: sorted(v) for k, v in sorted(by_proc.items())},
    }
    return res


def load_watch(path: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    meta = lines[0].get("meta", {}) if lines else {}
    return meta, [x for x in lines[1:] if "peer" in x]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aipc.spikes.outbound_watch")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--seconds", type=float, default=1800)
    r.add_argument("--interval", type=float, default=2)
    r.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("check")
    c.add_argument("watch", type=Path)
    c.add_argument("--ledger", type=Path, required=True)
    c.add_argument("--canary", default="")
    a = p.parse_args(argv)
    if a.cmd == "record":
        print(record(a.seconds, a.interval, a.out), "แถวที่ออกนอกเครื่อง", file=sys.stderr)
        return 0
    meta, rows = load_watch(a.watch)
    from aipc.cloud.ledger import Ledger

    ledger = Ledger(a.ledger).entries()  # รูปแบบไฟล์เดียวกับที่แอปเขียน
    res = check(rows, meta, ledger, a.canary)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if all(res[k] for k in res if k[0].isdigit()) else 1


if __name__ == "__main__":
    sys.exit(main())
