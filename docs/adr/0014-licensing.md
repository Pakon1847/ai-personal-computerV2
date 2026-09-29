# ADR-014: ไลเซนส์และการแจกจ่าย

- **สถานะ:** ตัดสินแล้ว 2026-09-23 (Pakon)
- **ต้องตัดสินก่อน:** เฟส 0

## ค่าที่ brief แนะนำ

ถ้าจะแจกจ่ายหรือใช้เชิงพาณิชย์: เลี่ยงโมเดล NC (MMS-TTS, InsightFace) และตรวจภาระของ GPL (Qt Virtual Keyboard, qt-session-lock)

## การตัดสิน

**ใช้ในงานศึกษาเท่านั้น** — โปรเจกต์นี้คือปริญญานิพนธ์ของมหาวิทยาลัย ไม่แจกจ่ายและไม่ใช้เชิงพาณิชย์

ผลที่ตามมา:

- ใช้โมเดลที่ไลเซนส์ห้ามใช้เชิงพาณิชย์ (NC) ได้ เช่น InsightFace pretrained, MMS-TTS-tha
- ใช้ส่วนที่เป็น GPL ได้ เช่น Qt Virtual Keyboard, qt-session-lock
- **แต่ต้องประกาศทุกตัว** ในตาราง "ไลเซนส์ของส่วนประกอบ" ด้านล่าง และในบทที่ 3 ของเล่ม
  เพราะกรรมการอาจถามว่า "ถ้าจะเอาไปใช้จริงต้องเปลี่ยนอะไร" — คำตอบต้องอยู่ในตารางนี้
- ถ้าอนาคตจะแจกจ่าย: ต้องกลับมาเปิด ADR นี้ใหม่ และเปลี่ยนทุกแถวที่คอลัมน์ "ใช้เชิงพาณิชย์ได้" เป็น "ไม่"

## ไลเซนส์ของส่วนประกอบ

เพิ่มแถวทุกครั้งที่เลือกโมเดลหรือไลบรารีใหม่ (brief หัวข้อ 11 กติกาข้อ 7) · ห้ามเพิ่มของที่ยังไม่ได้เปิดอ่านไลเซนส์จริง

| ส่วนประกอบ | ไลเซนส์ | ใช้เชิงพาณิชย์ได้ | แหล่งที่ตรวจ | วันที่ตรวจ |
|---|---|---|---|---|
| IBM Plex Sans Thai, IBM Plex Mono (ฟอนต์ใน `src/aipc/ui/fonts/`) | SIL Open Font License 1.1 | ได้ (ห้ามขายตัวฟอนต์แยก) | `src/aipc/ui/fonts/OFL.txt` ดาวน์โหลดจาก github.com/google/fonts | 2026-09-23 |
| PySide6-Essentials 6.11.2 (Qt for Python) | LGPL-3.0 (หรือเชิงพาณิชย์) | ได้ ถ้าลิงก์แบบ dynamic และให้ผู้ใช้เปลี่ยนไลบรารีได้ — เราติดตั้งผ่าน pip จึงเข้าเงื่อนไข | ยังไม่ได้เปิดอ่านไฟล์ไลเซนส์ใน wheel ด้วยตัวเอง ต้องตรวจซ้ำ | 2026-09-23 |
| Typhoon2.5-Qwen3-4B GGUF (`typhoon-ai/typhoon2.5-qwen3-4b-gguf` · ฐาน `scb10x/typhoon2.5-qwen3-4b`) | Apache-2.0 | ได้ | Hugging Face API (`cardData.license`) | 2026-09-29 |
| Qwen3-4B-Instruct-2507 GGUF (`unsloth/Qwen3-4B-Instruct-2507-GGUF` · ฐาน `Qwen/Qwen3-4B-Instruct-2507`) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| Gemma 4 E2B-it GGUF (`unsloth/gemma-4-E2B-it-GGUF` · ฐาน `google/gemma-4-E2B-it`) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| Qwen3-0.6B GGUF (`Qwen/Qwen3-0.6B-GGUF` · ตัวช่วยร่างสำหรับทดลอง) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| llama.cpp (`llama-server`, `llama-bench` · build บน Pi 5 · commit `86ea01d`) | MIT | ได้ | github.com/ggml-org/llama.cpp/LICENSE | 2026-09-29 |
