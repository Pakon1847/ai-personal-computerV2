# ถอดเสียงไทยด้วย Thonburian Whisper รุ่นเล็กบน Pi 5 · ประกาศก่อนวัด · 2026-10-01

ที่มา: medium (817M) ช้าเกิน (11–35 วิ · [ผล](../2026-10-01-voice-pi5/README.md)) · แนวคิดข้อ 1 ใน [ข้อเสนอบ่าย](../../reviews/2026-10-01-ideas-afternoon.md)

## โมเดล (การ์ดบน Hugging Face · ตรวจ 2026-10-01)

| รุ่น | พารามิเตอร์ | ไลเซนส์ | WER ที่การ์ดอ้าง (CV13 · DeepCut) |
|---|---|---|---|
| `biodatlab/whisper-th-medium-combined` (ที่ใช้อยู่) | 817M | Apache-2.0 | 7.42% |
| `biodatlab/whisper-th-small-combined` | 282M | Apache-2.0 | 13.14% |
| `biodatlab/distill-whisper-th-small` | 206M | MIT | 11.23% |

แปลงเป็น ggml บน Windows ด้วย whisper.cpp v1.9.4 `models/convert-h5-to-ggml.py` (f16):
small `79be5d2d…842b` (488 MB) · distill `c7affd39…28ea` (336 MB)

## ประกาศก่อนวัด (H9)

- ตัววัดเดิม `scripts/pi/measure-voice.sh` (เพิ่มตัวแปร `STT_MODEL` `STT_ARGS`) · ประโยคคำสั่ง 10 ประโยคเดิม · เสียงสังเคราะห์จาก Piper → **อ้างได้แค่ความเร็ว**
- วัด: small และ distill · แบบ f16 และ q5_0 (quantize บน Pi) · ค่าเริ่มต้น และ `-ac 512`
- **เกณฑ์ (การ์ด 0019):** ถอดประโยค ~2–3 วิ ≤ 5 วิ (มัธยฐาน 10 ประโยค) · RAM ขณะถอดพร้อม Gemma เหลือ ≥ 1 GB
- ข้อความที่ถอดได้บันทึกไว้ดู · ถ้าความหมายกลับ (เปิด↔ปิด) ให้รายงาน แม้จะเร็วผ่าน · ความแม่นจริงต้องใช้เสียงคนจริง (ยังไม่มี)

## ผล

(รอ Pi กลับมาออนไลน์)
