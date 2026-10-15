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
| PySide6-Essentials 6.11.2 + shiboken6 6.11.2 (Qt for Python) | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (หรือเชิงพาณิชย์จาก Qt) | ได้ ถ้าใช้ตาม LGPL: ลิงก์แบบ dynamic และให้ผู้ใช้เปลี่ยนไลบรารีได้ — เราติดตั้งผ่าน pip จึงเข้าเงื่อนไข | metadata ของ wheel ที่ติดตั้ง (`importlib.metadata`) | 2026-10-07 |
| opencv-python-headless 5.0.0.93 | Apache-2.0 | ได้ | metadata ของ wheel ที่ติดตั้ง | 2026-10-07 |
| icalendar 7.3.0 (อ่านไฟล์ปฏิทิน .ics · การ์ด 0014) | BSD-2-Clause | ได้ | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| recurring-ical-events 3.8.2 (กางนัดซ้ำ · การ์ด 0014) | LGPL-3.0-or-later | ได้ ถ้าใช้ตาม LGPL แบบเดียวกับ PySide6 (ติดตั้งผ่าน pip ผู้ใช้เปลี่ยนไลบรารีได้ · ไม่ได้แก้โค้ดของไลบรารี) | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| x-wr-timezone 2.0.1 (ตัวที่ recurring-ical-events ต้องใช้) | LGPL-3.0-or-later | ได้ (เงื่อนไขเดียวกับแถวบน) | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| click 8.5.0 (ตัวที่ x-wr-timezone ต้องใช้) | BSD-3-Clause | ได้ | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| python-dateutil 2.9.0.post0 (กฎนัดซ้ำ) | Apache-2.0 หรือ BSD-3-Clause (เลือกได้) | ได้ | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| six 1.17.0 (ตัวที่ python-dateutil ต้องใช้) | MIT | ได้ | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| tzdata 2026.5 (ข้อมูลเขตเวลา) | Apache-2.0 | ได้ | PyPI + metadata ของ wheel ที่ติดตั้ง | 2026-10-15 |
| ปฏิทิน Google ผ่าน "ที่อยู่ลับในรูปแบบ iCal" (บริการภายนอก · การ์ด 0014) | ข้อตกลงการใช้บริการของ Google (ไม่ใช่ไลเซนส์ซอฟต์แวร์) · ผู้ใช้ดึงปฏิทินของตัวเอง | **ไม่ได้ตรวจเงื่อนไขเชิงพาณิชย์** | support.google.com/calendar/answer/37648 | 2026-10-15 |
| numpy 2.5.3 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` | ได้ | metadata ของ wheel ที่ติดตั้ง | 2026-10-07 |
| YuNet (`opencv_zoo/models/face_detection_yunet`) | MIT | ได้ | README ในโฟลเดอร์โมเดล | 2026-10-07 |
| SFace (`opencv_zoo/models/face_recognition_sface`) | Apache-2.0 | ได้ | README ในโฟลเดอร์โมเดล | 2026-10-07 |
| MiniFASNet (Silent-Face-Anti-Spoofing · Minivision) | Apache-2.0 | ได้ | github.com/minivision-ai/Silent-Face-Anti-Spoofing | 2026-10-07 |
| whisper.cpp (ตัวถอดเสียง การ์ด 0019) | MIT | ได้ | github.com/ggml-org/whisper.cpp | 2026-10-07 |
| Thonburian distill-small (`biodatlab/distill-whisper-th-small` · แปลงเป็น ggml เอง 2026-10-01) | MIT | ได้ | model card บน Hugging Face | 2026-10-07 |
| greetd (ตัวจัดการ Login) | GPL-3.0 | ได้แต่ต้องเปิดซอร์สตาม GPL ถ้าแจกจ่าย · เราใช้แพ็กเกจของ OS ไม่ได้แก้ | github.com/kennylevinsen/greetd | 2026-10-07 |
| labwc (compositor) | GPL-2.0 | เหมือน greetd | github.com/labwc/labwc | 2026-10-07 |
| swaylock · swayidle (ล็อก/ไม่ได้ใช้เครื่อง) | MIT | ได้ | github.com/swaywm/swaylock · swayidle | 2026-10-07 |
| ข้อมูลอากาศ Open-Meteo (บริการภายนอก) | ข้อมูล CC BY 4.0 (ต้องให้เครดิต) · API แบบฟรีไม่เกิน 10,000 ครั้ง/วัน | ข้อมูลได้ (ให้เครดิต) · **ไม่ได้ตรวจเงื่อนไข API เชิงพาณิชย์** | open-meteo.com/en/terms | 2026-10-07 |

**ยังไม่ได้ตรวจ (ห้ามระบุไลเซนส์ในเล่มจนกว่าจะตรวจ):** Claude Code / บริการของ Anthropic (เป็นบริการตามข้อตกลงของบัญชี ไม่ใช่ไลเซนส์ซอฟต์แวร์เปิด) · Chromium (แพ็กเกจของ OS) ·
ฟอนต์อื่นนอกจาก IBM Plex · โปรแกรมของ OS ที่เรียกใช้ (pw-record, pdftotext, wpctl, gio)
| Typhoon2.5-Qwen3-4B GGUF (`typhoon-ai/typhoon2.5-qwen3-4b-gguf` · ฐาน `scb10x/typhoon2.5-qwen3-4b`) | Apache-2.0 | ได้ | Hugging Face API (`cardData.license`) | 2026-09-29 |
| chat template ของ Typhoon2.5 (`scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja` · จาก `typhoon-ai/typhoon2.5-qwen3-4b` revision `ce0a741`) | Apache-2.0 (ไฟล์ใน repo ของโมเดล) | ได้ | Hugging Face API (`cardData.license`) | 2026-09-29 |
| Qwen3-4B-Instruct-2507 GGUF (`unsloth/Qwen3-4B-Instruct-2507-GGUF` · ฐาน `Qwen/Qwen3-4B-Instruct-2507`) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| Gemma 4 E2B-it GGUF (`unsloth/gemma-4-E2B-it-GGUF` · ฐาน `google/gemma-4-E2B-it`) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| Qwen3-0.6B GGUF (`Qwen/Qwen3-0.6B-GGUF` · ตัวช่วยร่างสำหรับทดลอง) | Apache-2.0 | ได้ | Hugging Face API | 2026-09-29 |
| llama.cpp (`llama-server`, `llama-bench` · build บน Pi 5 · commit `86ea01d`) | MIT | ได้ | github.com/ggml-org/llama.cpp/LICENSE | 2026-09-29 |
| piper-tts 1.8.0 (`OHF-voice/piper1-gpl` · ตัวอ่านออกเสียง การ์ด 0019) | GPL-3.0-or-later | ได้แต่ต้องเปิดซอร์สตาม GPL ถ้าแจกจ่าย · แอปเรียกเป็นโปรเซสแยก | `pip show piper-tts` บน Pi | 2026-10-01 |
| เสียง Piper `th_TH-tsync2-medium` (ชุดข้อมูล NECTEC TSync2 ผ่าน `dubbing-ai/vaja-thai`) | CC BY-NC-SA 3.0 | **ไม่** | MODEL_CARD ใน `rhasspy/piper-voices` | 2026-10-01 |
| tltk 1.11 (ตัวแปลงหน่วยเสียงไทยของ piper-tts) | BSD-3-Clause | ได้ | `pip show tltk` บน Pi | 2026-10-01 |
| onnxruntime 1.30.0 | MIT | ได้ | `pip show onnxruntime` บน Pi | 2026-10-01 |
