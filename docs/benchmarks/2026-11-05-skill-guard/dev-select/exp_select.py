"""ทดลองบนชุดพัฒนา (S2a/S2b หลังรันแล้ว) · โน้ตบุ๊ก = คัดกรองความแม่น ไม่ใช่เวลา.
variant:
  auto     = แบบเดิม (tool_choice auto)
  required = tool_choice required + เครื่องมือ "ตอบเอง" (none)
"""
import json, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, "D:/aipc-0074/src")
from aipc.skills import catalog, manifest, retrieval, router
from aipc.spikes import skill_select as ss

SERVER = "http://127.0.0.1:18081"
NONE_TOOL = {"type": "function", "function": {
    "name": "answer_directly",
    "description": "ไม่มีเครื่องมือไหนตรงกับคำขอ → ตอบเองแบบคุยทั่วไป",
    "parameters": {"type": "object", "properties": {}}}}


def ask(text, tools, variant):
    body = {"messages": [{"role": "system", "content": ss.SYSTEM_PROMPT},
                         {"role": "user", "content": text}],
            "tools": tools, "tool_choice": "auto", "stream": False, "cache_prompt": True, **ss.SAMPLING}
    if variant == "required":
        body["tools"] = tools + [NONE_TOOL]
        body["tool_choice"] = "required"
    req = urllib.request.Request(SERVER + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    calls = m.get("tool_calls") or []
    return (calls[0]["function"]["name"] if calls else ""), (m.get("content") or "")


def run(dataset, n_user, variant, out):
    b = manifest.load_builtin()
    user, _ = ss.load_pool(Path("D:/aipc-0074/tests/data/skill_guard_pool.json"), b)
    user = user[:n_user]
    uids = {m.id for m in user}
    items = json.load(open(dataset, encoding="utf-8"))["items"]
    rows = []
    for it in items:
        picked = retrieval.pick(user, it["text"])
        if MIN_SCORE:
            ix = retrieval._index_for(user)
            q = ix._vec(retrieval.grams(it["text"]))
            sc = {s.id: sum(w * v.get(g, 0) for g, w in q.items()) for s, v in zip(ix.skills, ix.vecs)}
            picked = [m for m in picked if sc[m.id] >= MIN_SCORE]
        tools = catalog.tools(list(b) + picked, {"llm"})
        known = {t["function"]["name"] for t in tools}
        got = ss.by_rules(it["text"], list(b) + user, {"llm"}, True, "ai-first") or ""
        by, text = "rule", ""
        if not got:
            v = variant if variant != "hybrid" else ("required" if picked else "auto")
            name, text = ask(it["text"], tools, v)
            by = "ai"
            got = name if name in known else "none"
        rows.append({**it, "got": got, "by": by, "ok": got == it["expect"], "text_out": text[:120]})
    none = [r for r in rows if r["expect"] == "none"]
    res = {"variant": variant, "min_score": MIN_SCORE, "n_user": n_user, "correct": sum(r["ok"] for r in rows), "total": len(rows),
           "false_calls": sum(r["got"] != "none" for r in none), "none_total": len(none),
           "to_user_wrong": sum(1 for r in rows if not r["ok"] and r["got"] in uids), "rows": rows}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(Path(dataset).stem, n_user, variant, MIN_SCORE, res["correct"], "/", res["total"],
          "false", res["false_calls"], "/", res["none_total"], "to-user-wrong", res["to_user_wrong"], flush=True)


MIN_SCORE = 0.0
if __name__ == "__main__":
    if len(sys.argv) > 5:
        MIN_SCORE = float(sys.argv[5])
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
