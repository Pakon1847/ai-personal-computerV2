"""ดูฉันทำ แล้วทำตาม (การ์ด 0048): จดสิ่งที่ผู้ใช้ทำให้ดูในเบราว์เซอร์ของผู้ช่วย.

จด: คลิก (ลักษณะปุ่ม · ไม่จดตำแหน่งบนจอ) · คีย์ลัด (เฉพาะตอนไม่ได้อยู่ในช่องพิมพ์)
ไม่จดเด็ดขาด: ตัวอักษรที่พิมพ์ · ค่าในช่องกรอก · การคลิกในช่องรหัสผ่าน/ฟอร์มชำระเงิน (H1 H3)

ตัวจดในหน้าเว็บส่งแต่ละขั้นกลับทันทีผ่าน Runtime.addBinding · การ์ดร่างไว้ว่าเก็บใน sessionStorage
แต่ที่เก็บนั้นแยกตามโดเมน ขั้นที่จดจะหายเมื่อกดลิงก์ไปโดเมนย่อยอื่น (เช่น วิกิพีเดียไทย → อังกฤษ)
ทุกค่าที่มาจากหน้าเว็บเป็นข้อมูล (H8): ตรวจรูปแบบที่นี่ และผู้ใช้เห็นก่อนส่งให้ Claude
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass

BINDING = "__aipcDemoStep"
MAX_RECORDED = 40

STOP_JS = r"""(() => {
  window.__aipcDemoOff = true;
  const bar = document.getElementById('aipc-demo-bar');
  if (bar) bar.remove();
})()"""


def recorder_js(banner: str) -> str:
    """สคริปต์ที่ฝังในทุกหน้าของแท็บระหว่างบันทึก · ฝังซ้ำได้ (ตัวดักมีชุดเดียว)."""
    return _RECORDER_JS.replace("__BANNER__", json.dumps(banner, ensure_ascii=False))


_RECORDER_JS = r"""(() => {
  const banner = __BANNER__;
  window.__aipcDemoOff = false;
  const showBar = () => {
    if (document.getElementById('aipc-demo-bar') || !document.documentElement) return;
    const bar = document.createElement('div');
    bar.id = 'aipc-demo-bar';
    bar.textContent = banner;
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
      'background:#b3261e;color:#fff;font:600 18px sans-serif;text-align:center;padding:8px;' +
      'pointer-events:none';
    document.documentElement.appendChild(bar);
  };
  showBar();
  document.addEventListener('DOMContentLoaded', showBar);
  if (window.__aipcDemoOn) return;
  window.__aipcDemoOn = true;

  const cut = (s, n) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const typing = (el) => !!el && el.nodeType === 1 &&
    (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
  const BAD = new RegExp('passw|card[-_]?(number|num|holder)|cc-|cvv|cvc|security[-_]?code|' +
                         'otp|payment|billing|checkout', 'i');
  const secret = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const hints = [e.id, e.getAttribute('name'), e.getAttribute('autocomplete'),
                     e.getAttribute('action')].join(' ');
      if (BAD.test(hints)) return true;
      if (e.tagName === 'FORM' && e.querySelector('input[type="password"]')) return true;
    }
    return false;
  };
  const cssPath = (el) => {
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && parts.length < 6; e = e.parentElement) {
      if (e.id) { parts.unshift('#' + CSS.escape(e.id)); break; }
      const tag = e.tagName.toLowerCase();
      const same = e.parentElement
        ? [...e.parentElement.children].filter((c) => c.tagName === e.tagName) : [];
      parts.unshift(same.length > 1 ? `${tag}:nth-of-type(${same.indexOf(e) + 1})` : tag);
    }
    return parts.join(' > ');
  };
  const button = (el) => el.closest('a,button,summary,label,[role="button"],[role="link"],' +
    '[role="menuitem"],[role="menuitemradio"],[role="tab"],[role="option"],[role="checkbox"],' +
    '[role="switch"]') || el;
  const send = (step) => {
    try { window.__aipcDemoStep(JSON.stringify(step)); } catch (e) { /* หยุดบันทึกแล้ว */ }
  };

  addEventListener('click', (e) => {
    const raw = e.target;
    // isTrusted: สคริปต์ของหน้าเว็บปลอมการคลิกให้ถูกจดไม่ได้
    if (!e.isTrusted || window.__aipcDemoOff || !raw || raw.nodeType !== 1) return;
    const el = button(raw);
    if (typing(raw) || typing(el) || secret(raw)) return;
    send({kind: 'click', tag: el.tagName.toLowerCase(), id: cut(el.id, 60),
          testid: cut(el.getAttribute('data-testid'), 60),
          aria: cut(el.getAttribute('aria-label'), 60), role: cut(el.getAttribute('role'), 20),
          text: cut(el.innerText || el.textContent, 40), css: cut(cssPath(el), 200)});
  }, true);

  addEventListener('keydown', (e) => {
    if (!e.isTrusted || e.repeat || window.__aipcDemoOff) return;
    const a = document.activeElement;
    if (typing(e.target) || typing(a) || secret(a)) return;
    if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(e.key)) return;
    let key = e.key === ' ' ? 'Space' : e.key;
    if (e.shiftKey && /^[a-zA-Z]$/.test(key)) key = 'Shift+' + key.toUpperCase();
    if (e.altKey) key = 'Alt+' + key;
    if (e.ctrlKey) key = 'Ctrl+' + key;
    send({kind: 'key', key: cut(key, 30)});
  }, true);
})()"""


@dataclass(frozen=True)
class Step:
    kind: str  # click | key
    key: str = ""
    tag: str = ""
    id: str = ""
    testid: str = ""
    aria: str = ""
    role: str = ""
    text: str = ""
    css: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_LIMITS = {"key": 30, "tag": 20, "id": 60, "testid": 60, "aria": 60, "role": 20, "text": 40,
           "css": 200}  # fmt: skip


def parse_step(raw) -> Step | None:
    """ข้อมูลจากหน้าเว็บ → Step · ผิดรูปแบบ = None · รับเฉพาะช่องที่รู้จัก (H8)."""
    from aipc.skills import sitecmd

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, dict) or raw.get("kind") not in ("click", "key"):
        return None
    fields = {k: " ".join(str(raw.get(k) or "").split())[:n] for k, n in _LIMITS.items()}
    if raw["kind"] == "key":
        key = fields["key"]
        if not sitecmd.KEY_RE.fullmatch(key) or key.lower() in sitecmd.BROWSER_KEYS:
            return None
        return Step("key", key=key)
    return Step("click", **{k: v for k, v in fields.items() if k != "key"})


class Recording:
    """ขั้นที่จดไว้ระหว่างสาธิต · ตัวอ่านของ CDP เรียก on_binding จากอีกเธรด."""

    def __init__(self, session: str):
        self.session = session
        self.script = ""
        self._steps: list[Step] = []
        self._lock = threading.Lock()

    def on_binding(self, params: dict, session: str) -> None:
        if params.get("name") != BINDING or session != self.session:
            return
        step = parse_step(params.get("payload", ""))
        if step is not None:
            with self._lock:
                if len(self._steps) < MAX_RECORDED:
                    self._steps.append(step)

    @property
    def steps(self) -> tuple[Step, ...]:
        with self._lock:
            return tuple(self._steps)


def describe(step: Step) -> str:
    """ขั้นที่จดเป็นภาษาคน (แสดงให้ผู้ใช้ดูก่อนส่ง Claude)."""
    if step.kind == "key":
        return f"กดคีย์ {step.key}"
    label = step.aria or step.text or step.testid or step.id
    return f"คลิก “{label}”" if label else f"คลิกปุ่มในหน้าเว็บ ({step.tag or 'ไม่ทราบชนิด'})"


def for_claude(step: Step) -> str:
    """ลักษณะของขั้นที่ส่งให้ Claude · ไม่มีข้อมูลอื่นของผู้ใช้."""
    if step.kind == "key":
        return f"กดคีย์ {step.key}"
    pairs = (("แท็ก", step.tag), ("id", step.id), ("data-testid", step.testid),
             ("aria-label", step.aria), ("role", step.role), ("ข้อความบนปุ่ม", step.text),
             ("เส้นทาง CSS", step.css))  # fmt: skip
    shown = (f"{name}={json.dumps(v, ensure_ascii=False)}" for name, v in pairs if v)
    return "คลิก: " + " · ".join(shown)


def literal_command(name: str, steps: tuple[Step, ...]) -> str:
    """แบบจดตรง ๆ (เส้นทาง CSS ตามที่จด) · ใช้เทียบกับแบบที่ Claude เขียนในเกณฑ์ L3."""
    parts = [f"กดคีย์ {s.key}" if s.kind == "key" else f"คลิก {s.css}" for s in steps]
    return f"- {name} → " + " แล้ว ".join(parts)


_TAIL = re.compile(r"\s*(ครับ|ค่ะ|คะ|นะ|จ้า)+$")
_START = re.compile(r"(เริ่มบันทึก|เริ่มจด|จำขั้นตอน(นี้)?|ดูฉันทำ|ดูผมทำ|ดูหนูทำ)(ขั้นตอน(นี้)?)?")
_NAMED = re.compile(r"(?:(?:เสร็จ(?:แล้ว)?|จบ(?:แล้ว)?)\s*)?ตั้งชื่อ(?:ว่า)?\s*(?P<name>.+)")
_DONE = re.compile(r"เสร็จ(แล้ว)?|จบ(แล้ว)?|เรียบร้อย(แล้ว)?")
_CANCEL = re.compile(r"ยกเลิก(การ)?(บันทึก|จด|สาธิต)?")


def intent(text: str) -> tuple[str, str]:
    """คำพูด → (start | stop | done | cancel | "", ชื่อคำสั่ง) · โค้ดตัดสิน ไม่ใช่ AI (H6)."""
    t = _TAIL.sub("", " ".join(text.split()))
    if _START.fullmatch(t.replace(" ", "")):
        return "start", ""
    if m := _NAMED.fullmatch(t):
        return "stop", m.group("name").strip()
    bare = t.replace(" ", "")
    if _DONE.fullmatch(bare):
        return "done", ""
    if _CANCEL.fullmatch(bare):
        return "cancel", ""
    return "", ""


def site_of(url: str) -> str:
    """เว็บในรายการที่คุมได้และรับสกิลประจำเว็บ · ไม่ใช่ = ""."""
    from aipc.skills import sitecmd
    from aipc.skills.actions import SITES, SYSTEM_BROWSER_SITES

    if any(sitecmd.on_site(k, url) for k in sitecmd.NO_SITE_SKILL):  # อีเมล เอกสาร ไฟล์ของบัญชี Google
        return ""
    found = [k for k in SITES if k not in SYSTEM_BROWSER_SITES and k not in sitecmd.NO_SITE_SKILL
             and sitecmd.on_site(k, url)]  # fmt: skip
    # Google Maps อยู่ใต้ www.google.com จึงตรงกับ "google" ด้วย
    return "maps" if "maps" in found else (found[0] if found else "")
