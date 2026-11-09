"""วัด R1 H3 ของการ์ด 0080 รอบ 2 กับเซิร์ฟเวอร์จริง · ที่อยู่อ่านจาก AIPC_SHARE_URL (ไม่เขียนลงผล).

เซิร์ฟเวอร์จำกัด 10 ครั้ง/ชั่วโมง/IP ต่อชนิด (นับตามชั่วโมง UTC) สกิล 20 ตัวจึงต้องแบ่งส่งข้ามชั่วโมง
"""

import argparse
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from aipc.chat.memory import secret_reason
from aipc.skills import share

ROOT = Path(__file__).resolve().parents[3]
N_SKILLS = 20
N_GUESSES = 10_000
GAP_S = 2.0  # KV เขียนคีย์เดียวกันได้ไม่เกิน 1 ครั้ง/วินาที
THREADS = 4


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def picks() -> list[dict]:
    """สกิลดีตัวแรก ๆ ของชุดวัด 0074 ที่ส่งได้ (ไม่มีคำต้องห้าม · ไม่เกินขนาด)."""
    items = []
    for path in sorted((ROOT / "tests/data").glob("skill_guard_*s1.json")):
        items += json.loads(path.read_text(encoding="utf-8"))["items"]
    good = [i for i in items if i["label"] == "good"]
    ok = [
        i
        for i in good
        if not secret_reason(i["md"]) and len(i["md"].encode("utf-8")) <= share.MAX_UPLOAD
    ]
    return ok[:N_SKILLS]


def wait_next_hour() -> None:
    target = (int(time.time()) // 3600 + 1) * 3600 + 15
    while time.time() < target:
        time.sleep(min(30.0, max(0.1, target - time.time())))


def put(url: str, item: dict, row: dict) -> None:
    try:
        row["code"] = share.upload(item["md"], url)
    except share.ShareError as e:
        row["put_error"] = str(e)
    time.sleep(GAP_S)


def get(url: str, item: dict, row: dict) -> None:
    if "code" in row:
        try:
            row["exact"] = share.download(row["code"], url) == item["md"]
        except share.ShareError as e:
            row["exact"], row["get_error"] = False, str(e)
    time.sleep(GAP_S)


def guess(url: str, code: str, deadline: float) -> tuple[int, bool]:
    """(สถานะ HTTP, ตอบ JSON ของ Worker เองไหม) · 0 = ต่อไม่ได้ · -1 = หมดเวลาจึงไม่ได้ลอง."""
    if time.time() > deadline:
        return -1, False
    try:
        request = urllib.request.Request(
            f"{url}/v1/skills/{code}", headers={"User-Agent": share.USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=15) as reply:
            reply.read(share.MAX_UPLOAD + 1)
            return reply.status, True
    except urllib.error.HTTPError as e:
        return e.code, b"error" in e.read(200)
    except OSError:
        return 0, False


def h3(url: str, real: str) -> dict:
    guesses = [f"{secrets.randbelow(10**8):08d}" for _ in range(N_GUESSES)]
    spots = [N_GUESSES // 2, N_GUESSES - 1]  # แทรกเลขที่มีอยู่จริง: ถ้าไม่ถูกบล็อกจะเจอแน่
    for i in spots:
        guesses[i] = real
    hour_end = (int(time.time()) // 3600 + 1) * 3600 - 90  # จบก่อนเปลี่ยนชั่วโมง ไม่ให้กินโควตาของรอบถัดไป
    start = time.time()
    with ThreadPoolExecutor(THREADS) as pool:
        results = list(pool.map(lambda c: guess(url, c, hour_end), guesses))
    statuses = [s for s, _ in results]
    return {
        "started": datetime.fromtimestamp(start, UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - start, 1),
        "requested": N_GUESSES,
        "statuses": {str(k): v for k, v in sorted(Counter(statuses).items())},
        "found_200": statuses.count(200),
        "worker_json_429": sum(1 for s, own in results if s == 429 and own),
        "first_429_index": statuses.index(429) if 429 in statuses else None,
        "real_code_spots": {str(i): statuses[i] for i in spots},
    }


def run(url: str, out: Path) -> None:
    items = picks()
    rows = [{"id": i["id"]} for i in items]
    state = {"started": now(), "n": len(items), "rows": rows}

    def save() -> None:
        (out / "run.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    out.mkdir(parents=True, exist_ok=True)
    save()
    for k in range(0, 9):  # ชั่วโมงแรก 9 ตัว (ตัวลองเครื่องมือใช้โควตาไปแล้ว 1)
        put(url, items[k], rows[k])
    save()
    state["h3"] = h3(url, next(r["code"] for r in rows if "code" in r))
    save()
    wait_next_hour()
    for k in range(9, 19):
        put(url, items[k], rows[k])
    for k in range(0, 10):
        get(url, items[k], rows[k])
    save()
    wait_next_hour()
    put(url, items[19], rows[19])
    for k in range(10, 20):
        get(url, items[k], rows[k])
    state["finished"] = now()
    state["r1_exact"] = sum(1 for r in rows if r.get("exact") is True)
    save()
    print(
        "r1",
        state["r1_exact"],
        "/",
        len(rows),
        "h3",
        state["h3"]["statuses"],
        state["h3"]["real_code_spots"],
    )


def probe(url: str) -> None:
    """ลองเครื่องมือ 1 รอบ ไม่นับเป็นผล."""
    md = "---\nid: probe\n---\nทดสอบ\n"
    code = share.upload(md, url)
    time.sleep(GAP_S)
    print("probe exact", share.download(code, url) == md)


def expiry(url: str, out: Path) -> None:
    """หลัง 24 ชั่วโมง: เลขเดิมต้องใช้ไม่ได้ · ใช้เลขที่ฝากตัวแรก."""
    state = json.loads((out / "run.json").read_text(encoding="utf-8"))
    code = next(r["code"] for r in state["rows"] if "code" in r)
    try:
        share.download(code, url)
        result = "still_there"
    except share.ShareError as e:
        result = str(e)
    state["expiry"] = {"checked": now(), "result": result}
    (out / "run.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(result)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "run", "expiry"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs/benchmarks/2026-11-09-share-real")
    args = ap.parse_args()
    url = os.environ["AIPC_SHARE_URL"].rstrip("/")
    if args.cmd == "probe":
        probe(url)
    elif args.cmd == "run":
        run(url, args.out)
    else:
        expiry(url, args.out)


if __name__ == "__main__":
    main()
