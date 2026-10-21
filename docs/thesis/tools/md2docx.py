"""แปลงร่างเล่ม (Markdown ใน docs/thesis/draft/) เป็น .docx ·
ยืมหน้ากระดาษ/หัว-ท้ายกระดาษจากไฟล์ตัวอย่างของคณะ (word/).

    python docs/thesis/tools/md2docx.py

- ไม่แก้ไฟล์ใน word/ (ของกลุ่มอื่น) · เขียนผลที่ word/ai-pc/ · ใช้ไลบรารีมาตรฐานเท่านั้น (zipfile + XML)
- รูปแบบตามตัวอย่าง: TH Sarabun New · เนื้อความ 16pt จัดกระจายไทย เยื้องบรรทัดแรก ·
  หัวข้อหนา 16pt · หัวบทหนา 20pt กลาง
- คอมเมนต์ <!-- ที่มา … --> ถูกตัด (หลักฐานอยู่ในไฟล์ร่าง) · ```mermaid = ที่ว่างสำหรับภาพ (ต้องแปลงเป็นรูปเอง)
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "docs" / "thesis" / "draft"
SRC = ROOT / "word"
OUT = ROOT / "word" / "ai-pc"
# ร่าง → (ไฟล์ตัวอย่างที่ยืมหน้ากระดาษ, ชื่อไฟล์ผล)
JOBS = [
    ("abstract.md", "02-Abstract.docx", "02-Abstract.docx"),
    ("ch1.md", "04-Chapter1.docx", "04-Chapter1.docx"),
    ("ch2.md", "05-Chapter2.docx", "05-Chapter2.docx"),
    ("ch3.md", "06-Chapter3.docx", "06-Chapter3.docx"),
    ("ch4.md", "07-Chapter4.docx", "07-Chapter4.docx"),
    ("ch5.md", "08-Chapter5.docx", "08-Chapter5.docx"),
    ("ch6.md", "09-Chapter6.docx", "09-Chapter6.docx"),
    ("references.md", "10-References.docx", "10-References.docx"),
    ("cover.md", "01-Cover.docx", "01-Cover.docx"),
]
_F = "TH Sarabun New"
FONT = f'<w:rFonts w:ascii="{_F}" w:eastAsia="Sarabun" w:hAnsi="{_F}" w:cs="{_F}"/>'


def rpr(size: int = 32, bold: bool = False, italic: bool = False) -> str:
    b = "<w:b/><w:bCs/>" if bold else ""
    i = "<w:i/><w:iCs/>" if italic else ""
    return f'<w:rPr>{FONT}{b}{i}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'


def para(text: str, *, size=32, bold=False, italic=False, jc="", first=0, left=0, hanging=0,
         before=0, after=0, keep=False) -> str:  # fmt: skip
    ppr = ""
    if keep:
        ppr += "<w:keepNext/>"
    if before or after:
        ppr += f'<w:spacing w:before="{before}" w:after="{after}"/>'
    if first or left or hanging:
        ind = f' w:left="{left}"' if left else ""
        ind += f' w:firstLine="{first}"' if first else ""
        ind += f' w:hanging="{hanging}"' if hanging else ""
        ppr += f"<w:ind{ind}/>"
    if jc:
        ppr += f'<w:jc w:val="{jc}"/>'
    r = rpr(size, bold, italic)
    tab = "<w:r><w:tab/></w:r>"  # \t ในข้อความ = แท็บ (หลังหัวรายการ)
    runs = tab.join(
        f'<w:r>{r}<w:t xml:space="preserve">{escape(x)}</w:t></w:r>' for x in text.split("\t")
    )
    return f"<w:p><w:pPr>{ppr}{r}</w:pPr>{runs}</w:p>"


def table(rows: list[list[str]]) -> str:
    cols = max(len(r) for r in rows)
    width = 8640 // cols  # ความกว้างหน้ากระดาษในตัวอย่าง ~ 6 นิ้ว
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                     for s in ("top", "left", "bottom", "right", "insideH", "insideV"))  # fmt: skip
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
    head = f'<w:tbl><w:tblPr><w:tblW w:w="{width * cols}" w:type="dxa"/><w:jc w:val="center"/>'
    out = [head + f"<w:tblBorders>{border}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>"]
    tcpr = f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
    for n, r in enumerate(rows):
        cells = r + [""] * (cols - len(r))
        tcs = "".join(f"<w:tc>{tcpr}{para(c, size=28, bold=n == 0)}</w:tc>" for c in cells)
        out.append(f"<w:tr>{tcs}</w:tr>")
    out.append("</w:tbl>")
    return "".join(out) + para("", size=16)


def clean(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", text)  # ลิงก์ = เหลือข้อความ
    return text.strip()


def convert(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            kind = line[3:].strip() or "โค้ด"
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            label = "แผนภาพ (Mermaid) ในไฟล์ร่าง · ต้องแปลงเป็นรูป" if kind == "mermaid" else kind
            out.append(para(f"[{label}]", italic=True, jc="center", before=120, after=120))
            i = j + 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [clean(c) for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out.append(table(rows))
            continue
        if m := re.match(r"#\s+(บทที่\s*\d+)\s*(.*)", line):
            out.append(para(m.group(1), size=40, bold=True, jc="center"))
            if m.group(2):
                out.append(para(clean(m.group(2)), size=40, bold=True, jc="center", after=240))
        elif m := re.match(r"#\s+(.+)", line):
            out.append(para(clean(m.group(1)), size=40, bold=True, jc="center", after=240))
        elif m := re.match(r"##\s+(.+)", line):
            out.append(para(clean(m.group(1)), bold=True, before=240, keep=True))
        elif m := re.match(r"###+\s+(.+)", line):
            out.append(para(clean(m.group(1)), bold=True, left=360, before=120, keep=True))
        elif m := re.match(r"(\s*)[-*]\s+(.+)", line):
            depth = len(m.group(1)) // 2
            out.append(
                para(
                    "•\t" + clean(m.group(2)),
                    left=1080 + 360 * depth,
                    hanging=360,
                    jc="thaiDistribute",
                )
            )
        elif m := re.match(r"(\s*)(\d+[.)])\s+(.+)", line):
            depth = len(m.group(1)) // 2
            item = f"{m.group(2)}\t{clean(m.group(3))}"
            out.append(para(item, left=1080 + 360 * depth, hanging=360, jc="thaiDistribute"))
        elif re.match(r"(ตารางที่|ภาพที่)\s*\d", line):
            out.append(para(clean(line), bold=True, keep=True, before=120))
        elif line.startswith("[ภาพที่"):
            out.append(para(clean(line), italic=True, jc="center", before=120, after=120))
        else:
            out.append(para(clean(line), first=720, jc="thaiDistribute"))
        i += 1
    return "".join(out)


def build(draft: Path, template: Path, target: Path) -> None:
    with zipfile.ZipFile(template) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    sect = re.findall(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)[-1]
    sect = re.sub(r"<w:pgNumType[^>]*/>", "", sect)  # เลขหน้าเริ่มของเล่มตัวอย่าง = ไม่ใช้
    head = doc[: doc.index("<w:body>") + len("<w:body>")]
    body = convert(draft.read_text(encoding="utf-8"))
    new = head + body + sect + "</w:body></w:document>"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = (
                new.encode("utf-8")
                if item.filename == "word/document.xml"
                else zin.read(item.filename)
            )
            if item.filename == "docProps/core.xml":  # ชื่อผู้เขียน/ผู้แก้ล่าสุดของเล่มตัวอย่าง = ล้างออก
                data = re.sub(
                    rb"(<(?:dc:creator|cp:lastModifiedBy|dc:title)>)[^<]*", rb"\g<1>", data
                )
            if item.filename.startswith("word/header"):  # เลขที่โครงงานของกลุ่มอื่นบนหัวกระดาษปก
                data = data.decode("utf-8").replace("C03 /2568", "[ต้องเติม]").encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, target)


def main() -> None:
    for draft, template, name in JOBS:
        src = DRAFT / draft
        if not src.exists():
            print(f"ข้าม {draft} (ยังไม่มีร่าง)")
            continue
        build(src, SRC / template, OUT / name)
        print(f"{draft} → {OUT / name}")


if __name__ == "__main__":
    main()
