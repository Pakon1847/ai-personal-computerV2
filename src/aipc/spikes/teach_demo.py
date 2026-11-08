"""การ์ด 0048: ลองกับ Chromium จริง · L1 (จดครบ · ไม่จดสิ่งที่พิมพ์) · L3 (เล่นซ้ำ) · L4 (ไม่เจอ = หยุด).

ชุดงาน: tests/data/teach_demo_tasks.json · งาน how = human เป็นหน้าที่ของคนที่จอ ตัวนี้ข้าม
รันบน Pi 5 แบบไม่มีจอ:
    python -m aipc.spikes.teach_demo record --out l1.json
    python -m aipc.spikes.teach_demo replay --skills ชุดสกิล.json --out l3.json
    python -m aipc.spikes.teach_demo stop --out l4.json

ปุ่มกดผ่าน Input.dispatchMouseEvent (isTrusted = true เหมือนคนกด)
เพราะตัวจดไม่รับคลิกที่สคริปต์ของหน้าเว็บปลอมขึ้น
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from aipc.browser import demo
from aipc.browser.control import BrowserControl
from aipc.skills import sitecmd
from aipc.skills.browse import BrowseCommand

TASKS = Path("tests/data/teach_demo_tasks.json")
ARGS = ["--headless=new", "--window-size=1280,800", "--lang=th-TH", "--mute-audio",
        "--autoplay-policy=no-user-gesture-required"]  # fmt: skip
SEARCH_BOX = {"youtube": "input[name=search_query]", "wikipedia": "input[name=search]",
              "maps": "#searchboxinput"}  # fmt: skip
TEST_BOX_JS = r"""(() => {
  const i = document.createElement('input');
  i.id = 'aipc-test-box';
  i.style.cssText = 'position:fixed;left:20px;bottom:20px;width:200px;height:30px;z-index:99999';
  document.documentElement.appendChild(i);
})()"""
LOCATE_JS = r"""((sel, labels) => {
  const seen = (e) => { const r = e.getClientRects(); return r.length > 0 && r[0].width > 0; };
  let el = null;
  if (sel) el = [...document.querySelectorAll(sel)].find(seen) || null;
  if (!el && labels) {
    const want = labels.split('|').map((s) => s.trim());
    const all = [...document.querySelectorAll('button,a,[role],.ytp-menuitem,.ytp-menuitem-label')];
    el = all.filter(seen).find((e) => want.includes((e.innerText || '').trim().split('\n')[0]) ||
                                      want.includes(e.getAttribute('aria-label'))) || null;
  }
  if (!el) return null;
  const q = el.getBoundingClientRect();
  if (q.top < 0 || q.left < 0 || q.bottom > innerHeight || q.right > innerWidth) {
    el.scrollIntoView({block: 'center'});
  }
  const r = el.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const hit = document.elementFromPoint(x, y);
  if (!hit || !(hit === el || el.contains(hit))) return null;
  return {x, y, tag: el.tagName.toLowerCase(), aria: el.getAttribute('aria-label') || '',
          id: el.id || '', text: (el.innerText || '').trim().slice(0, 40)};
})"""


def loads(path: Path = TASKS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Driver:
    def __init__(self, profile: Path):
        self.ctl = BrowserControl(profile=profile, extra_args=ARGS, load_timeout=30.0)
        self.typed_where = ""

    def open(self, url: str) -> None:
        r = self.ctl.run(BrowseCommand("url", query=url))
        if not r.ok:
            raise RuntimeError(r.say)
        time.sleep(4)

    def js(self, expr: str):
        return self.ctl._eval(expr)

    def locate(self, step: dict) -> dict | None:
        expr = f"{LOCATE_JS}({json.dumps(step.get('selector'))}, {json.dumps(step.get('text'))})"
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if at := self.js(expr):
                return at
            time.sleep(0.25)
        return None

    def mouse(self, at: dict) -> None:
        session = self.ctl._page()
        press = {"button": "left", "clickCount": 1}
        for kind, extra in (("mouseMoved", {}), ("mousePressed", press), ("mouseReleased", press)):
            params = {"type": kind, "x": at["x"], "y": at["y"], **extra}
            self.ctl._cdp.call("Input.dispatchMouseEvent", params, session=session)
        time.sleep(0.8)

    def key(self, key: str) -> None:
        session = self.ctl._page()
        for kind in ("keyDown", "keyUp"):
            params = {"type": kind, "key": key, "windowsVirtualKeyCode": ord(key.upper())}
            if kind == "keyDown":
                params["text"] = key
            self.ctl._cdp.call("Input.dispatchKeyEvent", params, session=session)
        time.sleep(0.6)

    def type_secret(self, site: str, text: str) -> bool:
        """คลิกช่องพิมพ์ แล้วพิมพ์ทีละตัว · ผ่านเมื่อเบราว์เซอร์รับข้อความจริง."""
        box = SEARCH_BOX[site]
        at = self.js(f"{LOCATE_JS}({json.dumps(box)}, null)")
        if at is None:  # เว็บซ่อนช่องค้นหา (วิกิพีเดียที่จอกว้างเท่านี้) → ใส่ช่องทดสอบ
            box = "#aipc-test-box"
            self.js(TEST_BOX_JS)
            self.typed_where = "ช่องทดสอบที่ตัววัดใส่"
            at = self.locate({"selector": box})
        else:
            self.typed_where = "ช่องค้นหาของเว็บ"
        if at is None:
            return False
        self.mouse(at)
        session = self.ctl._page()
        for ch in text:
            self.ctl._cdp.call(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "text": ch, "key": ch},
                session=session,
            )
            self.ctl._cdp.call(
                "Input.dispatchKeyEvent", {"type": "keyUp", "key": ch}, session=session
            )
        got = self.js(f"document.querySelector({json.dumps(box)}).value")
        self.js(
            f"((e) => {{ e.value = ''; e.blur(); }})(document.querySelector({json.dumps(box)}))"
        )
        if box == "#aipc-test-box":
            self.js("document.getElementById('aipc-test-box').remove()")
        return bool(got) and text[:6] in got

    def close(self) -> None:
        self.ctl.close()


def do_steps(d: Driver, task: dict) -> list[str]:
    """ทำตามขั้นของงาน · คืนสิ่งที่กดจริง (ชนิด + ลักษณะปุ่ม)."""
    done = []
    for step in task["steps"]:
        if step["do"] == "key":
            d.key(step["key"])
            done.append({"kind": "key", "key": step["key"]})
            continue
        at = d.locate(step)
        if at is None:
            if step.get("optional"):
                continue
            raise RuntimeError(f"ไม่เจอปุ่ม: {step['what']}")
        d.mouse(at)
        done.append({"kind": "click", **at})
    return done


def same_step(want: dict, got: demo.Step) -> bool:
    """L1 "จดถูก": ปุ่มที่จดต้องเป็นปุ่มที่กดจริง ไม่ใช่แค่นับจำนวน."""
    if want["kind"] != got.kind:
        return False
    if got.kind == "key":
        return want["key"] == got.key
    labels = [(want.get("aria"), got.aria), (want.get("id"), got.id), (want.get("text"), got.text)]
    # แถวเมนูของ YouTube มีค่าปัจจุบันต่อท้าย ("Playback speed Normal") จึงเทียบแบบมีอยู่ในกัน
    if any(a and b and (a in b or b in a) for a, b in labels):
        return True
    return not any(a for a, _ in labels) and want.get("tag") == got.tag and bool(got.css)


def script_tasks(data: dict) -> list[dict]:
    return [t for t in data["tasks"] if t["how"] == "script"]


def before(d: Driver) -> None:
    """ค่าก่อนทำ สำหรับ effect ที่เทียบกับของเดิม."""
    d.js("window.__before_url = location.href")
    d.js("""window.__before_aria_pressed = (document.querySelector('.ytp-subtitles-button') ||
         {getAttribute: () => null}).getAttribute('aria-pressed')""")
    d.js("window.__before_zoom = parseFloat((location.href.match(/,([0-9.]+)z/) || [0, 0])[1])")


def cmd_record(a) -> int:
    data = loads()
    secret = data["secret_typing"]["text"]
    rows = []
    with tempfile.TemporaryDirectory(prefix="aipc-demo-") as tmp:
        d = Driver(Path(tmp))
        try:
            for t in script_tasks(data):
                row = {"id": t["id"], "site": t["site"], "ok": False}
                rows.append(row)
                try:
                    d.open(t["demo_url"])
                    r = d.ctl.run(BrowseCommand("demo_start", site=t["site"]))
                    if not r.ok:
                        raise RuntimeError(r.say)
                    row["typed"] = d.type_secret(t["site"], secret)
                    row["typed_where"] = d.typed_where
                    want = do_steps(d, t)
                    stop = d.ctl.run(BrowseCommand("demo_stop", query=t["say"]))
                    got = [s.kind for s in stop.steps]
                    dump = json.dumps([s.to_dict() for s in stop.steps], ensure_ascii=False)
                    right = len(want) == len(got) and all(map(same_step, want, stop.steps))
                    row.update(want=want, got=got, steps=[s.to_dict() for s in stop.steps],
                               lines=[demo.describe(s) for s in stop.steps],
                               secret_leaked=secret[:6] in dump, url=stop.url)  # fmt: skip
                    row["right"] = right
                    row["ok"] = right and not row["secret_leaked"] and bool(row["typed"])
                except Exception as e:  # noqa: BLE001 · บันทึกตามจริงแล้วไปงานถัดไป
                    row["error"] = f"{type(e).__name__}: {e}"
                    if d.ctl.demo_active:
                        d.ctl.run(BrowseCommand("demo_stop", direction="cancel"))
                print(json.dumps(row, ensure_ascii=False)[:400], flush=True)
        finally:
            d.close()
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    passed = sum(r["ok"] for r in rows)
    print(f"L1 (เฉพาะงานสคริปต์): {passed}/{len(rows)}")
    return 0


def run_command(d: Driver, cmd: sitecmd.SiteCommand, site: str) -> list[tuple[bool, str]]:
    """ทำคำสั่งของสกิลด้วยโค้ดจริงของ BrowserControl · หยุดที่ขั้นแรกที่ไม่สำเร็จ."""
    steps = sitecmd.parse_steps(cmd.arg)[0] if cmd.kind == "steps" else [(cmd.kind, cmd.arg)]
    out = []
    for kind, arg in steps:
        r = d.ctl.run(BrowseCommand(kind, query=arg, site=site, n=1))
        out.append((r.ok, r.say))
        if not r.ok:
            break
    return out


def cmd_replay(a) -> int:
    """เล่นซ้ำบนหน้าเว็บอื่น · skills = {"id งาน": "บรรทัดคำสั่ง"} ของแบบที่จะวัด."""
    data = loads()
    lines = json.loads(Path(a.skills).read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory(prefix="aipc-demo-") as tmp:
        d = Driver(Path(tmp))
        try:
            for t in data["tasks"]:
                if t["id"] not in lines:
                    continue
                cmds, errors = sitecmd.parse_section([(1, lines[t["id"]])])
                row = {"id": t["id"], "line": lines[t["id"]], "errors": errors, "ok": False}
                rows.append(row)
                if errors or not cmds:
                    print(json.dumps(row, ensure_ascii=False)[:300], flush=True)
                    continue
                try:
                    d.open(t["replay_url"])
                    before(d)
                    row["steps"] = run_command(d, cmds[0], t["site"])
                    time.sleep(2.5)
                    row["effect"] = bool(d.js(t["effect"]))
                    row["ok"] = row["effect"] and all(ok for ok, _ in row["steps"])
                except Exception as e:  # noqa: BLE001
                    row["error"] = f"{type(e).__name__}: {e}"
                print(json.dumps(row, ensure_ascii=False)[:300], flush=True)
        finally:
            d.close()
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"เล่นซ้ำสำเร็จ: {sum(r['ok'] for r in rows)}/{len(rows)}")
    return 0


def cmd_stop(a) -> int:
    """L4: เปลี่ยนตัวเลือกของขั้นที่ 2 เป็นตัวที่ไม่มีในหน้า → ต้องหยุด และไม่ทำขั้นถัดไป."""
    data = loads()
    broken = data["fail_cases"]["broken_selector"]
    tasks = {t["id"]: t for t in data["tasks"]}
    rows = []
    with tempfile.TemporaryDirectory(prefix="aipc-demo-") as tmp:
        d = Driver(Path(tmp))
        try:
            for tid in data["fail_cases"]["use_tasks"]:
                t = tasks[tid]
                d.open(t["demo_url"])
                before(d)
                first = data["fail_cases"]["first_step"][tid]
                line = f"- ทดสอบ → {first} แล้ว คลิก {broken} แล้ว กดคีย์ m"
                cmds, errors = sitecmd.parse_section([(1, line)])
                out = run_command(d, cmds[0], t["site"]) if cmds else []
                # ขั้น 1 ทำได้ · ขั้น 2 ไม่เจอ · ขั้น 3 ต้องไม่ถูกทำ
                stopped = len(out) == 2 and out[0][0] and not out[1][0]
                rows.append({"id": tid, "errors": errors, "steps": out, "ok": stopped})
                print(json.dumps(rows[-1], ensure_ascii=False)[:300], flush=True)
        finally:
            d.close()
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"L4: {sum(r['ok'] for r in rows)}/{len(rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m aipc.spikes.teach_demo", description=__doc__.splitlines()[0]
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_record)
    r = sub.add_parser("replay")
    r.add_argument("--skills", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_replay)
    r = sub.add_parser("stop")
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_stop)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
