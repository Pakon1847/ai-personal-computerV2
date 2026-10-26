"""แปลงร่างเล่ม (Markdown ใน docs/thesis/draft/) เป็น .docx ตามแม่แบบของคณะ "Template รหัส 66".

    python docs/thesis/tools/md2docx.py               # สร้างไฟล์ (เลขหน้าในสารบัญ = x)
    python docs/thesis/tools/md2docx.py --with-word   # สร้าง → ให้ Word นับหน้า → สร้างซ้ำพร้อมเลขหน้าจริง

- แม่แบบ = word/Template รหัส 66/ (ไม่แก้) · ผล = word/ai-pc/ · ใช้ไลบรารีมาตรฐานเท่านั้น (zipfile + XML)
- ยืมหน้ากระดาษ หัวกระดาษ (เลขหน้า) และสไตล์จากไฟล์แม่แบบ แล้วเขียนเนื้อหาใหม่ทั้งหมด (คำอธิบายสีแดงในแม่แบบไม่ติดมา)
  01 ปก = ปก รองปก หน้าอนุมัติ · 02 = กิตติกรรมประกาศ บทคัดย่อไทย/อังกฤษ (เลขหน้า ค ง จ …) ·
  03 = สารบัญ สารบัญตาราง สารบัญภาพ (สร้างจากหัวข้อในร่าง) · 04–10 = บทที่ 1–6 และบรรณานุกรม (เลขหน้าต่อกันทั้งเล่ม)
- รูปแบบตามแม่แบบ: TH Sarabun New · เนื้อความ 16 กระจายแบบไทย เยื้องบรรทัดแรก 0.5 นิ้ว · หัวบท 20 หนา กลาง ·
  หัวข้อ 16 หนา เว้น 1 บรรทัดก่อน · รายการใช้เลข/ขีดอัตโนมัติของ Word ที่ระยะ 0.5 นิ้ว ·
  "ตารางที่" หนา + ชื่อปกติ อยู่บนซ้ายของตาราง · "รูปที่" หนา + ชื่อปกติ อยู่กลางใต้รูป
- ข้อความไทยแยกเป็นช่วง (run) ที่ติดป้าย complex script ให้ Word ตัดคำไทยได้
  (ไม่อย่างนั้นการกระจายแบบไทยจะยืดตัวอักษร)
- คอมเมนต์ <!-- ที่มา … --> ถูกตัด (หลักฐานอยู่ในไฟล์ร่าง) · ```mermaid = ที่ว่างสำหรับรูป (ต้องแปลงเป็นรูปเอง)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "docs" / "thesis" / "draft"
TOOLS = Path(__file__).resolve().parent
TEMPLATE_DIR = "Template รหัส 66"
# ร่าง → ชื่อไฟล์ผล (บทและบรรณานุกรม เลขหน้าต่อกันตามลำดับนี้)
CHAPTERS = [
    ("ch1.md", "04-Chapter1.docx"),
    ("ch2.md", "05-Chapter2.docx"),
    ("ch3.md", "06-Chapter3.docx"),
    ("ch4.md", "07-Chapter4.docx"),
    ("ch5.md", "08-Chapter5.docx"),
    ("ch6.md", "09-Chapter6.docx"),
    ("references.md", "10-References.docx"),
]
PAGES_JSON = "_pages.json"  # ผลนับหน้าจาก Word (pages.ps1)
THAI_LETTERS = "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"  # ลำดับเลขหน้าแบบ ThaiLetter ของ Word
TODO = "[ต้องเติม]"

_F = "TH Sarabun New"
FONT = f'<w:rFonts w:ascii="{_F}" w:eastAsia="{_F}" w:hAnsi="{_F}" w:cs="{_F}"/>'
THAI = re.compile(r"([฀-๿]+)")
TEXT_W = 8306  # ความกว้างพื้นที่พิมพ์ (A4 ลบขอบซ้ายขวา 1.25 นิ้ว) หน่วย twip
PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


# ---------- ตัวสร้าง XML พื้นฐาน ----------


def rpr(size: int = 32, bold: bool = False, italic: bool = False, cs: bool = False) -> str:
    b = "<w:b/><w:bCs/>" if bold else ""
    i = "<w:i/><w:iCs/>" if italic else ""
    c = "<w:cs/>" if cs else ""
    return f'<w:rPr>{FONT}{b}{i}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>{c}</w:rPr>'


def runs(text: str, size: int = 32, bold: bool = False, italic: bool = False) -> str:
    """ข้อความ → run · ช่วงอักษรไทยติด <w:cs/> · \\t = แท็บ"""
    out = []
    for n, piece in enumerate(text.split("\t")):
        if n:
            out.append("<w:r><w:tab/></w:r>")
        for seg in THAI.split(piece):
            if seg:
                r = rpr(size, bold, italic, cs=bool(THAI.fullmatch(seg)))
                out.append(f'<w:r>{r}<w:t xml:space="preserve">{escape(seg)}</w:t></w:r>')
    return "".join(out)


def para(
    text="",
    *,
    spans=None,
    size=32,
    bold=False,
    italic=False,
    jc="",
    first=0,
    left=0,
    hanging=0,
    before=0,
    after=0,
    keep=False,
    tabs=(),
    num=None,
) -> str:
    """ย่อหน้าหนึ่งย่อหน้า · spans = [(ข้อความ, หนา?)] ใช้เมื่อหนาแค่บางส่วน (เช่น "ตารางที่ 1.1" หนา ชื่อปกติ)"""
    ppr = "<w:keepNext/>" if keep else ""
    if num:  # (numId, ระดับ) = เลข/ขีดอัตโนมัติ
        ppr += f'<w:numPr><w:ilvl w:val="{num[1]}"/><w:numId w:val="{num[0]}"/></w:numPr>'
    if tabs:
        ppr += (
            "<w:tabs>" + "".join(f'<w:tab w:val="left" w:pos="{t}"/>' for t in tabs) + "</w:tabs>"
        )
    ppr += f'<w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
    if first or left or hanging:
        ind = f' w:left="{left}"' if left else ""
        ind += f' w:firstLine="{first}"' if first else ""
        ind += f' w:hanging="{hanging}"' if hanging else ""
        ppr += f"<w:ind{ind}/>"
    if jc:
        ppr += f'<w:jc w:val="{jc}"/>'
    spans = spans if spans is not None else [(text, bold)]
    body = "".join(runs(t, size, b, italic) for t, b in spans)
    return f"<w:p><w:pPr>{ppr}{rpr(size, bold)}</w:pPr>{body}</w:p>"


def blank(size: int = 32, n: int = 1) -> str:
    return para("", size=size) * n


def col_widths(rows: list[list[str]], total: int) -> list[int]:
    """แบ่งความกว้างคอลัมน์ตามความยาวข้อความ (ขั้นต่ำ/สูงสุดกันคอลัมน์แคบหรือกว้างเกิน)"""
    cols = max(len(r) for r in rows)
    weight = [
        min(max(max((len(r[c]) for r in rows if c < len(r)), default=0), 10), 60)
        for c in range(cols)
    ]
    widths = [total * w // sum(weight) for w in weight]
    widths[-1] += total - sum(widths)
    return widths


def table(rows: list[list[str]]) -> str:
    """ตารางมีเส้น · แถวแรก = หัวตาราง (หนา · ซ้ำทุกหน้าเมื่อตารางยาวข้ามหน้า)"""
    cols = max(len(r) for r in rows)
    widths = col_widths(rows, TEXT_W)
    border = "".join(
        f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        for s in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = [
        f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/>'
        f"<w:tblBorders>{border}</w:tblBorders>"
        f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
    ]
    for n, r in enumerate(rows):
        cells = r + [""] * (cols - len(r))
        trpr = (
            "<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>"
            if n == 0
            else "<w:trPr><w:cantSplit/></w:trPr>"
        )
        tcs = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>{para(c, bold=n == 0)}</w:tc>'
            for c, w in zip(cells, widths, strict=True)
        )
        out.append(f"<w:tr>{trpr}{tcs}</w:tr>")
    out.append("</w:tbl>")
    return "".join(out) + blank()


def plain_table(rows: list[tuple[list[str], int]], widths: list[int]) -> str:
    """ตารางไม่มีเส้น (ใช้จัดสารบัญ) · แต่ละแถว = (ข้อความแต่ละช่อง, จำนวนช่องที่ช่องแรกกินรวม)"""
    nil = "".join(
        f'<w:{s} w:val="nil"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = [
        f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
        f"<w:tblBorders>{nil}</w:tblBorders>"
        f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="0" w:type="dxa"/>'
        f'<w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
    ]
    for cells, span in rows:
        tcs, c = [], 0
        for k, text in enumerate(cells):
            n = span if k == 0 else 1
            w = sum(widths[c : c + n])
            gs = f'<w:gridSpan w:val="{n}"/>' if n > 1 else ""
            jc = "right" if c + n == len(widths) else ""
            tcs.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{gs}</w:tcPr>'
                f"{para(text, jc=jc)}</w:tc>"
            )
            c += n
        out.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{''.join(tcs)}</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


# ---------- เลข/ขีดอัตโนมัติ (numbering.xml) ----------


class Numbering:
    """รายการแต่ละชุดในร่าง = รายการอัตโนมัติชุดใหม่ของ Word (เริ่มนับจากเลขแรกที่เขียนในร่าง)"""

    DEC, BUL = 9001, 9002  # abstractNumId ที่เพิ่มเอง (ไม่ชนของแม่แบบ)

    def __init__(self) -> None:
        self.nums: list[str] = []
        self.next_id = 9001

    def new(self, bullet: bool, start: int = 1) -> int:
        nid = self.next_id
        self.next_id += 1
        absid = self.BUL if bullet else self.DEC
        ovr = (
            ""
            if bullet
            else (f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="{start}"/></w:lvlOverride>')
        )
        self.nums.append(f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{absid}"/>{ovr}</w:num>')
        return nid

    def merge(self, xml: str) -> str:
        def lvl(i: int, fmt: str, text: str) -> str:
            left = 1080 + 360 * i
            return (
                f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
                f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/><w:pPr>'
                f'<w:ind w:left="{left}" w:hanging="360"/></w:pPr>{rpr()}</w:lvl>'
            )

        dec = "".join(lvl(i, "decimal", f"%{i + 1}.") for i in range(3))
        bul = "".join(lvl(i, "bullet", "-") for i in range(3))
        multi = '<w:multiLevelType w:val="multilevel"/>'
        absn = (
            f'<w:abstractNum w:abstractNumId="{self.DEC}">{multi}{dec}</w:abstractNum>'
            f'<w:abstractNum w:abstractNumId="{self.BUL}">{multi}{bul}</w:abstractNum>'
        )
        m = re.search(r"<w:num\b", xml)  # abstractNum ต้องมาก่อน num ทั้งหมด
        at = m.start() if m else xml.index("</w:numbering>")
        xml = xml[:at] + absn + xml[at:]
        return xml.replace("</w:numbering>", "".join(self.nums) + "</w:numbering>")


# ---------- รูป ----------

EMU = 914400  # หน่วยของ Word: 914400 ต่อ 1 นิ้ว
MAX_W, MAX_H = 5.5, 7.0  # ขนาดรูปสูงสุดในหน้า (นิ้ว) · พื้นที่พิมพ์กว้าง 5.77 นิ้ว


class Media:
    """รูปที่ใส่ในไฟล์หนึ่งไฟล์ · แต่ละรูปได้ rId ของตัวเองใน document.xml.rels"""

    def __init__(self) -> None:
        self.files: list[tuple[str, Path]] = []

    def add(self, path: Path) -> str:
        rid = f"rIdAipcImg{len(self.files) + 1}"
        self.files.append((rid, path))
        return rid


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path}: รองรับเฉพาะรูป PNG")
    return struct.unpack(">II", head[16:24])


def image_para(rid: str, path: Path, n: int) -> str:
    """ย่อหน้ากลางหน้าที่มีรูปหนึ่งรูป · ย่อให้พอดีพื้นที่พิมพ์โดยคงสัดส่วน · ติดกับชื่อรูปบรรทัดถัดไป"""
    px_w, px_h = png_size(path)
    scale = min(MAX_W / (px_w / 96), MAX_H / (px_h / 96), 1.0)
    cx, cy = int(px_w / 96 * scale * EMU), int(px_h / 96 * scale * EMU)
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    pic = "http://schemas.openxmlformats.org/drawingml/2006/picture"
    drawing = (
        f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{9000 + n}" name="รูป {n}"/>'
        f'<a:graphic xmlns:a="{a}"><a:graphicData uri="{pic}"><pic:pic xmlns:pic="{pic}">'
        f'<pic:nvPicPr><pic:cNvPr id="{9000 + n}" name="{escape(path.name)}"/>'
        f"<pic:cNvPicPr/></pic:nvPicPr>"
        f'<pic:blipFill><a:blip r:embed="{rid}"/>'
        f"<a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        f"</a:graphicData></a:graphic></wp:inline></w:drawing>"
    )
    ppr = '<w:keepNext/><w:spacing w:before="240" w:after="120" w:line="240" w:lineRule="auto"/>'
    return f'<w:p><w:pPr>{ppr}<w:jc w:val="center"/></w:pPr><w:r>{drawing}</w:r></w:p>'


# ---------- แปลงร่างบท ----------


def clean(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", text)  # ลิงก์ = เหลือข้อความ
    return re.sub(r"ภาพที่(?=\s*\d)", "รูปที่", text).strip()  # แม่แบบใช้คำว่า "รูปที่"


CAPTION = re.compile(r"(ตารางที่|ภาพที่|รูปที่)\s*([0-9ก-ฮ]+\.\d+)\s*(.*)")
LIST = re.compile(r"(\s*)(?:([-*])|(\d+)[.)])\s+(.+)")


def convert(md: str, numbering: Numbering, media: Media | None = None) -> tuple[str, list[dict]]:
    """Markdown → XML ของเนื้อหา และรายการหัวข้อ/ตาราง/รูปสำหรับสารบัญ"""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.splitlines()
    out: list[str] = []
    toc: list[dict] = []
    list_id: dict[tuple[bool, int], int] = {}  # (เป็นขีด?, ระดับ) → numId ของรายการชุดปัจจุบัน
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not LIST.match(line) and line.strip():
            list_id.clear()  # ข้อความอื่นคั่น = รายการชุดถัดไปเริ่มนับใหม่
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            kind = line[3:].strip() or "โค้ด"
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            if kind != "mermaid":  # โค้ด Mermaid = ต้นฉบับของรูป (render_figures.py) ไม่พิมพ์ลงเล่ม
                out.append(para(f"[{kind}]", italic=True, jc="center", before=120))
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
            title = clean(m.group(2))
            out.append(para(m.group(1), size=40, bold=True, jc="center"))
            out.append(para(title, size=40, bold=True, jc="center"))
            toc.append(
                {
                    "kind": "chapter",
                    "num": m.group(1).split()[-1],
                    "text": title,
                    "find": m.group(1),
                }
            )
        elif m := re.match(r"#\s+(.+)", line):
            title = clean(m.group(1))
            out.append(para(title, size=40, bold=True, jc="center") + blank())
            toc.append({"kind": "part", "text": title, "find": title})
        elif m := re.match(r"##\s+(.+)", line):
            text = clean(m.group(1))
            out.append(blank() + para(text, bold=True, keep=True))
            toc.append({"kind": "section", "text": text, "find": text})
        elif m := re.match(r"###+\s+(.+)", line):
            out.append(para(clean(m.group(1)), bold=True, left=360, keep=True))
        elif m := LIST.match(line):
            depth = min(len(m.group(1)) // 2, 2)
            bullet = m.group(2) is not None
            key = (bullet, depth)
            if key not in list_id:
                list_id[key] = numbering.new(bullet, 1 if bullet else int(m.group(3)))
            out.append(para(clean(m.group(4)), num=(list_id[key], depth), jc="thaiDistribute"))
        elif (m := re.match(r"!\[(.+)\]\((.+)\)\s*$", line)) and media is not None:
            path = (DRAFT / m.group(2)).resolve()
            if not path.exists():
                raise SystemExit(f"ไม่พบรูป {path} (รัน docs/thesis/tools/render_figures.py ก่อน?)")
            out.append(image_para(media.add(path), path, len(media.files)))
            cap = CAPTION.match(clean(m.group(1)))
            out.append(
                caption_fig(cap.group(2), cap.group(3))
                if cap
                else para(clean(m.group(1)), jc="center")
            )
            if cap:
                toc.append(
                    {
                        "kind": "figure",
                        "num": cap.group(2),
                        "text": cap.group(3),
                        "find": f"รูปที่ {cap.group(2)}",
                    }
                )
        elif line.startswith("[ภาพที่") or line.startswith("[รูปที่"):
            inner = clean(line.strip()[1:-1] if line.strip().endswith("]") else line.strip()[1:])
            name, _, note = inner.partition(" — ")
            cap = CAPTION.match(name)
            out.append(
                para(
                    f"[{note or 'ต้องเติม: ใส่รูป'}]",
                    italic=True,
                    jc="center",
                    before=240,
                    after=120,
                    keep=True,
                )
            )
            out.append(caption_fig(cap.group(2), cap.group(3)) if cap else para(name, jc="center"))
            if cap:
                toc.append(
                    {
                        "kind": "figure",
                        "num": cap.group(2),
                        "text": cap.group(3),
                        "find": f"รูปที่ {cap.group(2)}",
                    }
                )
        elif (cap := CAPTION.match(clean(line))) and (
            cap.group(1) != "ตารางที่" or next_is_table(lines, i)
        ):
            if cap.group(1) == "ตารางที่":
                out.append(
                    para(
                        spans=[(f"ตารางที่ {cap.group(2)}", True), (f" {cap.group(3)}", False)],
                        keep=True,
                    )
                )
                toc.append(
                    {
                        "kind": "table",
                        "num": cap.group(2),
                        "text": cap.group(3),
                        "find": f"ตารางที่ {cap.group(2)}",
                    }
                )
            else:
                out.append(caption_fig(cap.group(2), cap.group(3)))
                toc.append(
                    {
                        "kind": "figure",
                        "num": cap.group(2),
                        "text": cap.group(3),
                        "find": f"รูปที่ {cap.group(2)}",
                    }
                )
        elif m := re.match(r"\[(\d+)\]\t(.+)", line):  # รายการบรรณานุกรม = เยื้องแขวน
            out.append(
                para(f"[{m.group(1)}]\t{clean(m.group(2))}", left=720, hanging=720, after=120)
            )
        else:
            out.append(para(clean(line), first=720, jc="thaiDistribute"))
        i += 1
    return "".join(out), toc


def next_is_table(lines: list[str], i: int) -> bool:
    """บรรทัด "ตารางที่ N.M …" เป็นชื่อตารางก็ต่อเมื่อบรรทัดถัดไปที่ไม่ว่างคือตาราง (ไม่ใช่ประโยคที่อ้างถึงตาราง)"""
    rest = (x for x in lines[i + 1 :] if x.strip())
    return next(rest, "").startswith("|")


def caption_fig(num: str, name: str) -> str:
    return para(spans=[(f"รูปที่ {num}", True), (f" {name}", False)], jc="center", after=240)


# ---------- ปก / บทคัดย่อ (เขียนตามแม่แบบ) ----------


def cover_body(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    titles = [clean(t) for t in re.findall(r"^#\s+(.+)$", md, re.M)] or [TODO]
    year = re.search(r"^ปีการศึกษา\s*(.+)$", md, re.M)
    year_line = f"ปีการศึกษา {clean(year.group(1)) if year else TODO}"
    name_tabs = (1980, 3240, 5040)
    name_line = "\t[ชื่อ]\t[นามสกุล]\t[รหัสนักศึกษา]"

    # กล่องข้อความมุมขวาบนของแม่แบบ = ย่อหน้าแบบกรอบลอย (frame) เหนือขอบบน ไม่ดันชื่อเรื่องลง
    frame = (
        '<w:framePr w:w="4320" w:wrap="around" w:vAnchor="page" w:hAnchor="margin"'
        ' w:xAlign="right" w:y="1100"/>'
    )
    project_no = para(f"โครงงาน เลขที่ {TODO}", bold=True, jc="right").replace(
        "<w:pPr>", "<w:pPr>" + frame, 1
    )

    def title_block() -> str:
        return "".join(para(t, size=40, bold=True, jc="center") for t in titles)

    def c18(text: str, bold: bool = True) -> str:
        return para(text, size=36, bold=bold, jc="center")

    page1 = (
        project_no
        + title_block()
        + blank(36, 5)
        + para(name_line, size=36, bold=True, tabs=name_tabs)
        + blank(36, 5)
        + c18("วิทยาศาสตรบัณฑิต")
        + c18("สาขาวิชาวิทยาการคอมพิวเตอร์")
        + blank(36, 5)
        + c18("คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้")
        + c18(year_line)
    )
    page2 = (
        title_block()
        + blank(36, 5)
        + para(name_line, size=36, bold=True, tabs=name_tabs)
        + blank(36, 4)
        + c18("โครงงานนี้นำเสนอต่อสาขาวิชาวิทยาการคอมพิวเตอร์เพื่อเป็นส่วนหนึ่ง")
        + c18("ของการศึกษาตามหลักสูตรปริญญา")
        + c18("วิทยาศาสตรบัณฑิต")
        + c18("สาขาวิชาวิทยาการคอมพิวเตอร์")
        + blank(36, 3)
        + c18("คณะวิทยาศาสตร์ มหาวิทยาลัยแม่โจ้")
        + c18(year_line)
    )
    dots = "." * 80
    signers = [
        ("ประธานกรรมการ", "[ต้องเติม: ชื่อประธานกรรมการ]"),
        ("กรรมการ", "[ต้องเติม: ชื่อกรรมการ]"),
        ("กรรมการ", "[ต้องเติม: ชื่อกรรมการ]"),
    ]
    sign = "".join(
        blank(36) + para(f"\t{dots}{role}", size=36, tabs=(1440,)) + c18(who, bold=False)
        for role, who in signers
    )
    page3 = (
        title_block()
        + blank(36, 2)
        + para(name_line, size=36, tabs=name_tabs)
        + blank(36, 2)
        + c18("โครงงานนี้ได้รับการพิจารณาอนุมัติให้นับเป็นส่วนหนึ่งของการศึกษา", bold=False)
        + c18("ตามหลักสูตรปริญญาวิทยาศาสตรบัณฑิต", bold=False)
        + c18("สาขาวิชาวิทยาการคอมพิวเตอร์", bold=False)
        + blank(36)
        + para("คณะกรรมการสอบโครงงาน", size=36)
        + sign
        + blank(36)
        + c18(year_line, bold=False)
    )
    return page1 + PAGE_BREAK + page2 + PAGE_BREAK + page3


INFO_SKIP = re.compile(
    r"(ชื่อโครงงาน|ผู้จัดทำ|อาจารย์ที่ปรึกษา|สาขาวิชา|Project title|Author|Advisor|Program)[^:]{0,20}:"
)


def ack_body() -> str:
    """กิตติกรรมประกาศจาก draft/acknowledgement.md · บรรทัด "ผู้จัดทำ: ชื่อ" = ชื่อชิดขวาท้ายข้อความ"""
    src = DRAFT / "acknowledgement.md"
    md = re.sub(
        r"<!--.*?-->", "", src.read_text(encoding="utf-8") if src.exists() else "", flags=re.S
    )
    out = [para("กิตติกรรมประกาศ", size=40, bold=True, jc="center"), blank()]
    signer = "[ต้องเติม: ชื่อ นามสกุล]"
    for line in (x.strip() for x in md.splitlines()):
        if not line or line.startswith("#"):
            continue
        if line.startswith("ผู้จัดทำ:"):
            signer = line.split(":", 1)[1].strip()
        else:
            out.append(para(clean(line), first=720, jc="thaiDistribute"))
    if len(out) == 2:
        out.append(para("[ต้องเติม: กิตติกรรมประกาศ]", first=720, jc="thaiDistribute"))
    return "".join(out) + blank(32, 3) + para(signer, jc="right")


def abstract_body(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    parts = re.split(r"^#\s+.+$", md, flags=re.M)
    th, en = (parts[1], parts[2]) if len(parts) >= 3 else (md, "")
    tabs = (3060, 5940)

    def info(rows: list[tuple[str, list[str]]]) -> str:
        out = []
        for label, values in rows:
            for k, v in enumerate(values):
                head = (label, True) if k == 0 else ("", False)
                out.append(para(spans=[head, (f"\t{v}", False)], tabs=tabs))
            out.append(blank())
        return "".join(out)

    def body(text: str, keyword_label: str) -> str:
        out = []
        for line in (x.strip() for x in text.splitlines()):
            if not line or INFO_SKIP.match(line):
                continue
            if line.startswith(keyword_label):
                rest = line[len(keyword_label) :].lstrip(": ")
                out.append(
                    para(
                        spans=[(keyword_label + " ", True), (clean(rest), False)],
                        first=720,
                        jc="thaiDistribute",
                    )
                )
            else:
                out.append(para(clean(line), first=720, jc="thaiDistribute"))
        return "".join(out)

    ack = ack_body()
    thai = (
        info(
            [
                ("หัวข้อโครงงาน", ["[ต้องเติม: ชื่อโครงงานภาษาไทย]"]),
                ("ผู้เขียน", ["[ต้องเติม: ชื่อ นามสกุล]\tรหัสนักศึกษา [ต้องเติม]"]),
                ("ปริญญา", ["วิทยาศาสตรบัณฑิต (วิทยาการคอมพิวเตอร์)"]),
                (
                    "คณะกรรมการที่ปรึกษาโครงงาน",
                    [
                        "[ต้องเติม: ชื่อ]\tประธานกรรมการ",
                        "[ต้องเติม: ชื่อ]\tกรรมการ",
                        "[ต้องเติม: ชื่อ]\tกรรมการ",
                    ],
                ),
            ]
        )
        + para("บทคัดย่อ", size=40, bold=True, jc="center")
        + body(th, "คำสำคัญ")
    )
    eng = (
        info(
            [
                ("Project Name", ["[ต้องเติม: English project title]"]),
                ("Author", ["[ต้องเติม: name]\t, Student ID [ต้องเติม]"]),
                ("Degree", ["Bachelor of Science (Computer Science)"]),
                (
                    "Project Advisory Committee",
                    [
                        "[ต้องเติม: name]\t, Chairperson",
                        "[ต้องเติม: name]\t, Committee",
                        "[ต้องเติม: name]\t, Committee",
                    ],
                ),
            ]
        )
        + para("ABSTRACT", size=40, bold=True, jc="center")
        + body(en, "Keywords")
    )
    return ack + PAGE_BREAK + thai + PAGE_BREAK + eng


# ---------- สารบัญ ----------

LINES_PER_PAGE = 22  # จำนวนบรรทัดต่อหน้าของสารบัญ (ตัวอักษร 16 · ขอบบน 2 นิ้ว ล่าง 1 นิ้ว · หักหัวหน้าแล้ว)
CHARS_PER_LINE = 70  # ชื่อหัวข้อยาวกว่านี้ (นับเฉพาะตัวที่กินที่) = ขึ้นบรรทัดใหม่ในช่องกลาง


def row_lines(row: tuple[list[str], int]) -> int:
    width = len(re.sub(r"[ัิ-ฺ็-๎]", "", max(row[0], key=len)))  # สระบน/ล่าง วรรณยุกต์ไม่กินที่
    return 1 + width // CHARS_PER_LINE


def thai_page(n: int) -> str:
    return THAI_LETTERS[n - 1] if 1 <= n <= len(THAI_LETTERS) else "x"


def toc_pages(
    title: str, head: list[str], rows: list[tuple[list[str], int]], widths: list[int]
) -> list[str]:
    """แบ่งแถวเป็นหน้า · หน้าถัดไปมีหัว "(ต่อ)" ตามแม่แบบ · ไม่ขึ้นหน้าใหม่ด้วยแถวว่าง"""
    pages, cur, used = [], [], 0
    for row in rows:
        if used + row_lines(row) > LINES_PER_PAGE:
            pages.append(cur)
            cur, used = [], 0
        if not cur and not any(row[0]):
            continue
        cur.append(row)
        used += row_lines(row)
    if cur:
        pages.append(cur)
    out = []
    for n, chunk in enumerate(pages or [[]]):
        name = title if n == 0 else f"{title} (ต่อ)"
        top = (
            para(name, size=40, bold=True, jc="center") + blank() + head_row(head, widths) + blank()
        )
        out.append(top + (plain_table(chunk, widths) if chunk else ""))
    return out


def head_row(head: list[str], widths: list[int]) -> str:
    """แถว "ตาราง … หน้า" (หนา) · ใช้แท็บชิดขวาที่ขอบขวาของพื้นที่พิมพ์"""
    right = sum(widths)
    p = para(spans=[(head[0], True), ("\t" + head[-1], True)])
    return p.replace(
        "<w:spacing", f'<w:tabs><w:tab w:val="right" w:pos="{right}"/></w:tabs><w:spacing', 1
    )


def contents_body(tocs: list[tuple[str, list[dict]]], pages: dict, front: dict) -> tuple[str, int]:
    def page_of(item: dict, file: str) -> str:
        info = pages.get(file)
        if not info:
            return "x"
        for text, pg in info["paras"]:
            if text.startswith(item["find"]):
                return str(info["start"] + pg - 1)
        return "x"

    toc_rows: list[tuple[list[str], int]] = []
    tbl_rows: list[tuple[list[str], int]] = []
    fig_rows: list[tuple[list[str], int]] = []
    for file, items in tocs:
        for it in items:
            pg = page_of(it, file)
            if it["kind"] == "chapter":
                toc_rows += [([""], 3), ([f"บทที่ {it['num']}", it["text"], pg], 1)]
            elif it["kind"] == "part":
                toc_rows += [([""], 3), ([it["text"], pg], 2)]
            elif it["kind"] == "section":
                toc_rows.append((["", it["text"], pg], 1))
            elif it["kind"] == "table":
                tbl_rows.append(([it["num"], it["text"], pg], 1))
            elif it["kind"] == "figure":
                fig_rows.append(([it["num"], it["text"], pg], 1))

    w_toc, w_list = [945, 6600, 761], [720, 6825, 761]
    # จำนวนหน้าของสารบัญ/สารบัญตาราง ต้องรู้ก่อน เพื่อใส่เลขหน้าของสารบัญตาราง/ภาพในสารบัญ
    n_toc = len(toc_pages("สารบัญ", ["", "หน้า"], [(["-", "-"], 2)] * 5 + toc_rows, w_toc))
    n_tbl = len(toc_pages("สารบัญตาราง", ["ตาราง", "หน้า"], tbl_rows, w_list))
    lists_start = front["contents"] + n_toc
    head_rows = [
        (["กิตติกรรมประกาศ", thai_page(front["ack"])], 2),
        (["บทคัดย่อภาษาไทย", thai_page(front["th"])], 2),
        (["บทคัดย่อภาษาอังกฤษ", thai_page(front["en"])], 2),
        (["สารบัญตาราง", thai_page(lists_start)], 2),
        (["สารบัญภาพ", thai_page(lists_start + n_tbl)], 2),
    ]
    toc_pg = toc_pages("สารบัญ", ["", "หน้า"], head_rows + toc_rows, w_toc)
    tbl_pg = toc_pages("สารบัญตาราง", ["ตาราง", "หน้า"], tbl_rows, w_list)
    fig_pg = toc_pages("สารบัญภาพ", ["รูป", "หน้า"], fig_rows, w_list)
    all_pages = toc_pg + tbl_pg + fig_pg
    return PAGE_BREAK.join(all_pages), len(all_pages)


# ---------- เขียนไฟล์ .docx ----------


def template(word_dir: Path, prefix: str) -> Path:
    found = sorted((word_dir / TEMPLATE_DIR).glob(f"{prefix}-*.docx"))
    if not found:
        raise SystemExit(f"ไม่พบแม่แบบ {prefix}-*.docx ใน {word_dir / TEMPLATE_DIR}")
    return found[0]


def build(
    tpl: Path,
    body: str,
    target: Path,
    *,
    page_start: int | None = None,
    numbering: Numbering | None = None,
    media: Media | None = None,
) -> None:
    with zipfile.ZipFile(tpl) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    sect = re.findall(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)[-1]
    if page_start is not None:
        if "<w:pgNumType" in sect:
            sect = re.sub(r'(<w:pgNumType[^>]*w:start=")\d+', rf"\g<1>{page_start}", sect)
        else:
            sect = re.sub(r"(<w:pgMar[^>]*/>)", rf'\1<w:pgNumType w:start="{page_start}"/>', sect)
    head = doc[: doc.index("<w:body>") + len("<w:body>")]
    new = head + body + sect + "</w:body></w:document>"
    used = set(re.findall(r'r:(?:id|embed)="([^"]+)"', body + sect))
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with zipfile.ZipFile(tpl) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
        dropped = set()
        for rel in re.findall(r"<Relationship [^>]*/>", rels):  # รูปประกอบคำอธิบายของแม่แบบ = ไม่ใช้
            rid = re.search(r'Id="([^"]+)"', rel).group(1)
            if "/image" in rel and rid not in used:
                rels = rels.replace(rel, "")
                dropped.add("word/" + re.search(r'Target="([^"]+)"', rel).group(1))
        images = media.files if media else []
        new_rels = "".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/image" Target="media/aipc-{n}.png"/>'
            for n, (rid, _) in enumerate(images, 1)
        )
        rels = rels.replace("</Relationships>", new_rels + "</Relationships>")
        for n, (_, path) in enumerate(images, 1):
            zout.write(path, f"word/media/aipc-{n}.png")
        for item in zin.infolist():
            if item.filename in dropped:
                continue
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            elif (
                item.filename == "[Content_Types].xml" and images and b'Extension="png"' not in data
            ):
                data = data.replace(
                    b"<Default ", b'<Default Extension="png" ContentType="image/png"/><Default ', 1
                )
            elif item.filename == "word/numbering.xml" and numbering:
                data = numbering.merge(data.decode("utf-8")).encode("utf-8")
            elif item.filename == "docProps/core.xml":  # ชื่อผู้เขียน/ผู้แก้ล่าสุดของแม่แบบ = ล้างออก
                data = re.sub(
                    rb"(<(?:dc:creator|cp:lastModifiedBy|dc:title)>)[^<]*", rb"\g<1>", data
                )
            zout.writestr(item, data)
    shutil.move(tmp, target)


def generate(word_dir: Path, out: Path) -> None:
    pages_file = out / PAGES_JSON
    pages = json.loads(pages_file.read_text(encoding="utf-8-sig")) if pages_file.exists() else {}

    build(
        template(word_dir, "01"),
        cover_body((DRAFT / "cover.md").read_text(encoding="utf-8")),
        out / "01-Cover.docx",
    )
    print("cover.md → 01-Cover.docx")
    build(
        template(word_dir, "02"),
        abstract_body((DRAFT / "abstract.md").read_text(encoding="utf-8")),
        out / "02-Abstract.docx",
        page_start=3,
    )
    print("abstract.md → 02-Abstract.docx")

    # เลขหน้าเริ่มของแต่ละบท = ต่อจากบทก่อนหน้า (ต้องมีผลนับหน้าจาก Word)
    start = 1
    tocs = []
    for draft, name in CHAPTERS:
        src = DRAFT / draft
        if not src.exists():
            print(f"ข้าม {draft} (ยังไม่มีร่าง)")
            continue
        numbering = Numbering()
        media = Media()
        body, toc = convert(src.read_text(encoding="utf-8"), numbering, media)
        build(
            template(word_dir, "04"),
            body,
            out / name,
            page_start=start,
            numbering=numbering,
            media=media,
        )
        if name in pages:
            pages[name]["start"] = start
            start += pages[name]["pages"]
        tocs.append((name, toc))
        print(f"{draft} → {name}")

    ab = pages.get("02-Abstract.docx", {"paras": [], "pages": 3})

    def ab_page(prefix: str, default: int) -> int:
        return next((3 + pg - 1 for text, pg in ab["paras"] if text.startswith(prefix)), default)

    front = {
        "ack": 3,
        "th": ab_page("บทคัดย่อ", 4),
        "en": ab_page("ABSTRACT", 5),
        "contents": 3 + ab["pages"],
    }
    body, _ = contents_body(tocs, pages, front)
    build(template(word_dir, "03"), body, out / "03-Contents.docx", page_start=front["contents"])
    print("(หัวข้อทุกบท) → 03-Contents.docx" + ("" if pages else " · เลขหน้า = x (ยังไม่ได้ให้ Word นับ)"))


def count_pages(out: Path) -> None:
    """ให้ Microsoft Word เปิดแต่ละไฟล์ นับหน้า และจดว่าย่อหน้าไหนอยู่หน้าใด → _pages.json"""
    script = TOOLS / "pages.ps1"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(out)],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--word-dir",
        type=Path,
        default=ROOT / "word",
        help="โฟลเดอร์ที่มี 'Template รหัส 66' (ค่าเริ่มต้น word/)",
    )
    ap.add_argument("--with-word", action="store_true", help="ให้ Word นับหน้าแล้วสร้างซ้ำพร้อมเลขหน้าจริง")
    args = ap.parse_args()
    out = args.word_dir / "ai-pc"
    if args.with_word:
        (out / PAGES_JSON).unlink(missing_ok=True)
        generate(args.word_dir, out)
        count_pages(out)
    generate(args.word_dir, out)


if __name__ == "__main__":
    main()
