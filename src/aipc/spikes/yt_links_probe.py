"""ตรวจหน้าแรก YouTube ที่เข้าสู่ระบบแล้ว: ลิงก์คลิปอยู่ในแท็กและ class อะไร (การ์ด 0064 S0 ข้อ 2).

ใช้: python yt_links_probe.py <โฟลเดอร์โปรไฟล์ชั่วคราว> · รันบน Pi ในเซสชันที่มีจอ ·
ไม่อ่านชื่อบัญชี ชื่อคลิป หรือคุกกี้ · พิมพ์แค่จำนวน ชื่อแท็ก/class และ path ของลิงก์ (ตัด query ออก)
"""

import json
import sys
import time
from pathlib import Path

from aipc.browser import control
from aipc.browser.control import BrowserControl

PROBE_JS = r"""(() => {
  const out = {path: location.pathname, now: 0, watch: 0, shapes: {}, parents: {}};
  out.now = document.querySelectorAll(%s).length;
  for (const a of document.querySelectorAll('a[href*="/watch"], a[href*="/shorts/"]')) {
    const r = a.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    out.watch++;
    const shape = a.tagName + (a.id ? '#' + a.id : '') + '.' + [...a.classList].join('.');
    out.shapes[shape] = (out.shapes[shape] || 0) + 1;
    let p = a.parentElement, chain = [];
    for (let i = 0; i < 4 && p; i++, p = p.parentElement) chain.push(p.tagName.toLowerCase());
    const key = chain.join('<');
    out.parents[key] = (out.parents[key] || 0) + 1;
  }
  return out;
})()"""


def main(profile: str) -> dict:
    ctl = BrowserControl(profile=Path(profile))
    sel = control.LINKS_JS.split("sel = 'a#video-title-link", 1)[1].split(";", 1)[0]
    sel = "'a#video-title-link" + sel
    ctl._start("about:blank")
    ctl._page()
    ctl._go("https://www.youtube.com/")
    time.sleep(4)  # หน้าแรกโหลดคลิปทีหลัง
    probe = ctl._eval(PROBE_JS % sel)
    links = ctl.links()
    ctl.close()
    probe["links_js_found"] = len(links)
    return probe


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), ensure_ascii=False, indent=1))
