"""วัดชุดคำถามสอบจบ 100 ข้อ (tests/data/exam_questions.json · Pakon ขอ 2026-09-30).

    python -m aipc.spikes.exam --label typhoon25-4b --server http://127.0.0.1:8080 \
        --model-name "Typhoon2.5 4B" \
        --out <ไฟล์.json> [--cloud]

ทำตามลำดับเดียวกับแอป: คำสั่งเครื่องที่แปลได้แน่นอน → สกิลสั่งเครื่อง · ที่เหลือ → AI ในเครื่อง
(system prompt + รายการสกิลชุดเดียวกับแอป · catalog.system_prompt/tools) → เลือกสกิล / ตอบเอง /
เลือก ask-cloud (--cloud เท่านั้น) → aipc.cloud.ask (Claude ค้นเว็บได้) · ถามทีละข้อ ไม่มีบทสนทนาต่อเนื่อง

ตรวจอัตโนมัติ (ชั้นแรก · คน 2 คนตรวจข้อที่ไม่ชัด + สุ่ม 20%):
- skill:X → ไปถูกสกิลไหม · answer → มีคำใน must_any ไหม · honest/refuse → บอกตรง ๆ/ปฏิเสธ (must_any) ไหม
- must_not → แต่งข้อมูล · ข้อที่ Claude ตอบ (ข้อมูลจากเว็บ) ไม่ตรวจ must_not แต่ติดป้ายให้คนตรวจ
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from aipc.skills import catalog, manifest, router

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "tests" / "data" / "exam_questions.json"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "max_tokens": 512}  # เท่ากับแอป (chat.client)


def placeholders(now: datetime) -> dict:
    from aipc.ui.thaidate import BE_OFFSET, DAYS, MONTHS

    d = now.date()
    tomorrow = d + timedelta(days=1)
    nxt = MONTHS[d.month % 12]
    days = (date(d.year + 1, 1, 1) - d).days
    return {
        "today_day": str(d.day),
        "today_month": MONTHS[d.month - 1],
        "weekday": DAYS[d.weekday()],
        "tomorrow_weekday": DAYS[tomorrow.weekday()],
        "be_year": str(d.year + BE_OFFSET),
        "days_to_newyear": str(days),
        "days_to_newyear_minus1": str(days - 1),
        "hour": str(now.hour),
        "next_month": nxt,
    }


def fill(words: list[str], ph: dict) -> list[str]:
    return [w.format(**ph) for w in words]


def has_any(text: str, words: list[str]) -> bool:
    t = text.lower().replace(",", "")
    return any(w.lower().replace(",", "") in t for w in words)


def ask_local(server: str, system: str, text: str, tools: list[dict], timeout: float = 600) -> dict:
    """ถาม llama-server แบบ stream เพื่อจับเวลาถึง token แรก · คืน text, tool, ttft, seconds, timings."""
    body = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
        "stream": True,
        "cache_prompt": True,
        **SAMPLING,
    }
    if tools:
        body["tools"], body["tool_choice"] = tools, "auto"
    req = urllib.request.Request(
        server.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    out = {"text": "", "tool": "", "ttft": None, "timings": {}, "finish": ""}
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.strip()
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("timings"):
                out["timings"] = chunk["timings"]
            for ch in chunk.get("choices", []):
                delta = ch.get("delta") or {}
                if ch.get("finish_reason"):
                    out["finish"] = ch["finish_reason"]
                for call in delta.get("tool_calls") or []:
                    name = (call.get("function") or {}).get("name")
                    if name and not out["tool"]:
                        out["tool"] = name
                        out["ttft"] = out["ttft"] or round(time.monotonic() - t0, 2)
                if delta.get("content"):
                    out["ttft"] = out["ttft"] or round(time.monotonic() - t0, 2)
                    out["text"] += delta["content"]
    out["seconds"] = round(time.monotonic() - t0, 2)
    return out


def run_item(it: dict, skills, system: str, tools: list[dict], local, cloud, ph: dict) -> dict:
    """1 ข้อ · local(system, text, tools) → dict · cloud(text) → CloudReply หรือ None (ไม่มีไฮบริด)."""
    row = {"id": it["id"], "cat": it["cat"], "q": it["q"], "expect": it["expect"]}
    r = router.route_ai_first(it["q"], skills)
    if r.skill is not None:  # คำสั่งเครื่องที่แปลได้แน่นอน
        row.update(route=r.skill.id, by="rule", text="", ttft=0.0, seconds=0.0)
    else:
        res = local(system, it["q"], tools)
        row.update(
            by="local",
            text=res["text"],
            ttft=res["ttft"],
            seconds=res["seconds"],
            finish=res.get("finish", ""),
            timings=res.get("timings", {}),
            route=res["tool"] or "chat",
        )
        if res["tool"] == catalog.ASK_CLOUD and cloud is not None:
            c = cloud(it["q"])
            row.update(
                by="cloud",
                cloud_ok=c.ok,
                cloud_error=c.error,
                cloud_seconds=c.seconds,
                cloud_cost=c.cost_usd,
                text=c.text or c.error,
                seconds=round(res["seconds"] + c.seconds, 2),
            )
    judge(row, it, ph)
    return row


def judge(row: dict, it: dict, ph: dict) -> None:
    exp, text = it["expect"], row.get("text", "")
    must_any = fill(it.get("must_any", []), ph)
    must_not = fill(it.get("must_not", []), ph)
    row["fabricated"] = bool(must_not) and row["by"] != "cloud" and has_any(text, must_not)
    if exp.startswith("skill:"):
        row["auto"] = "ok" if row["route"] == exp.split(":", 1)[1] else "wrong-route"
    elif row["route"] not in ("chat", catalog.ASK_CLOUD):
        row["auto"] = "wrong-route"  # คำถามทั่วไปถูกส่งไปสกิล
    elif row["by"] == "cloud":
        row["auto"] = "cloud-answered" if row.get("cloud_ok") else "cloud-failed"
    elif row["fabricated"]:
        row["auto"] = "fabricated"
    elif has_any(text, must_any):
        row["auto"] = "ok"
    else:
        row["auto"] = "check"  # ให้คนตรวจ


def summarize(rows: list[dict], crit: dict) -> dict:
    def share(sel, good):
        s = [r for r in rows if sel(r)]
        return (sum(good(r) for r in s), len(s))

    ok_like = ("ok", "cloud-answered")
    route = share(lambda r: r["expect"].startswith("skill:"), lambda r: r["auto"] == "ok")
    honest = share(lambda r: r["expect"] in ("honest", "refuse"), lambda r: r["auto"] in ok_like)
    fab = sum(r["fabricated"] for r in rows)
    ttfts = sorted(r["ttft"] for r in rows if r["by"] != "rule" and r.get("ttft") is not None)
    by_cat = {}
    for r in rows:
        c = by_cat.setdefault(r["cat"], {"n": 0, "ok": 0, "check": 0, "cloud": 0})
        c["n"] += 1
        c["ok"] += r["auto"] in ok_like
        c["check"] += r["auto"] == "check"
        c["cloud"] += r["by"] == "cloud"
    return {
        "route": route,
        "honest": honest,
        "fabricated": fab,
        "n": len(rows),
        "auto_ok": sum(r["auto"] in ok_like for r in rows),
        "to_check": sum(r["auto"] == "check" for r in rows),
        "cloud": sum(r["by"] == "cloud" for r in rows),
        "ttft_median": ttfts[len(ttfts) // 2] if ttfts else None,
        "seconds_total": round(sum(r.get("seconds") or 0 for r in rows), 1),
        "by_cat": by_cat,
        "checks": {
            "fabricated": fab / len(rows) <= crit["hallucination_max"],
            "honest": honest[1] == 0 or honest[0] / honest[1] >= crit["honest_min"],
            "route": route[1] == 0 or route[0] / route[1] >= crit["route_min"],
            "ttft": bool(ttfts) and ttfts[len(ttfts) // 2] <= crit["first_token_s_median_max"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aipc.spikes.exam")
    ap.add_argument("--label", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--model-name", default="")
    ap.add_argument(
        "--cloud", action="store_true", help="ไฮบริด: เปิดเครื่องมือ ask-cloud + ถาม Claude จริง"
    )
    ap.add_argument("--only", default="", help="เฉพาะ id ที่ขึ้นต้นด้วย (เช่น B) · ว่าง = ทุกข้อ")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    items = [i for i in data["items"] if i["id"].startswith(a.only)]
    now = datetime.now()
    ph = placeholders(now)
    skills = manifest.load_builtin()
    system = catalog.system_prompt(now.date(), cloud=a.cloud, model=a.model_name)
    system += catalog.TOOLS_HINT
    tools = catalog.tools(skills, {"llm"}, cloud=a.cloud)
    cloud = None
    if a.cloud:
        from aipc.cloud import ask

        def cloud(q):
            return ask.ask(q)

    def local(system, text, tools):
        return ask_local(a.server, system, text, tools)

    rows = []
    res = {
        "label": a.label,
        "model": a.model_name,
        "cloud": a.cloud,
        "date": now.isoformat(timespec="minutes"),
        "system_chars": len(system),
        "rows": rows,
    }
    for it in items:
        row = run_item(it, skills, system, tools, local, cloud, ph)
        rows.append(row)
        print(
            f"{row['id']} {row['by']:5} {row['route']:15} {row['auto']:14} "
            f"ttft {row.get('ttft')} · "
            f"{row.get('seconds')} วิ · {row.get('text', '')[:60]!r}",
            flush=True,
        )
        res["summary"] = summarize(rows, data["criteria"])
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
    s = res["summary"]
    print(
        f"{a.label}: ok อัตโนมัติ {s['auto_ok']}/{s['n']} · ให้คนตรวจ {s['to_check']} · "
        f"แต่ง {s['fabricated']} · "
        f"สกิลถูก {s['route'][0]}/{s['route'][1]} · บอกตรง ๆ {s['honest'][0]}/{s['honest'][1]} · "
        f"ส่ง cloud {s['cloud']} · เริ่มตอบ (มัธยฐาน) {s['ttft_median']} วิ"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
