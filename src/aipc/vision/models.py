"""โหลดโมเดลใบหน้า 3 ตัวผ่าน OpenCV และตรวจ sha256 ก่อนใช้ทุกครั้ง (การ์ด 0005).

- YuNet: หากล่องหน้า + 5 จุด (ไฟล์อยู่ในแพ็กเกจ)
- MiniFASNet ×2: PAD = บอกว่าหน้าจริงหรือรูป/จอ (ไฟล์อยู่ในแพ็กเกจ · แปลงเองจากต้นฉบับ ดู NOTICE.md)
- SFace: embedding 128 ตัว (37 MB ไม่อยู่ใน git · `python -m aipc.vision.models fetch`)

ไฟล์ไม่ตรง sha256 = ไม่โหลด (ไฟล์เสียหรือถูกเปลี่ยน → ใบหน้าใช้ไม่ได้ ดีกว่าผลผิดเงียบ ๆ · H1 H5)
ที่มาและไลเซนส์ของทุกไฟล์: models/NOTICE.md
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent / "models"


@dataclass(frozen=True)
class ModelFile:
    name: str
    sha256: str
    url: str = ""  # มี = ดาวน์โหลดได้ · ว่าง = มากับแพ็กเกจ


YUNET = ModelFile(
    "face_detection_yunet_2023mar.onnx",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)
FAS_V2 = ModelFile(
    "2.7_80x80_MiniFASNetV2.onnx",
    "314303502333dd72a3a314537a97199a28afd2c3e2099597382886703031b405",
)
FAS_V1SE = ModelFile(
    "4_0_0_80x80_MiniFASNetV1SE.onnx",
    "9cd4527a192dcf41f90e2b2066215daf7867ee34a8a857cdf9e98de60c93355d",
)
SFACE = ModelFile(
    "face_recognition_sface_2021dec.onnx",
    "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx",
)

# รุ่น int8 (quantized) ของ SFace จาก OpenCV Zoo · เล็กกว่า 4 เท่า
# ทดลองว่าเร็วขึ้นบน Pi แค่ไหน (การ์ด 0005 ข้อ 8)
# embedding คนละแบบกับ fp32 → แม่แบบที่ลงทะเบียนด้วยรุ่นหนึ่งใช้กับอีกรุ่นไม่ได้ (store ตรวจ sha256 ให้)
SFACE_INT8 = ModelFile(
    "face_recognition_sface_2021dec_int8.onnx",
    "2b0e941e6f16cc048c20aee0c8e31f569118f65d702914540f7bfdc14048d78a",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec_int8.onnx",
)
SFACE_VARIANTS = {"fp32": SFACE, "int8": SFACE_INT8}


class ModelError(RuntimeError):
    """โมเดลใช้ไม่ได้ (ไม่มีไฟล์ / sha256 ไม่ตรง) · ผู้เรียกต้องบอกผู้ใช้ว่าใบหน้ายังใช้ไม่ได้."""


def download_dir() -> Path:
    """ที่เก็บโมเดลที่ดาวน์โหลด · ตั้งเองได้ด้วย AIPC_MODEL_DIR (เช่น /opt/aipc-v2/models บน Pi)."""
    if os.environ.get("AIPC_MODEL_DIR"):
        return Path(os.environ["AIPC_MODEL_DIR"])
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "aipc" / "models"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate(m: ModelFile) -> Path:
    """หาไฟล์แล้วตรวจ sha256 · ไม่ผ่าน = ModelError."""
    path = (download_dir() if m.url else HERE) / m.name
    if not path.exists():
        hint = " · ดาวน์โหลดด้วย python -m aipc.vision.models fetch" if m.url else ""
        raise ModelError(f"ไม่มีไฟล์โมเดล {path}{hint}")
    got = sha256(path)
    if got != m.sha256:
        raise ModelError(f"ไฟล์โมเดล {m.name} ไม่ตรง sha256 (ได้ {got[:12]}…) · ไฟล์เสียหรือถูกเปลี่ยน")
    return path


def fetch(m: ModelFile = SFACE) -> Path:
    """ดาวน์โหลดลงไฟล์ชั่วคราว ตรวจ sha256 แล้วค่อยย้ายเข้าที่ (ไม่ทิ้งไฟล์ครึ่ง ๆ ไว้ · H1)."""
    dest = download_dir() / m.name
    if dest.exists() and sha256(dest) == m.sha256:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(m.url, tmp)  # noqa: S310 (URL คงที่ในโค้ด ไม่ได้มาจากผู้ใช้ · H8)
    if sha256(tmp) != m.sha256:
        tmp.unlink()
        raise ModelError(f"ดาวน์โหลด {m.name} แล้ว sha256 ไม่ตรง · ไม่ใช้ไฟล์นี้")
    os.replace(tmp, dest)
    return dest


class Detector:
    """YuNet: คืนแถว [x, y, w, h, 5×(x, y), score] ต่อหน้า เรียงจากหน้าใหญ่สุด."""

    def __init__(self, min_score: float = 0.8):
        import cv2

        self._net = cv2.FaceDetectorYN.create(str(locate(YUNET)), "", (320, 320), min_score)
        self._size = (320, 320)

    def detect(self, frame: np.ndarray) -> list[np.ndarray]:
        h, w = frame.shape[:2]
        if (w, h) != self._size:
            self._net.setInputSize((w, h))
            self._size = (w, h)
        _, faces = self._net.detect(frame)
        if faces is None:
            return []
        return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)


class Embedder:
    """SFace: รับหน้าที่ align แล้ว 112×112 (จาก aipc.vision.align.crop) คืนเวกเตอร์ 128 ตัว."""

    def __init__(self, variant: str = "fp32"):
        import cv2

        self.model = SFACE_VARIANTS[variant]
        self._net = cv2.FaceRecognizerSF.create(str(locate(self.model)), "")

    def embed(self, aligned: np.ndarray) -> np.ndarray:
        return self._net.feature(aligned).reshape(-1).astype(np.float32)


def fas_box(src_w: int, src_h: int, box, scale: float) -> tuple[int, int, int, int]:
    """กรอบที่ขยายรอบหน้าแบบเดียวกับต้นฉบับ (generate_patches._get_new_box) · คืน x0, y0, x1, y1.

    MiniFASNet ต้องเห็นรอบ ๆ หน้าด้วย (ขอบจอ/ขอบกระดาษคือหลักฐานของการปลอม) จึงขยาย 2.7 และ 4 เท่า
    ขยายแล้วล้นภาพ → เลื่อนกรอบกลับเข้ามา (ไม่ย่อ) เหมือนต้นฉบับ
    """
    x, y, bw, bh = box
    scale = min((src_h - 1) / bh, (src_w - 1) / bw, scale)
    nw, nh = bw * scale, bh * scale
    cx, cy = x + bw / 2, y + bh / 2
    x0, y0, x1, y1 = cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2
    if x0 < 0:
        x1, x0 = x1 - x0, 0
    if y0 < 0:
        y1, y0 = y1 - y0, 0
    if x1 > src_w - 1:
        x0, x1 = x0 - (x1 - src_w + 1), src_w - 1
    if y1 > src_h - 1:
        y0, y1 = y0 - (y1 - src_h + 1), src_h - 1
    return int(x0), int(y0), int(x1), int(y1)


class Liveness:
    """MiniFASNet 2 ตัว (กรอบ 2.7× และ 4×) เฉลี่ยกัน · คืนคะแนน "หน้าจริง" 0–1 (ช่องที่ 1 ของต้นฉบับ).

    เตรียมภาพแบบเดียวกับต้นฉบับทุกอย่าง: BGR, 80×80, ค่า 0–255 ไม่หาร 255, เรียงเป็น CHW
    """

    def __init__(self):
        import cv2

        self._cv2 = cv2
        pairs = ((FAS_V2, 2.7), (FAS_V1SE, 4.0))  # (ไฟล์, ขยายกรอบกี่เท่า) ตามชื่อไฟล์ต้นฉบับ
        self._nets = [(cv2.dnn.readNetFromONNX(str(locate(m))), s) for m, s in pairs]

    def score(self, frame: np.ndarray, box) -> float:
        h, w = frame.shape[:2]
        total = np.zeros(3)
        for net, scale in self._nets:
            x0, y0, x1, y1 = fas_box(w, h, box, scale)
            patch = self._cv2.resize(frame[y0 : y1 + 1, x0 : x1 + 1], (80, 80))
            net.setInput(patch.transpose(2, 0, 1)[None].astype(np.float32))
            logits = net.forward().reshape(-1)
            e = np.exp(logits - logits.max())
            total += e / e.sum()
        return float(total[1] / len(self._nets))


def main(argv: list[str]) -> int:
    if argv[:1] == ["fetch"]:
        print(fetch(SFACE_VARIANTS[argv[1]] if len(argv) > 1 else SFACE))
        return 0
    if argv[:1] == ["check"]:
        ok = True
        for m in (YUNET, FAS_V2, FAS_V1SE, SFACE):
            try:
                print("ผ่าน", locate(m))
            except ModelError as e:
                ok = False
                print("ไม่ผ่าน", e)
        return 0 if ok else 1
    print("ใช้: python -m aipc.vision.models fetch [fp32|int8] | check")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
