"""หน้าเว็บที่ AI เห็น (การ์ด 0025): ของที่อยู่บนจอติดเลข + ข้อความบนจอ เป็นข้อความสั้น ๆ.

วัดบน Pi 5 2026-10-13: หน้าเว็บ 1 หน้า ≈ 450–850 token ≈ 25–45 วิให้ Gemma อ่าน → ส่งเฉพาะที่อยู่ในจอ ·
ที่อยู่เว็บถอด %E0… เป็นตัวไทย · ลิงก์ซ้ำรวมกัน · ข้อความไม่ซ้ำกับรายการ
"""

from __future__ import annotations

from urllib.parse import unquote

MAX_ITEMS = 40
TEXT_CHARS = 700

# ของที่มองเห็นบนจอ เรียงบนลงล่าง ซ้ายไปขวา · ติดเลขไว้ที่ data-aipc-n ให้ click/type หาเจอ ·
# ช่องรหัสผ่านไม่ส่งให้ AI เลย (การ์ด 0025 หัวข้อ 2) · ลิงก์ที่ชี้ที่เดียวกันรวมเป็นรายการเดียว (Bing: ชื่อเว็บ + หัวข้อ) ·
# ข้อความบนจอ = ข้อความที่ไม่อยู่ในรายการ (ไม่ส่งซ้ำ · token น้อยลง)
OBSERVE_JS = r"""(() => {
  for (const el of document.querySelectorAll('[data-aipc-n]')) el.removeAttribute('data-aipc-n');
  const SEL = 'a[href], button, input:not([type=hidden]):not([type=password]), textarea, select, ' +
              '[role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], ' +
              '[role=radio], [role=switch], [role=combobox], [role=searchbox], [role=textbox], ' +
              '[contenteditable=true]';
  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();
  const shown = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || r.right < 0 ||
        r.left > innerWidth) return null;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      return null;
    return r;
  };
  const items = [], byHref = new Map();
  for (const el of document.querySelectorAll(SEL)) {
    if (el.closest('[aria-hidden=true]')) continue;
    const tag = el.tagName.toLowerCase(), type = (el.type || '').toLowerCase();
    // ปุ่มซ้อนในลิงก์/ปุ่มอื่น = ส่วนของตัวนอก (ช่องกรอกนับแยกเสมอ)
    if (!/^(input|textarea|select)$/.test(tag) && el.parentElement &&
        el.parentElement.closest(SEL)) continue;
    const r = shown(el);
    if (!r) continue;
    const role = el.getAttribute('role') || '';
    const choice = type === 'checkbox' || type === 'radio' ||
                   /^(checkbox|radio|switch)$/.test(role);
    const field = !choice && (tag === 'textarea' || tag === 'select' || el.isContentEditable ||
      (tag === 'input' && !/^(submit|button|reset|image)$/.test(type)) ||
      /^(combobox|searchbox|textbox)$/.test(role));
    const lab = el.labels && el.labels.length ? clean(el.labels[0].innerText) : '';
    let label, kind;
    if (field) {
      kind = 'ช่อง';
      label = lab || el.getAttribute('aria-label') || el.placeholder || el.title || el.name || '';
      const v = tag === 'select' ? (el.selectedOptions[0] || {}).text : el.value;
      if (v) label += ' = ' + clean(v).slice(0, 40);
    } else if (choice) {
      kind = 'ตัวเลือก';
      label = (lab || el.getAttribute('aria-label') || el.value || '') +
              ((el.checked || el.getAttribute('aria-checked') === 'true') ? ' (เลือกอยู่)' : '');
    } else {
      kind = (tag === 'a' || role === 'link') ? 'ลิงก์' : 'ปุ่ม';
      label = clean(el.innerText) || el.getAttribute('aria-label') || el.title || el.value ||
              (el.querySelector('img[alt]') || {}).alt || '';
    }
    label = clean(label);
    if (!label || /^(true|false)$/i.test(label)) continue;
    const href = kind === 'ลิงก์' ? (el.href || '') : '';
    if (href && byHref.has(href)) {
      const it = byHref.get(href);
      if (!it.label.includes(label)) it.label += ' — ' + label;
      continue;
    }
    const it = {el, kind, label, y: r.top, x: r.left};
    if (href) byHref.set(href, it);
    items.push(it);
  }
  items.sort((p, q) => (Math.round(p.y / 8) - Math.round(q.y / 8)) || (p.x - q.x));
  const out = items.slice(0, %MAX%).map((it, i) => {
    it.el.setAttribute('data-aipc-n', String(i + 1));
    return {n: i + 1, kind: it.kind, label: it.label.slice(0, 80)};
  });
  const parts = [];
  const walker = document.createTreeWalker(document.body || document.documentElement,
                                           NodeFilter.SHOW_TEXT);
  let total = 0;
  while (walker.nextNode() && total < %TEXT%) {
    const t = clean(walker.currentNode.nodeValue);
    const p = walker.currentNode.parentElement;
    if (!t || !p || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(p.tagName)) continue;
    if (p.closest('label, [aria-hidden=true]')) continue;
    const item = p.closest('[data-aipc-n]');
    // อยู่ในรายการแล้ว = ไม่ส่งซ้ำ · ยกเว้นลิงก์กลางประโยค (ไม่งั้นประโยคขาดเป็นรู · วิกิพีเดีย)
    if (item && !(item.tagName === 'A' && item.parentElement &&
                  clean(item.parentElement.innerText).length > clean(item.innerText).length + 30))
      continue;
    const r = p.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight || r.width < 1) continue;
    if (p.checkVisibility && !p.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      continue;  // เมนูที่ซ่อนอยู่ (วิกิพีเดีย)
    parts.push(t);
    total += t.length + 1;
  }
  return {title: document.title, url: location.href, items: out,
          text: parts.join(' ').slice(0, %TEXT%),
          atTop: scrollY < 4,
          atEnd: innerHeight + scrollY >= document.documentElement.scrollHeight - 4};
})()""".replace("%MAX%", str(MAX_ITEMS)).replace("%TEXT%", str(TEXT_CHARS))


def page_text(obs: dict) -> str:
    """หน้าเว็บเป็นข้อความสั้น ๆ ให้ AI อ่าน."""
    if not obs:
        return header(obs)
    lines = [header(obs)]  # ภาษาไทยแบบ %E0%B8… = token มากกว่าหลายเท่า → header() ถอดแล้ว
    pos = "บนสุด" if obs.get("atTop") else "ท้ายสุด" if obs.get("atEnd") else "กลางหน้า"
    lines.append(f"ตำแหน่ง: {pos}")
    for it in obs.get("items", []):
        lines.append(f"[{it['n']}] {it['kind']}: {it['label']}")
    if obs.get("text"):
        lines.append("ข้อความบนจอ: " + obs["text"])
    return "\n".join(lines)


def header(obs: dict) -> str:
    """บรรทัดเดียว: ชื่อหน้า · ที่อยู่ (ขั้นวางแผนเห็นแค่นี้)."""
    if not obs:
        return "หน้าเว็บ: (ยังไม่ได้เปิดเบราว์เซอร์)"
    url = unquote(obs.get("url", ""))
    return f"หน้าเว็บ: {obs.get('title', '')} · {url[:100]}"
