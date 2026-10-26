"""แปลงแผนภาพ Mermaid ในร่างเล่มเป็นรูป PNG สำหรับใส่ในเล่ม Word.

    python docs/thesis/tools/render_figures.py

- อ่านบล็อก ```mermaid ใน docs/thesis/draft/*.md ที่มีบรรทัด `%% figure: <ชื่อ>`
  → เขียน docs/thesis/figures/<ชื่อ>.png
- วาดด้วย Microsoft Edge แบบไม่เปิดหน้าต่าง (headless) + Mermaid จาก CDN (ต้องต่ออินเทอร์เน็ตตอนสร้างรูปเท่านั้น)
  แล้วตัดขอบขาวด้วย OpenCV (มีในโปรเจกต์อยู่แล้ว)
- รูปเป็นผลของโค้ด Mermaid ในร่าง · แก้แผนภาพ = แก้โค้ดในร่างแล้วรันสคริปต์นี้ใหม่
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "docs" / "thesis" / "draft"
OUT = ROOT / "docs" / "thesis" / "figures"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js"
BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)
NAME = re.compile(r"^\s*%% figure: ([\w-]+)\s*$", re.M)

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>body {{ margin: 0; padding: 24px; background: #fff;
  font-family: 'TH Sarabun New', sans-serif; }}
.mermaid svg {{ max-width: none !important; }}</style>
<script src="{mermaid}"></script></head><body><pre class="mermaid">{code}</pre>
<script>mermaid.initialize({{ startOnLoad: true, theme: 'neutral',
  themeVariables: {{ fontFamily: 'TH Sarabun New', fontSize: '20px' }},
  flowchart: {{ useMaxWidth: false }}, sequence: {{ useMaxWidth: false }},
  er: {{ useMaxWidth: false }} }});</script>
</body></html>"""


def render(name: str, code: str, workdir: Path) -> Path:
    html = workdir / f"{name}.html"
    shot = workdir / f"{name}.png"
    # < > ในข้อความในเครื่องหมายคำพูด ใช้รหัสของ Mermaid (ไม่อย่างนั้นถูกอ่านเป็นแท็ก HTML แล้วหาย)
    code = re.sub(
        r'"[^"\n]*"', lambda m: m.group(0).replace("<", "#lt;").replace(">", "#gt;"), code
    )
    escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html.write_text(PAGE.format(mermaid=MERMAID, code=escaped), encoding="utf-8")
    subprocess.run(
        [str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", "--window-size=2000,8000",
         "--virtual-time-budget=20000", f"--screenshot={shot}", html.as_uri()],
        check=True, capture_output=True, timeout=120,
    )  # fmt: skip
    return crop(shot, OUT / f"{name}.png")


def crop(src: Path, dst: Path, pad: int = 16) -> Path:
    """ตัดขอบขาวรอบแผนภาพ เหลือระยะขอบ pad พิกเซล"""
    img = cv2.imread(str(src))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ys, xs = (gray < 245).nonzero()
    if not len(xs):
        raise SystemExit(f"{src.name}: ไม่พบแผนภาพในภาพที่วาด (Mermaid โหลดไม่ขึ้น?)")
    if ys.max() >= img.shape[0] - 2 or xs.max() >= img.shape[1] - 2:
        raise SystemExit(f"{src.name}: แผนภาพล้นหน้าต่างที่ใช้วาด ต้องขยาย --window-size")
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, img.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, img.shape[1])
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), img[y0:y1, x0:x1])
    return dst


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for md in sorted(DRAFT.glob("*.md")):
            for code in BLOCK.findall(md.read_text(encoding="utf-8")):
                if m := NAME.search(code):
                    out = render(m.group(1), NAME.sub("", code), Path(tmp))
                    print(f"{md.name} → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
