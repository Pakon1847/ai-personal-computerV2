"""แปลง MiniFASNet ต้นฉบับ (PyTorch) เป็น ONNX แล้วตรวจว่าผลตรงกับต้นฉบับ (การ์ด 0005).

ใช้ครั้งเดียวบนเครื่องพัฒนา ไม่ได้อยู่ในแอป และไม่ต้องลง PyTorch บน Pi
ขั้นตอน (ทำซ้ำได้):
    git clone https://github.com/minivision-ai/Silent-Face-Anti-Spoofing  (commit b6d5f04)
    python -m venv convenv && convenv/bin/pip install torch onnx onnxscript opencv-python-headless
    cd Silent-Face-Anti-Spoofing
    ../convenv/bin/python <repo>/tools/convert_minifasnet.py <โฟลเดอร์ผลลัพธ์>
ผลที่ได้ควรตรงกับ sha256 ใน src/aipc/vision/models/NOTICE.md (ถ้า PyTorch/ONNX รุ่นต่างกัน ไฟล์อาจต่าง
แต่ผลการทำนายต้องเท่ากัน — สคริปต์ตรวจตรงนี้ให้)
"""

import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, ".")  # รันจากโฟลเดอร์ของ repo ต้นฉบับ
from src.model_lib.MiniFASNet import (  # noqa: E402
    MiniFASNetV1,
    MiniFASNetV1SE,
    MiniFASNetV2,
    MiniFASNetV2SE,
)
from src.utility import get_kernel, parse_model_name  # noqa: E402

MODELS = {
    "MiniFASNetV1": MiniFASNetV1,
    "MiniFASNetV2": MiniFASNetV2,
    "MiniFASNetV1SE": MiniFASNetV1SE,
    "MiniFASNetV2SE": MiniFASNetV2SE,
}


def convert(name: str, out_dir: str, rng) -> float:
    h, w, kind, _ = parse_model_name(name)
    model = MODELS[kind](conv6_kernel=get_kernel(h, w))
    state = torch.load(f"resources/anti_spoof_models/{name}", map_location="cpu")
    model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
    model.eval()
    path = f"{out_dir}/{name.replace('.pth', '.onnx')}"
    torch.onnx.export(
        model, torch.zeros(1, 3, h, w), path,
        input_names=["input"], output_names=["logits"], opset_version=17, dynamo=False,
    )  # fmt: skip
    net = cv2.dnn.readNetFromONNX(path)
    worst = 0.0
    for _ in range(5):
        x = rng.integers(0, 256, (1, 3, h, w)).astype(np.float32)  # ต้นฉบับใช้ค่า 0–255 ไม่หาร 255
        with torch.no_grad():
            ref = torch.softmax(model(torch.from_numpy(x)), 1).numpy()
        net.setInput(x)
        out = net.forward()
        out = np.exp(out - out.max())
        worst = max(worst, float(np.abs(out / out.sum() - ref).max()))
    return worst


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    for name in ("2.7_80x80_MiniFASNetV2.pth", "4_0_0_80x80_MiniFASNetV1SE.pth"):
        diff = convert(name, sys.argv[1], rng)
        print(f"{name}: max |OpenCV-ONNX − PyTorch| (softmax) = {diff:.2e}")
        assert diff < 1e-5, "ผลไม่ตรงต้นฉบับ"
