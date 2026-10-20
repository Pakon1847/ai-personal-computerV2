"""การ์ด 0046 เกณฑ์ W3 (ทางตรรกะ · ใช้ backend จริงของแอป · ไม่ต้องใช้เบราว์เซอร์): สกิลประจำเว็บไม่ทำงานผิดที่.

    python -m aipc.spikes.site_skill_eval --out ผล.json

1. ไม่ใช่คำสั่งถูกทำ: ประโยค none/ask ของชุดเสียง 0042 ทั้ง 5 ชุด + ชุด 0045 (voice_cmd_dev/test) ·
   พูดขณะเปิด YouTube / Spotify แล้วได้ "ทำเลย" (siteRun) ต้อง 0 · การ์ดถามก่อน (ใกล้เคียง) นับแยก (ไม่ใช่การทำ)
2. ผิดเว็บ: ทุกคำพูดของทุกสกิลประจำเว็บ พูดขณะเปิดเว็บอื่น (รวมโดเมนปลอมชื่อคล้าย) → ต้องไม่ได้อะไรเลย
3. ทางจริงของคำพูดในสกิล (ลำดับเดียวกับ WorkspacePage.voiceCommand): ระบบเดิมรับไป หรือถึงสกิลประจำเว็บ
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aipc.spikes import voice_all_eval as ev

URLS = {"youtube": "https://www.youtube.com/watch?v=x", "spotify": "https://open.spotify.com/"}
ELSEWHERE = ["https://www.netflix.com/browse", "https://th.wikipedia.org/wiki/x",
             "https://www.google.com/search?q=x", "https://evil-youtube.com/watch?v=x",
             "https://youtube.com.evil.example/watch", "https://open.spotify.com.evil.example/",
             "https://www.viu.com/ott/th/"]  # fmt: skip
SYSTEM = ("skill", "browser", "open_browser", "app", "command")  # ทางที่หน้าจอทำก่อนสกิลประจำเว็บ


def non_commands(skills) -> list[str]:
    out = []
    for name in ("dev", "test", "test2", "dev3", "test3"):
        items = json.loads((ev.DATA / f"voice_all_{name}.json").read_text(encoding="utf-8"))[
            "items"
        ]
        out += [i["text"] for i in items if i["expect"] in ("none", "ask")]
    for name in ("dev", "test"):
        items = json.loads((ev.DATA / f"voice_cmd_{name}.json").read_text(encoding="utf-8"))[
            "items"
        ]
        out += [t for t in items if ev.label(t, skills) in ("none", "ask")]
    return sorted(set(out))


def main(argv: list[str] | None = None) -> int:
    from aipc.ui import handsfree

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _engine, skills = ev.backend()
    site_skills = [s for s in skills._skills if s.site]
    texts = non_commands(skills)
    acted, asked = [], []
    for site, url in URLS.items():
        for t in texts:
            if skills.siteCommand(t, url).get("siteRun"):
                acted.append([site, t])
            if skills.siteNear(t, url).get("confirmToken"):
                asked.append([site, t])
    wrong = []
    for s in site_skills:
        for c in s.commands:
            for p in c.phrases:
                for url in ELSEWHERE:
                    if skills.siteCommand(p, url) or skills.siteNear(p, url):
                        wrong.append([s.id, p, url])
    reach = []
    for s in site_skills:
        for c in s.commands:
            for p in c.phrases:
                way = handsfree.route(p, True, skills.voiceSkill, skills.voiceIntent)
                got = skills.siteCommand(p, URLS[s.site]) if way not in SYSTEM else {}
                to = "site" if got else f"system:{way}" if way in SYSTEM else f"other:{way}"
                reach.append({"skill": s.id, "phrase": p, "arg": c.arg, "goes_to": to})
    summary = {
        "noncommand_texts": len(texts),
        "noncommand_acted": len(acted),
        "noncommand_asked_near": len(asked),
        "wrong_site_tries": sum(len(c.phrases) for s in site_skills for c in s.commands)
        * len(ELSEWHERE),
        "wrong_site_hits": len(wrong),
        "phrases": len(reach),
        "phrases_reach_site_skill": sum(r["goes_to"] == "site" for r in reach),
        "phrases_taken_by_system": sum(r["goes_to"].startswith("system") for r in reach),
    }
    a.out.write_text(json.dumps({"summary": summary, "acted": acted, "asked_near": asked,
                                 "wrong_site": wrong, "reach": reach},
                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for r in reach:
        if r["goes_to"] != "site":
            print(f"  {r['skill']}: “{r['phrase']}” → {r['goes_to']}")
    for site, t in asked:
        print(f"  ถามก่อน ({site}): {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
