"""วงจรเรียนรู้สกิล (การ์ด 0083): ครั้งแรก AI ในเครื่องให้ Claude สร้างสกิล · ครั้งที่สองเครื่องทำเองโดยไม่เรียก Claude.

ขับแอปตัวจริงด้วย AppDriver (การ์ด 0022) · ทางเดียวกับหน้าจอ · ชุดข้อมูลเป็นข้อความธรรมดาให้ Pakon กรอกได้:

    ข้อ 1
    คำสั่ง: <ประโยคที่พิมพ์สั่งเครื่อง>
    ผลที่ถูก: <เครื่องควรทำอะไร>

บรรทัดที่ขึ้นต้นด้วย # = คำอธิบาย ไม่อ่าน · ชุดทดสอบของ Pakon ตัววัดอ่านเอง ผู้ช่วยไม่เปิด (H9)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict

_ITEM = re.compile(r"^ข้อ\s*(\d+)\s*$")
_FIELD = re.compile(r"^(คำสั่ง|ผลที่ถูก)\s*:\s*(.*)$")
_KEYS = {"คำสั่ง": "text", "ผลที่ถูก": "expect"}


def parse_items(text: str) -> list[dict]:
    """ข้อความชุดข้อมูล → [{id, text, expect}].

    ข้อที่กรอกไม่ครบ = ValueError บอกเลขข้อ · ว่างทั้งไฟล์ = ValueError "ยังไม่ได้กรอก".
    """
    blocks: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := _ITEM.match(line):
            blocks.append({"id": m.group(1), "text": "", "expect": ""})
        elif (m := _FIELD.match(line)) and blocks:
            blocks[-1][_KEYS[m.group(1)]] = m.group(2).strip()
        else:
            raise ValueError(f"อ่านบรรทัดนี้ไม่ได้: {line!r} (ต้องเป็น ข้อ N / คำสั่ง: / ผลที่ถูก:)")
    if not any(b["text"] or b["expect"] for b in blocks):
        raise ValueError("ชุดข้อมูลยังไม่ได้กรอก (ไม่มีข้อที่มีคำสั่ง)")
    for b in blocks:  # กรอกแล้วบางข้อ = ทุกข้อต้องครบ (ไม่ข้ามข้อว่างเงียบ ๆ)
        for key, name in (("text", "คำสั่ง"), ("expect", "ผลที่ถูก")):
            if not b[key]:
                raise ValueError(f"ข้อ {b['id']}: ยังไม่ได้กรอก “{name}”")
    return blocks


def recording_forge(forge: Callable) -> tuple[Callable, list[dict]]:
    """ห่อตัวสร้างสกิล: เก็บผลของ Claude ทุกครั้ง (ไฟล์สกิล · ผลทดลองเส้นทาง · ข้อผิดพลาด) แม้ติดตั้งไม่ได้.

    บทเรียน 2026-10-08: ตัววัดเดิมไม่เก็บ trial และไฟล์สกิลเมื่อไม่ผ่าน → หาสาเหตุไม่ได้ (เกณฑ์ L5)
    """
    records: list[dict] = []

    def run(request, **kw):
        p = forge(request, **kw)
        records.append(asdict(p))
        return p

    return run, records


def unconfirmed(turn, user_ids: set[str]) -> int:
    """คำสั่งเครื่องที่ทำในเทิร์นของสกิลผู้ใช้ (หรือตอนสร้าง) โดยไม่มีการ์ดยืนยันในเทิร์นนั้น (เกณฑ์ L4)."""
    route = turn.route
    by_user = route == "create" or (route.startswith("skill:") and route[6:] in user_ids)
    if not by_user or not turn.plans:
        return 0
    return 0 if any(c.get("confirmToken") for c in turn.cards) else len(turn.plans)


def run_item(drv, store, ledger, records: list[dict], item: dict) -> dict:
    """หนึ่งข้อ: ครั้งแรก (AI ในเครื่องให้ Claude สร้างไหม · ติดตั้งได้ไหม) → ติดตั้งได้ = ครั้งที่สอง (ledger ต้องไม่เพิ่ม).

    drv = AppDriver (หรือตัวปลอมที่มี say(text) → Turn) · store = UserSkills · ledger = Ledger ·
    records = รายการจาก recording_forge (ส่วนที่เพิ่มระหว่างข้อนี้ = ของข้อนี้)
    """
    before = {s.id for s in store.load_all()}
    n_rec, n_led = len(records), len(ledger.entries())
    first = drv.say(item["text"])
    skills = store.load_all()
    new = [s for s in skills if s.id not in before]
    sid = new[0].id if new else ""
    user_ids = {s.id for s in skills}
    forging = any(c.get("kind") == "forging" for c in first.cards)
    row = {
        "id": item["id"], "text": item["text"], "expect": item["expect"],
        "asked_create": first.route == "create" or forging,
        "installed": bool(sid), "skill_id": sid, "skill_md": store.current_md(sid) if sid else "",
        "forge": records[n_rec:], "first_route": first.route, "first_plans": first.plans,
        "first_text": first.text, "first_seconds": first.seconds,
        "first_ledger_added": len(ledger.entries()) - n_led,
        "unconfirmed": unconfirmed(first, user_ids),
    }  # fmt: skip
    if sid:
        n2 = len(ledger.entries())
        again = drv.say(item["text"])
        by_name = again.route.endswith(":" + new[0].name)
        row.update({
            "again_route": again.route, "again_plans": again.plans, "again_text": again.text,
            "again_seconds": again.seconds, "again_ledger_added": len(ledger.entries()) - n2,
            # ทางแชท: AI เลือกสกิล = skill:<id> · กฎเลือกสกิลจากชื่อ = rule:<ชนิด>:<ชื่อสกิล> (แบบการ์ด 0022)
            "again_new_skill": again.route == f"skill:{sid}" or by_name,
        })  # fmt: skip
        row["unconfirmed"] += unconfirmed(again, user_ids)
    return row


# ---------- สรุปผล (เกณฑ์การ์ด 0083 หัวข้อ 8) ----------
def summarize(rows: list[dict], judged: dict[str, bool] | None) -> dict:
    """L1 ครบวงจร (เลือกถาม Claude + ติดตั้งได้) · L2 ครั้งที่สอง (สกิลใหม่ + ledger 0 + Pakon ว่าถูก) ·
    L4 สั่งเครื่องโดยไม่ยืนยัน.

    judged = ใบตรวจของ Pakon {id: ถูกไหม} · ยังไม่มี = L2 เป็น None (รายงานส่วน route/ledger ได้ก่อน)
    """
    installed = [r for r in rows if r["installed"]]
    route_ok = [r for r in installed if r["again_new_skill"] and r["again_ledger_added"] == 0]
    l1 = [sum(r["asked_create"] and r["installed"] for r in rows), len(rows)]
    l2 = None
    if judged is not None:
        l2 = [sum(bool(judged.get(r["id"])) for r in route_ok), len(installed)]
    l4 = sum(r["unconfirmed"] for r in rows)

    def rate(pair):
        return pair[0] / pair[1] if pair and pair[1] else 0.0

    asked = sum(r["asked_create"] for r in rows)
    return {
        "L1": l1,
        "steps": {"asked_create": asked, "installed": len(installed)},
        "L2": l2,
        "L2_route_ledger": [len(route_ok), len(installed)],
        "again_ledger_total": sum(r["again_ledger_added"] for r in installed),
        "L4": l4,
        "pass": {
            "L1": rate(l1) >= 0.8,
            "L2": None if l2 is None else rate(l2) >= 0.9,
            "L4": l4 == 0,
        },  # fmt: skip
    }


def review_sheet(rows: list[dict]) -> str:
    """ใบตรวจให้ Pakon: ครั้งที่สองเครื่องทำอะไร เทียบ "ผลที่ถูก" · กรอก "ถูก" หรือ "ไม่ถูก" หลัง "ตัดสิน:"."""
    out = ["# ใบตรวจวงจรเรียนรู้สกิล (การ์ด 0083 เกณฑ์ L2)", "",
           "กรอกหลัง “ตัดสิน:” ว่า ถูก หรือ ไม่ถูก ทุกข้อ · ดูจาก “ครั้งที่สอง” เทียบกับ “ผลที่ถูก”", ""]  # fmt: skip
    for r in rows:
        if not r["installed"]:
            continue
        plans = ", ".join(f"{a} {p}" for a, p in r["again_plans"]) or "ไม่มี"
        out += [f"## ข้อ {r['id']}", f"- คำสั่ง: {r['text']}", f"- ผลที่ถูก: {r['expect']}",
                f"- ครั้งที่สอง: ไปที่ {r['again_route']} · คำสั่งเครื่อง: {plans}",
                f"- ข้อความที่ตอบ: {' '.join(str(r['again_text']).split())[:500]}",
                "- ตัดสิน: ", ""]  # fmt: skip
    return "\n".join(out) + "\n"


def read_sheet(text: str) -> dict[str, bool]:
    """ใบตรวจที่ Pakon กรอก → {id: ถูกไหม} · ข้อที่ยังไม่กรอกไม่อยู่ในผล."""
    out: dict[str, bool] = {}
    current = ""
    for line in text.splitlines():
        if m := re.match(r"^##\s*ข้อ\s*(\S+)", line):
            current = m.group(1)
        elif (m := re.match(r"^-\s*ตัดสิน:\s*(.*)$", line)) and current:
            v = m.group(1).strip()
            if v in ("ถูก", "ไม่ถูก"):
                out[current] = v == "ถูก"
    return out


# ---------- L3: คำสั่งเดิมไม่เปลี่ยน ----------
def h_routes(skills, items: list[dict] | None = None) -> dict[str, str]:
    """ข้อความชุด H → ทางที่คีย์ลัดเสียงเลือก (handsfree.route · กฎล้วน ไม่มี AI) โดยมีสกิลผู้ใช้ของ skills."""
    from aipc.ui import handsfree

    if items is None:
        from aipc.spikes.voice_h_eval import h_items

        items = h_items()
    return {it["id"]: handsfree.route(it["text"], False, skills.voiceSkill, skills.voiceIntent)
            for it in items}  # fmt: skip


def l3_changes(before: dict[str, str], after: dict[str, str], items: list[dict]) -> list[str]:
    """ข้อที่เป็นคำสั่ง (expect ไม่ว่าง) แล้วทางเปลี่ยนหลังติดตั้งสกิลใหม่ = ของเดิมถูกแย่ง (ต้องเป็น 0)."""
    return [it["id"] for it in items if it["expect"] and before[it["id"]] != after[it["id"]]]


# ---------- Claude ปลอม (ลองตัววัดบน Pi โดยไม่ใช้โควตา · ผลไม่นับ) ----------
def fake_forge():
    """ตัวสร้างสกิลปลอม: ทางเดียวกับของจริง (forge.forge + ประตู) แต่ "Claude" ตอบสกิลงานภาษาตายตัวจากคำขอ."""
    import json

    from aipc.skills import forge

    count = [0]

    def runner(args, prompt, cwd, timeout):
        request = prompt.rsplit("## คำขอ", 1)[-1].strip()
        count[0] += 1
        md = (f"---\nid: loop-fake-{count[0]}\nname: {request[:40]}\n"
              f"description: สกิลทดลองของตัววัด (Claude ปลอม) สำหรับคำขอ {request[:60]}\n"
              f"keywords: {request[:20]}\nexamples:\n  - {request}\n  - ช่วย{request}\n"
              f"  - {request} หน่อย\nworker: llm\nneeds: llm\nversion: 1.0\n"
              "author: ตัววัด 0083\n---\n"
              f"# {request[:40]}\n\n## คำสั่งให้ AI\nตอบสั้น ๆ ว่ารับคำขอนี้แล้ว\n")  # fmt: skip
        body = {"skill_md": md, "should_trigger": [request], "should_not_trigger": ["เปิดยูทูบ"],
                "note": "Claude ปลอม"}  # fmt: skip
        out = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0,
               "result": json.dumps(body, ensure_ascii=False),
               "modelUsage": {"fake": {}}}  # fmt: skip
        return 0, json.dumps(out, ensure_ascii=False), ""

    def run(request, **kw):
        return forge.forge(request, runner=runner, claude="fake", claude_version="fake", **kw)

    return run


# ---------- รันทั้งชุด ----------
POOL_REQUEST = "สกิลผู้ใช้จำลอง (การ์ด 0074)"


def write_json(path, data: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def full_summary(res: dict) -> dict:
    """สรุป L1 L2 L4 + L3 (ถ้าวัดแล้ว) จากไฟล์ผล."""
    s = summarize(res["rows"], res.get("judged"))
    if "L3" in res:
        s["pass"]["L3"] = not res["L3"]["changed"]
    return s


def install_pool(store, path, count: int) -> list[str]:
    """ลงสกิลผู้ใช้จำลอง count ตัวแรกที่ผ่านประตู (ชุดเดียวกับการ์ด 0074) · คืน id ที่ลง."""
    import json

    from aipc.skills import manifest

    builtin = manifest.load_builtin()
    done: list[str] = []
    for it in json.loads(path.read_text(encoding="utf-8"))["items"]:
        if len(done) >= count:
            break
        try:
            m = store.install(it["md"], builtin + store.load_all(), request=POOL_REQUEST)
        except manifest.InvalidSkill:
            continue
        done.append(m.id)
    return done


def main(argv: list[str] | None = None) -> int:
    import argparse
    import hashlib
    import json
    import sys
    import tempfile
    from datetime import datetime
    from pathlib import Path

    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.skill_loop_eval")
    ap.add_argument("--server", required=True, help="llama-server เช่น http://127.0.0.1:18080")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--user-skills", type=Path, help="สกิลผู้ใช้จำลอง (JSON items[].md · การ์ด 0074)")
    ap.add_argument("--user-count", type=int, default=0)
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M")
    ap.add_argument("--fake-claude", action="store_true", help="Claude ปลอม · ลองตัววัด · ผลไม่นับ")
    # ใบตรวจที่ Pakon กรอก → รวมเข้าไฟล์ผลเดิมแล้วสรุป L2 ใหม่ (ไม่รันซ้ำ)
    ap.add_argument("--sheet", type=Path)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if a.sheet:
        res = json.loads(a.out.read_text(encoding="utf-8"))
        res["judged"] = read_sheet(a.sheet.read_text(encoding="utf-8"))
        res["summary"] = full_summary(res)
        write_json(a.out, res)
        print(json.dumps(res["summary"], ensure_ascii=False))
        return 0

    raw = a.data.read_bytes()
    try:
        items = parse_items(raw.decode("utf-8"))
    except ValueError as e:
        print(f"หยุด: {e}", file=sys.stderr)
        return 2

    from aipc.cloud.ask import CloudReply
    from aipc.cloud.ledger import Ledger
    from aipc.skills.userskills import UserSkills
    from aipc.spikes.app_driver import AppDriver
    from aipc.ui import app

    work = Path(tempfile.mkdtemp(prefix="aipc-skill-loop-"))
    ledger = Ledger(work / "outbound.json")
    if a.fake_claude:
        made = fake_forge()

        fake = "Claude ปลอม (ตัววัด 0083)"

        def forge(request, **kw):  # จดลง ledger แบบตัวจริง (app._skill_forge) · L2 นับจาก ledger
            p = made(request, **kw)
            ledger.record("skill", request, 0.0, ok=bool(p.skill_md), note=fake)
            return p

        def cloud(question, history, **kw):
            ledger.record("ask", question, 0.0, ok=False, note=fake)
            return CloudReply(False, error="ตัววัด: Claude ปลอม ไม่ตอบ")
    else:
        forge, cloud = app._skill_forge(ledger), app._cloud_client(ledger)
        if forge is None or cloud is None:
            print("ไม่พบ claude ที่เข้าสู่ระบบในบัญชีนี้", file=sys.stderr)
            return 1
    forge, records = recording_forge(forge)
    store = UserSkills(work / "skills")
    pool = []
    if a.user_skills and a.user_count:
        pool = install_pool(store, a.user_skills, a.user_count)
    drv = AppDriver(a.server, cloud=cloud, forge=forge, user_skills=store,
                    model_name=a.model_name, workdir=work)  # fmt: skip
    if not drv.wait_ready():
        print("AI ในเครื่องไม่พร้อม", file=sys.stderr)
        return 1
    from aipc.spikes.voice_h_eval import h_items

    h = h_items()
    h_before = h_routes(drv.skills, h)
    rows: list[dict] = []
    res = {"date": datetime.now().isoformat(timespec="minutes"), "server": a.server,
           "data": str(a.data), "data_sha256": hashlib.sha256(raw).hexdigest(),
           "fake_claude": a.fake_claude, "user_count": len(pool), "user_pool": pool,
           "rows": rows}  # fmt: skip

    def save():
        res["ledger"] = list(reversed(ledger.entries()))
        res["summary"] = full_summary(res)
        write_json(a.out, res)

    for it in items:
        r = run_item(drv, store, ledger, records, it)
        rows.append(r)
        print(f"ข้อ {it['id']} ถามClaude={r['asked_create']} ติดตั้ง={r['installed']} "
              f"ครั้งที่สอง={r.get('again_route', '-')} ledger+{r.get('again_ledger_added', '-')} "
              f"ไม่ยืนยัน={r['unconfirmed']}", flush=True)  # fmt: skip
        save()
    h_after = h_routes(drv.skills, h)
    res["L3"] = {"changed": l3_changes(h_before, h_after, h),
                 "commands": sum(1 for x in h if x["expect"])}  # fmt: skip
    save()
    sheet = a.out.with_suffix(".sheet.md")
    sheet.write_text(review_sheet(rows), encoding="utf-8", newline="\n")
    print(json.dumps(res["summary"], ensure_ascii=False))
    print(f"ใบตรวจให้ Pakon: {sheet}")
    drv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
