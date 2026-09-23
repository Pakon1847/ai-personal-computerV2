# ไฟล์โมเดลใบหน้า (การ์ด 0005) · ที่มาและไลเซนส์

| ไฟล์ | ที่มา | ไลเซนส์ | sha256 |
|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` | [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (ไม่แก้ไข) | MIT · `LICENSE-yunet.txt` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `2.7_80x80_MiniFASNetV2.onnx` | แปลงจาก `resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth` ของ [minivision-ai/Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) commit `b6d5f04` (sha256 ต้นฉบับ `a5eb02e1…099bec0`) | Apache-2.0 · `LICENSE-minifasnet-apache-2.0.txt` | `314303502333dd72a3a314537a97199a28afd2c3e2099597382886703031b405` |
| `4_0_0_80x80_MiniFASNetV1SE.onnx` | แปลงจาก `4_0_0_80x80_MiniFASNetV1SE.pth` commit เดียวกัน (sha256 ต้นฉบับ `84ee1d37…c5f5990`) | Apache-2.0 | `9cd4527a192dcf41f90e2b2066215daf7867ee34a8a857cdf9e98de60c93355d` |
| `face_recognition_sface_2021dec.onnx` (**ไม่อยู่ใน repo** 37 MB · ดาวน์โหลดด้วย `python -m aipc.vision.models fetch`) | [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) (ไม่แก้ไข) | Apache-2.0 · `LICENSE-sface-apache-2.0.txt` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

**การแก้ไขตาม Apache-2.0 ข้อ 4(b):** ไฟล์ MiniFASNet `.onnx` คือการเปลี่ยนรูปแบบไฟล์จาก PyTorch เป็น ONNX (opset 17) เท่านั้น
ไม่ได้แก้หรือฝึกน้ำหนักใหม่ · สคริปต์แปลงอยู่ที่ `tools/convert_minifasnet.py` · ตรวจแล้วว่าผลผ่าน OpenCV DNN
ต่างจาก PyTorch ต้นฉบับไม่เกิน 1.5e-8 (softmax) กับอินพุตสุ่ม 5 ชุดต่อโมเดล (2026-09-24)

**ข้อจำกัดที่ต้องบอก:** ไลเซนส์ของชุดข้อมูลที่ใช้ฝึก SFace และ MiniFASNet ไม่ได้ระบุไว้ใน repo ต้นทาง ·
โปรเจกต์นี้ใช้ในงานศึกษาเท่านั้น (ADR-014)
