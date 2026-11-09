"""แชร์สกิล (การ์ด 0080) · 2 ทาง · ไม่ว่าทางไหน ผู้รับต้องผ่านด่านและหน้าตรวจก่อนติดตั้งเหมือนไฟล์ทุกครั้ง.

QR ทั้งไฟล์ (ไม่มีเซิร์ฟเวอร์ ไม่ออกเน็ต):
  ไฟล์ .md ของสกิล → บีบอัด (zlib) → base64 → ข้อความ "AIPC1:…" → รูป QR
  (OpenCV มีตัวสร้าง/อ่าน QR อยู่แล้ว · ไม่เพิ่ม dependency)
  QR ใส่ได้ ~2,300 ตัวอักษร (ระดับแก้ผิด M) · สกิลทั่วไป ~1,800 ไบต์ บีบแล้วเหลือ ~800 ตัวอักษร
เลข 8 หลัก (รอบ 2 · ต้องมีเซิร์ฟเวอร์และผู้ใช้กดยืนยันว่าให้ไฟล์ออกจากเครื่อง):
  ฝากไฟล์ไว้ 24 ชม. ได้เลขกลับมา · แสดงเลขคู่กับ QR เล็ก ๆ ที่มีแค่ "AIPC2:<เลข>" จึงสแกนง่าย
  ตัวเซิร์ฟเวอร์อยู่ที่ server/share-worker/
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import urllib.error
import urllib.request
import zlib
from pathlib import Path

PREFIX = "AIPC1:"  # QR ทั้งไฟล์ · เปลี่ยนวิธีเข้ารหัสเมื่อไหร่ = รุ่นใหม่
CODE_PREFIX = "AIPC2:"  # QR ของเลข 8 หลัก
MAX_PAYLOAD = 2300  # ตัวอักษรใน QR (ความจุสูงสุดของ QR รุ่น 40 ระดับ M ≈ 2,331 ไบต์)
MAX_MD = 64 * 1024  # แตกไฟล์ได้ไม่เกินนี้ (กันข้อมูลที่บีบมาให้แตกเป็นไฟล์ใหญ่มาก)
MAX_UPLOAD = 16 * 1024  # เท่าที่เซิร์ฟเวอร์รับ
SCALE = 8  # 1 จุดของ QR = 8 พิกเซล
TIMEOUT_S = 15
USER_AGENT = "aipc-skill-share/1"  # Cloudflare ปฏิเสธชื่อเริ่มต้นของ Python-urllib (error 1010)
# ที่อยู่เซิร์ฟเวอร์ฝากสกิล · ว่าง = ยังไม่ได้ตั้ง (หน้าจอซ่อนทางเลข · QR ทั้งไฟล์ยังใช้ได้)
SERVER_URL = "https://aipc-thesis-2026.aipc-thesis-2026.workers.dev"


class ShareError(ValueError):
    """เหตุผลภาษาคน."""


class NotSent(ShareError):
    """ไม่ได้ส่งอะไรออกจากเครื่อง (ไม่มีเซิร์ฟเวอร์ · มีความลับ · ใหญ่เกิน)."""


def server_url() -> str:
    """ที่อยู่เซิร์ฟเวอร์ · AIPC_CLOUD=0 (ตัววัดและการทดสอบ) = ไม่ออกเน็ต."""
    if os.environ.get("AIPC_CLOUD", "1") == "0":
        return ""
    return os.environ.get("AIPC_SHARE_URL", SERVER_URL).rstrip("/")


def encode(skill_md: str) -> str:
    packed = base64.urlsafe_b64encode(zlib.compress(skill_md.encode("utf-8"), 9)).decode("ascii")
    text = PREFIX + packed
    if len(text) > MAX_PAYLOAD:
        raise ShareError(
            f"สกิลนี้ใหญ่เกิน QR 1 รูป ({len(text)} จาก {MAX_PAYLOAD} ตัวอักษร) · ใช้ “ส่งออกเป็นไฟล์” แทน"
        )
    return text


def decode(text: str) -> str:
    if not text.startswith(PREFIX):
        raise ShareError("QR นี้ไม่ใช่สกิลของผู้ช่วย")
    try:
        # validate=True: ตัวอักษรนอกชุด base64 = เสีย (ค่าเริ่มต้นของ Python ทิ้งเงียบ ๆ แล้วได้ข้อมูลว่าง)
        raw = base64.b64decode(text[len(PREFIX) :].encode("ascii"), altchars=b"-_", validate=True)
        d = zlib.decompressobj()
        md = d.decompress(raw, MAX_MD)
        if d.unconsumed_tail:
            raise ShareError("สกิลใน QR ใหญ่ผิดปกติ · ไม่อ่านต่อ")
        if not md or not d.eof:
            raise ValueError("ข้อมูลไม่ครบ")
        return md.decode("utf-8")
    except (binascii.Error, zlib.error, UnicodeError, ValueError) as e:
        if isinstance(e, ShareError):
            raise
        raise ShareError("อ่าน QR ได้แต่ข้อมูลเสีย · ให้เพื่อนสร้าง QR ใหม่") from e


def _qr_bitmap(text: str):
    """รูป QR (numpy · ขาวดำ · มีขอบขาว 4 จุดตามมาตรฐาน)."""
    import cv2

    p = cv2.QRCodeEncoder_Params()
    p.correction_level = cv2.QRCODE_ENCODER_CORRECT_LEVEL_M  # แก้ผิดได้ ~15% (ถ่ายจากจอ/ภาพเบลอเล็กน้อย)
    img = cv2.QRCodeEncoder.create(p).encode(text)
    img = cv2.resize(img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_NEAREST)
    pad = 4 * SCALE
    return cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)


def qr_image(skill_md: str):
    return _qr_bitmap(encode(skill_md))


def _write_bitmap(img, path: Path) -> None:
    import cv2

    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ShareError("สร้างรูป QR ไม่ได้")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.tobytes())  # ไม่ใช้ cv2.imwrite: วินโดวส์เขียน path ภาษาไทยไม่ได้


def write_png(skill_md: str, path: Path) -> None:
    _write_bitmap(qr_image(skill_md), path)


def write_code_png(code: str, path: Path) -> None:
    """รูป QR ของเลข 8 หลัก · มีแค่เลข จึงเล็กกว่า QR ทั้งไฟล์มาก."""
    _write_bitmap(_qr_bitmap(CODE_PREFIX + clean_code(code)), path)


def read_image_text(path: Path) -> str:
    """รูปที่มี QR → ข้อความใน QR · ไม่เจอ = ShareError."""
    import cv2
    import numpy as np

    from aipc.vision import qr

    data = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ShareError("เปิดรูปนี้ไม่ได้")
    text = qr.read_frame(img)
    if not text:
        raise ShareError("ไม่พบ QR ในรูปนี้ · ถ่ายให้เห็น QR ทั้งรูป ชัด ๆ แล้วลองใหม่")
    return text


def resolve(text: str, url: str | None = None, opener=None) -> str:
    """ข้อความใน QR → ไฟล์ .md · QR ทั้งไฟล์ถอดได้เลย · QR ของเลขต้องไปโหลดจากเซิร์ฟเวอร์."""
    if text.startswith(CODE_PREFIX):
        return download(text[len(CODE_PREFIX) :], url, opener)
    return decode(text)


def read_image(path: Path, url: str | None = None, opener=None) -> str:
    """รูปที่มี QR → ไฟล์ .md ของสกิล · ไม่เจอ/ไม่ใช่ = ShareError."""
    return resolve(read_image_text(path), url, opener)


_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def clean_code(text: str) -> str:
    """เลขที่ผู้ใช้พิมพ์ ("1234 5678" · เลขไทยก็ได้) → 8 หลักติดกัน · ผิดรูปแบบ = ShareError."""
    code = re.sub(r"[\s-]", "", text.translate(_THAI_DIGITS))
    if not re.fullmatch(r"[0-9]{8}", code):
        raise ShareError("เลขแชร์สกิลต้องเป็นตัวเลข 8 หลัก")
    return code


def pretty_code(code: str) -> str:
    return f"{code[:4]} {code[4:]}"


def _reply_error(e: urllib.error.HTTPError) -> str:
    if e.code == 404:
        return "ไม่พบเลขนี้ หรือหมดอายุแล้ว (เก็บไว้ 24 ชั่วโมง)"
    if e.code == 429:
        return "ลองหลายครั้งเกินไป หรือเซิร์ฟเวอร์ถึงโควตาของวันนี้แล้ว · รอสักชั่วโมงแล้วลองใหม่"
    if e.code == 413:
        return "สกิลนี้ใหญ่เกินกว่าจะฝากได้ · ใช้ “ส่งออก” เป็นไฟล์แทน"
    return f"เซิร์ฟเวอร์ตอบผิดพลาด ({e.code}) · แชร์ด้วย QR ทั้งไฟล์แทนได้"


def upload(md: str, url: str | None = None, opener=None) -> str:
    """ฝากไฟล์สกิลแล้วได้เลข 8 หลัก · NotSent = ยังไม่มีอะไรออกจากเครื่อง."""
    from aipc.chat.memory import secret_reason

    base = server_url() if url is None else url.rstrip("/")
    if not base:
        raise NotSent("ยังไม่ได้ตั้งเซิร์ฟเวอร์ฝากสกิล · แชร์ด้วย QR ทั้งไฟล์แทนได้")
    if secret_reason(md):
        raise NotSent("สกิลนี้มีคำเกี่ยวกับรหัสผ่าน OTP หรือเลขบัตร จึงไม่ส่งขึ้นเซิร์ฟเวอร์ · แชร์ด้วย QR ทั้งไฟล์แทนได้")
    body = md.encode("utf-8")
    if len(body) > MAX_UPLOAD:
        raise NotSent("สกิลนี้ใหญ่เกินกว่าจะฝากได้ · ใช้ “ส่งออก” เป็นไฟล์แทน")
    request = urllib.request.Request(
        base + "/v1/skills", data=body, method="POST",
        headers={"Content-Type": "text/markdown; charset=utf-8", "User-Agent": USER_AGENT},
    )  # fmt: skip
    try:
        with (opener or urllib.request.urlopen)(request, timeout=TIMEOUT_S) as reply:
            code = json.loads(reply.read(1024))["code"]
    except urllib.error.HTTPError as e:
        raise ShareError(_reply_error(e)) from e
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ShareError("ส่งไม่สำเร็จ · ตรวจอินเทอร์เน็ต แล้วลองใหม่ หรือแชร์ด้วย QR ทั้งไฟล์") from e
    return clean_code(str(code))


def download(code: str, url: str | None = None, opener=None) -> str:
    """เลข 8 หลัก → ไฟล์ .md (ยังไม่ได้ตรวจ · ผู้เรียกต้องส่งเข้าด่านเสมอ)."""
    code = clean_code(code)
    base = server_url() if url is None else url.rstrip("/")
    if not base:
        raise NotSent("ยังไม่ได้ตั้งเซิร์ฟเวอร์ฝากสกิล")
    request = urllib.request.Request(
        f"{base}/v1/skills/{code}", method="GET", headers={"User-Agent": USER_AGENT}
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=TIMEOUT_S) as reply:
            raw = reply.read(MAX_UPLOAD + 1)
    except urllib.error.HTTPError as e:
        raise ShareError(_reply_error(e)) from e
    except OSError as e:
        raise ShareError("โหลดไม่สำเร็จ · ตรวจอินเทอร์เน็ตแล้วลองใหม่") from e
    if len(raw) > MAX_UPLOAD:
        raise ShareError("ไฟล์จากเซิร์ฟเวอร์ใหญ่ผิดปกติ · ไม่อ่านต่อ")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ShareError("ไฟล์จากเซิร์ฟเวอร์เสีย · ให้เพื่อนส่งใหม่") from e
