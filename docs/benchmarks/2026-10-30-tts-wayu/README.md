# Wayu-Paxa-TTS-Edge บน Pi 5 · **สถานะ: ประกาศก่อนรัน** (2026-10-30 · ผลจะเติมด้านล่างโดยไม่แก้ส่วนนี้)

## คำถาม

Pakon ขอ (2026-10-30): ติดตั้ง Wayu-Paxa-TTS-Edge แล้วทดสอบ 10 ประโยคที่ยาวไม่เท่ากัน (ไทยล้วน · ไทยผสมอังกฤษ) ·
แต่ละประโยคสร้างเสียงใช้เวลากี่วินาที · เหมาะใช้ในระบบจริงไหม · ทดสอบ 3 เสียง

## ของที่วัด

- โมเดล: [`wayu-ai/wayu-paxa-tts-edge`](https://huggingface.co/wayu-ai/wayu-paxa-tts-edge) revision `8196688` · 82M พารามิเตอร์ (Kokoro/StyleTTS2) · 24 kHz ·
  **ไลเซนส์น้ำหนัก CC-BY-NC-4.0 (ห้ามใช้เชิงการค้า)** · โค้ด `wayu-research/wayu-tts-inference` `07ab898` Apache-2.0 · งานวิจัย arXiv 2609.03502
- 3 เสียง (หน้าโมเดลไม่ได้จัดอันดับ → เลือกแบบ "clear · neutral" ที่เหมาะกับผู้ช่วย): `f_young_clear` · `m_young_clear` · `f_mid_clear`
- ตัวเทียบ: Piper `th_TH-tsync2-medium` ที่แอปใช้อยู่ (`/opt/aipc-voice`) ข้อความเดียวกัน
- ติดตั้งแยก: Python 3.12 (uv 0.12.24) ใน `~/wayu-venv` · torch CPU · ไม่แตะ venv ของแอป · ไม่ใช้ apt (ไม่มี espeak-ng: คำอังกฤษที่ไม่มีในพจนานุกรมอาจอ่านไม่ออก)
- ข้อจำกัดการติดตั้งที่รู้ก่อนรัน: `tltk` ขอ scikit-learn ~=1.2 (ใช้ได้แค่ numpy 1) แต่ transformers/pandas ต้อง numpy 2 →
  ใช้ scikit-learn ≥ 1.5 นอกเงื่อนไขของ tltk · ตรวจแล้วบนโน้ตบุ๊กว่า tltk แปลงไทยเป็นเสียงอ่านได้ตามปกติ

## ชุดทดสอบ

`tests/data/tts_wayu_sentences.json` (commit `71cf9c7` ก่อนติดตั้ง) · 10 ประโยค · ไทยล้วน 5 (T01–T05) · ไทยผสมอังกฤษ 5 (M01–M05) · 5–256 ตัวอักษร

## วิธีวัด (`scripts/bench/tts_speed.py` · บน Pi 5 · ไม่มีงานอื่นรัน)

ต่อเสียง: โหลดโมเดล (จับเวลา) → อุ่นเครื่อง 1 ครั้ง (ไทย + อังกฤษ) → ทุกประโยค 3 รอบ ใช้มัธยฐาน ·
เวลาสร้างเสียงทั้งประโยค · ความยาวเสียง · **RTF = เวลาสร้าง ÷ ความยาวเสียง** (< 1 = สร้างเร็วกว่าพูด) · RAM สูงสุดของโปรเซส ·
เก็บไฟล์เสียงรอบแรกให้ Pakon ฟัง (ไม่ใส่ git)

## เกณฑ์ "เหมาะใช้ในระบบจริง" (จากการ์ด 0019 · ประกาศก่อนรัน)

| ข้อ | เกณฑ์ | ที่มา |
|---|---|---|
| 1 | ประโยคสั้น ≤ 60 ตัวอักษร (= ท่อนแรกที่แอปเล่น) สร้างเสร็จ ≤ 2 วิ (มัธยฐาน) | การ์ด 0019 "เริ่มพูด ≤ 2 วิ" · ท่อนแรก ≤ 60 ตัวอักษร |
| 2 | RTF < 1 ทุกประโยค (สร้างท่อนถัดไปทันก่อนท่อนก่อนหน้าพูดจบ) | ผู้วัดตั้ง · ไม่มีในการ์ด |
| 3 | RAM สูงสุดของตัวอ่าน ≤ 1 GB | 8 GB − Gemma 4.5 GB (วัด 2026-10-30) − แอป/ระบบ ~1.5 GB − เผื่อ 1 GB (การ์ด 0019) |
| 4 | ฟังแล้วอ่านถูกและฟังรู้เรื่อง (Pakon ฟัง · ไทยและคำอังกฤษ) | ไม่มีตัวเลข · รายงานตามที่ Pakon ตัดสิน |

"เหมาะ" = ผ่าน 1–3 และ Pakon ฟังผ่าน · ต่อให้ผ่าน **ไม่ติดตั้งในแอปจนกว่า Pakon อนุมัติ** (กฎเหล็กข้อ 2) และต้องตัดสินเรื่องไลเซนส์ NC

## ทำซ้ำ

```bash
~/wayu-venv/bin/python scripts/bench/tts_speed.py --engine wayu --model ~/wayu-model \
    --voices f_young_clear m_young_clear f_mid_clear --sentences tests/data/tts_wayu_sentences.json \
    --out docs/benchmarks/2026-10-30-tts-wayu/wayu-pi5.json --keep ~/tts-wayu-wav
/opt/aipc-voice/venv/bin/python scripts/bench/tts_speed.py --engine piper \
    --model /opt/aipc-voice/th_TH-tsync2-medium.onnx --voices piper-th ... --out .../piper-pi5.json
```

## ผล (ยังไม่รัน)
