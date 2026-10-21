"""การ์ด 0046 เกณฑ์ W2–W3: คำสั่งของสกิลประจำเว็บ YouTube กับ Chromium จริง + เว็บจริง · ตรวจผลจากสถานะในหน้า.

รันบน Pi ในเซสชัน Wayland หรือ labwc แบบไม่มีจอ (วิธีเดียวกับ docs/benchmarks/2026-10-13-voice-browser):

    WAYLAND_DISPLAY=wayland-0 python -m aipc.spikes.site_skill_e2e ผล.json [--query คำค้น]

- โปรไฟล์ชั่วคราว (ไม่ล็อกอินบัญชีใคร) · หาคลิปด้วยคำสั่งเดิมของระบบ (ค้นในยูทูบ → เปิดคลิปแรก) ไม่เขียนลิงก์ตายตัว
- W2: ทุกคำสั่งในไฟล์สกิล youtube-voice (ทางเดียวกับแอป: BrowseCommand key/click) ·
  ผ่าน = สถานะในหน้าเปลี่ยนตามที่ควร
  (เวลาวิดีโอ หยุด/เล่น ปิดเสียง ความเร็ว เต็มจอ โหมดโรงหนัง คำบรรยาย มินิเพลเยอร์ คลิปถัดไป ปุ่มไลก์) ·
  คำสั่งที่ไม่มีตัวตรวจ = นับว่าไม่ผ่าน
- W3: คำสั่งเดียวกันขณะหน้าที่เปิดเป็นเว็บอื่น (Wikipedia) ต้องไม่ทำงานเลย (Result.ok = False และหน้าไม่เปลี่ยน)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from aipc.browser.control import BrowserControl
from aipc.skills import manifest
from aipc.skills.browse import BrowseCommand

STATE_JS = r"""((LIKE, DISLIKE) => {
  const v = document.querySelector('video');
  const flexy = document.querySelector('ytd-watch-flexy');
  const cc = document.querySelector('.ytp-subtitles-button');
  const like = document.querySelector(LIKE);
  const dislike = document.querySelector(DISLIKE);
  const player = document.querySelector('#movie_player');
  return {
    t: v ? Math.round(v.currentTime * 10) / 10 : null, paused: v ? v.paused : null,
    dur: v && isFinite(v.duration) ? v.duration : null,
    muted: v ? v.muted : null, rate: v ? v.playbackRate : null,
    fs: !!document.fullscreenElement, theater: flexy ? flexy.hasAttribute('theater') : null,
    mini: !!document.querySelector('ytd-miniplayer[active], ytd-app[miniplayer-is-active]'),
    cc: cc && cc.offsetParent !== null ? cc.getAttribute('aria-pressed') : null,
    like: like ? like.getAttribute('aria-pressed') : null,
    dislike: dislike ? dislike.getAttribute('aria-pressed') : null,
    ad: !!(player && player.classList.contains('ad-showing')),
    url: location.href,
  };
})"""


def _flip(key):
    return lambda a, b: a[key] is not None and b[key] is not None and a[key] != b[key]


LIKE = "ytd-watch-metadata like-button-view-model button"
DISLIKE = "ytd-watch-metadata dislike-button-view-model button"


def _near(frac):
    """เวลาอยู่ที่ราว frac ของความยาวคลิป (±10%) · กดคีย์ตัวเลขของ YouTube."""
    return lambda a, b: bool(b["dur"]) and abs(b["t"] - b["dur"] * frac) <= b["dur"] * 0.1


# ผลที่ควรเห็นต่อคีย์/ปุ่ม (ตามความหมายของคำสั่งในไฟล์) · a = ก่อน · b = หลัง
CHECKS = {
    ("key", "l"): ("เวลาเดินหน้า ≥ 5 วิ", lambda a, b: b["t"] - a["t"] >= 5),
    ("key", "j"): ("เวลาถอยหลัง ≥ 5 วิ", lambda a, b: a["t"] - b["t"] >= 5),
    ("key", "0"): ("กลับต้นคลิป (< 3 วิ)", lambda a, b: b["t"] is not None and b["t"] < 3),
    ("key", "k"): ("หยุด/เล่นสลับ", _flip("paused")),
    ("key", "m"): ("ปิด/เปิดเสียงสลับ", _flip("muted")),
    ("key", ">"): ("เร็วขึ้น", lambda a, b: b["rate"] > a["rate"]),
    ("key", "<"): ("ช้าลง", lambda a, b: b["rate"] < a["rate"]),
    ("key", "t"): ("โหมดโรงหนังสลับ", _flip("theater")),
    ("key", "c"): ("คำบรรยายสลับ", _flip("cc")),
    ("key", "f"): ("เต็มจอ", lambda a, b: b["fs"] is True),
    ("key", "Escape"): ("ออกจากเต็มจอ", lambda a, b: a["fs"] is True and b["fs"] is False),
    ("key", "Shift+N"): ("ไปคลิปถัดไป (ที่อยู่เปลี่ยน)", lambda a, b: a["url"] != b["url"]),
    ("key", "Shift+P"): ("ไปคลิปก่อนหน้า (ที่อยู่เปลี่ยน)", lambda a, b: a["url"] != b["url"]),
    ("key", "i"): ("มินิเพลเยอร์", _flip("mini")),
    ("click", LIKE): ("ปุ่มไลก์เปลี่ยนสถานะ (ต้องล็อกอิน)", _flip("like")),
    # การ์ด 0050 (เขียนก่อนรันสกิลที่ Claude ในเครื่องสร้าง): คีย์/ปุ่มที่ไฟล์ใหม่ใช้
    ("key", "Shift+."): ("เร็วขึ้น", lambda a, b: b["rate"] > a["rate"]),
    ("key", "Shift+,"): ("ช้าลง", lambda a, b: b["rate"] < a["rate"]),
    ("key", "Home"): ("กลับต้นคลิป (< 3 วิ)", lambda a, b: b["t"] is not None and b["t"] < 3),
    ("key", "5"): ("ไปราวครึ่งคลิป", _near(0.5)),
    ("key", "9"): ("ไปราว 90% ของคลิป", _near(0.9)),
    ("click", "like-button-view-model button"): ("ปุ่มไลก์เปลี่ยนสถานะ (ต้องล็อกอิน)", _flip("like")),
    ("click", "dislike-button-view-model button"): (
        "ปุ่มไม่ชอบเปลี่ยนสถานะ (ต้องล็อกอิน)",
        _flip("dislike"),
    ),
    ("click", "#subscribe-button-shape button"): (
        "ติดตามช่อง (ต้องล็อกอิน · วัดไม่ได้)",
        lambda a, b: False,
    ),
}
# ลำดับให้แต่ละข้อวัดได้: เดินหน้าก่อนถอย · เต็มจอก่อนออก · เปลี่ยนคลิป/มินิเพลเยอร์ไว้ท้าย (ออกจากหน้าคลิปเดิม)
ORDER = ["5", "l", "j", "9", "Home", "0", "k", "m", ">", "<", "Shift+.", "Shift+,", "t", "c", LIKE,
         "like-button-view-model button", "dislike-button-view-model button",
         "#subscribe-button-shape button", "f", "Escape", "Shift+P", "Shift+N", "i"]  # fmt: skip


def state(b: BrowserControl) -> dict:
    with b._lock:
        return b._eval(f"{STATE_JS}({json.dumps(LIKE)}, {json.dumps(DISLIKE)})") or {}


def wait_video(b: BrowserControl, timeout: float = 60.0) -> dict:
    """รอจนคลิปเล่นจริงและไม่มีโฆษณา (กดข้ามโฆษณาด้วยคำสั่งเดิมของระบบเมื่อข้ามได้)."""
    end = time.monotonic() + timeout
    s = state(b)
    while time.monotonic() < end:
        s = state(b)
        if s.get("ad"):
            b.run(BrowseCommand("skip_ad"))
        elif s.get("t") is not None and s["t"] > 1:
            return s
        time.sleep(1)
    return s


def run_site(b: BrowserControl, skill) -> list[dict]:
    rows = []
    cmds = sorted(skill.commands, key=lambda c: ORDER.index(c.arg) if c.arg in ORDER else 99)
    for c in cmds:
        wait_video(b, 120)  # คลิปเล่นอยู่และไม่มีโฆษณา (ระหว่างโฆษณา YouTube ห้ามกรอ/เปลี่ยนความเร็ว)
        before = state(b)
        t0 = time.monotonic()
        r = b.run(BrowseCommand(c.kind, query=c.arg, site=skill.site))
        took = round(time.monotonic() - t0, 2)
        time.sleep(1.5)  # ให้หน้าเว็บเปลี่ยนสถานะ (เปลี่ยนคลิป/เต็มจอใช้เวลา)
        after = state(b)
        name, check = CHECKS.get((c.kind, c.arg), ("ไม่มีตัวตรวจ", lambda a, b: False))
        try:
            ok = bool(r.ok and check(before, after))
        except (KeyError, TypeError):
            ok = False
        if before.get("ad"):
            name += " · วัดระหว่างโฆษณา"
        rows.append({"phrase": c.phrases[0], "kind": c.kind, "arg": c.arg, "expect": name,
                     "result_ok": r.ok, "say": r.say, "ok": ok, "seconds": took,
                     "before": before, "after": after})  # fmt: skip
        print(
            f"{'✓' if ok else '✗'} {c.phrases[0]} [{c.kind} {c.arg}] {name} · {r.say} · {took}s",
            flush=True,
        )
    return rows


def run_wrong_site(b: BrowserControl, skill) -> list[dict]:
    """W3: หน้าอื่น (Wikipedia) · คำสั่งของสกิล YouTube ต้องไม่ทำงาน (ไม่กด ไม่คลิก หน้าไม่เปลี่ยน)."""
    b.run(BrowseCommand("site", site="wikipedia"))
    time.sleep(2)
    rows = []
    for c in skill.commands:
        with b._lock:
            url0 = b._url()
        r = b.run(BrowseCommand(c.kind, query=c.arg, site=skill.site))
        with b._lock:
            url1 = b._url()
        ran = r.ok or url0 != url1
        rows.append({"phrase": c.phrases[0], "arg": c.arg, "ran": ran, "say": r.say})
        print(f"{'✗ ทำ!' if ran else '✓ ไม่ทำ'} {c.phrases[0]} บน {url0} · {r.say}", flush=True)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--query", default="ข่าวเช้า")
    # การ์ด 0050: สกิลไม่ติดมากับระบบแล้ว → ระบุไฟล์สกิลที่จะวัด
    ap.add_argument("--skill", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    skill = manifest.load(a.skill)
    profile = Path(tempfile.mkdtemp(prefix="aipc-site-e2e-"))
    b = BrowserControl(profile=profile, extra_args=["--autoplay-policy=no-user-gesture-required"])
    try:
        b.run(BrowseCommand("site_search", site="youtube", query=a.query))
        time.sleep(3)
        r = b.run(BrowseCommand("open", n=1, direction="clip"))
        print("เปิดคลิป:", r.ok, r.say, flush=True)
        start = wait_video(b)
        print("เริ่ม:", json.dumps(start, ensure_ascii=False), flush=True)
        rows = run_site(b, skill)
        wrong = run_wrong_site(b, skill)
    finally:
        b.close()
    ok = sum(r["ok"] for r in rows)
    summary = {"site": "youtube", "commands": len(rows), "ok": ok,
               "rate": round(ok / len(rows), 3) if rows else 0.0,
               "wrong_site_runs": sum(w["ran"] for w in wrong), "wrong_site_tries": len(wrong),
               "query": a.query}  # fmt: skip
    a.out.write_text(json.dumps({"summary": summary, "rows": rows, "wrong_site": wrong},
                                ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
