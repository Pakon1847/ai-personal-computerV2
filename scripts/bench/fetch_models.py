"""โหลดไฟล์โมเดลสำหรับเทียบ LLM (2026-10-29) ลง ~/bench-models · ตรึง revision + ตรวจ sha256 ทุกไฟล์.

    python3 -I fetch_models.py <models.json> <โฟลเดอร์> [label ...]

models.json = รายการจาก Hugging Face API (label · repo · rev · file · sha256) · ไม่ใส่ label = ทุกตัว ·
ไฟล์ที่มีแล้วและ sha256 ตรง = ข้าม · โหลดค้าง = ต่อจากเดิม (curl -C -)
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    rows = json.load(open(sys.argv[1]))
    dest = Path(sys.argv[2]).expanduser()
    only = set(sys.argv[3:])
    dest.mkdir(parents=True, exist_ok=True)
    bad = 0
    for r in rows:
        if only and r["label"] not in only or "repo" not in r:
            continue
        path = dest / r["file"]
        if path.exists() and path.stat().st_size == r["size"] and sha256(path) == r["sha256"]:
            print("HAVE", r["label"], flush=True)
            continue
        url = f"https://huggingface.co/{r['repo']}/resolve/{r['rev']}/{r['file']}"
        print("START", r["label"], flush=True)
        subprocess.run(["curl", "-sSL", "--fail", "--retry", "8", "--retry-delay", "10",
                        "--retry-all-errors", "-C", "-", "-o", str(path), url])  # fmt: skip
        ok = path.exists() and sha256(path) == r["sha256"]
        print("MATCH" if ok else "MISMATCH", r["label"], flush=True)
        bad += not ok
    print(f"ALL-DONE bad={bad}", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
