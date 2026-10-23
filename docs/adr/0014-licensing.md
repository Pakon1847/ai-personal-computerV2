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
| gtklock 4.0.0-1 (จอล็อกรุ่น 2 · การ์ด 0055) | GPL-3.0-or-later | ได้แต่ต้องเปิดซอร์สตาม GPL ถ้าแจกจ่าย · ใช้แพ็กเกจของ OS ไม่ได้แก้ | `/usr/share/doc/gtklock/copyright` บน Pi 5 | 2026-10-23 |
| gtklock-playerctl-module 4.0.0-2 (ปุ่มเพลงบนจอล็อก) | GPL-3.0-or-later (`gtklock-module.h` = Expat) | เหมือน gtklock | `/usr/share/doc/gtklock-playerctl-module/copyright` บน Pi 5 | 2026-10-23 |
| playerctl / libplayerctl2 2.4.1-3 (คุมเพลงผ่าน MPRIS) | LGPL-3.0-or-later | ได้ (ใช้เป็นโปรแกรม/ไลบรารีของ OS · ไม่ได้แก้) | `/usr/share/doc/playerctl/copyright` บน Pi 5 | 2026-10-23 |
| `aipc-autounlock.c` ของเรา (โมดูลที่ gtklock โหลดเข้าโปรเซส · การ์ด 0055) | ของโปรเจกต์ (ไม่ได้ใส่ไลเซนส์) · **ทำงานในโปรเซสของโปรแกรม GPL** | งานศึกษา = ได้ · **ถ้าแจกจ่ายต้องเปิดซอร์สโมดูลนี้ด้วยไลเซนส์ที่เข้ากับ GPL-3.0** (ปลั๊กอินที่โหลดเข้าโปรเซสนับเป็นงานต่อยอด · ตามแนวของ FSF GPL FAQ) | อ่านจาก copyright ของ gtklock ข้างบน · ผมไม่ใช่นักกฎหมาย | 2026-10-23 |
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
| เสียง Piper `en_US-ljspeech-medium` (อ่านออกเสียงอังกฤษ · การ์ด 0039 ระยะ B · เทรนจากศูนย์บนชุดข้อมูล LJ Speech) | ชุดข้อมูล: public domain · repo `rhasspy/piper-voices`: MIT | ได้ | MODEL_CARD ใน `rhasspy/piper-voices` + Hugging Face API (`cardData.license`) | 2026-10-19 |
| espeak-ng (ตัวแปลงหน่วยเสียงอังกฤษของ piper-tts · มากับ wheel `piper-tts` 1.8.0 เป็น `espeakbridge.so` + `espeak-ng-data` · ไม่ได้ติดตั้งแยก) | อยู่ใต้ไลเซนส์ของ wheel: GPL-3.0-or-later (`COPYING` ใน dist-info) | ได้แต่ต้องเปิดซอร์สตาม GPL ถ้าแจกจ่าย (เหมือน piper-tts) | `piper_tts-1.8.0.dist-info/METADATA` + `licenses/` บน Pi | 2026-10-19 |
| sherpa-onnx 1.13.8 + sherpa-onnx-core (ตัวถอดของคีย์ลัด · การ์ด 0026) | Apache-2.0 ("Apache licensed, as found in the LICENSE file") | ได้ | `pip show sherpa-onnx` ใน `/opt/aipc-voice/zipformer/venv` บน Pi | 2026-10-19 |
| โมเดล Zipformer ไทย (`yfyeung/icefall-asr-gigaspeech2-th-zipformer-2024-06-20`) | น้ำหนักโมเดล: Apache-2.0 · **ข้อมูลที่ใช้ฝึก GigaSpeech2: เงื่อนไขการเข้าถึงกำหนด "non-commercial research and educational purposes" และ SpeechColab ไม่ได้ถือลิขสิทธิ์เสียง** | **ไม่แน่ใจ → ถือว่าไม่** (โมเดลที่ฝึกจากข้อมูลที่ใช้ได้เฉพาะวิจัย) · ใช้ได้ตาม ADR นี้ (งานศึกษา) | Hugging Face API (`cardData.license`) + หน้า dataset `speechcolab/gigaspeech2` | 2026-10-19 |
| whisper `ggml-base.en.bin` (ตัวถอดเสียงอังกฤษ · การ์ด 0040) | MIT ("Whisper's code and model weights are released under the MIT License") · ไฟล์ ggml: repo `ggerganov/whisper.cpp` MIT | ได้ | README ของ `openai/whisper` + Hugging Face API · sha256 ตรวจตอนติดตั้ง | 2026-10-19 |
| บริการดูหนัง/ฟังเพลง (Netflix · Viu · iQIYI · WeTV · Disney+ Hotstar · Spotify · การ์ด 0031 รอบ 2) | ข้อตกลงการใช้บริการของแต่ละเจ้า (ไม่ใช่ไลเซนส์ซอฟต์แวร์) · ผู้ใช้เข้าสู่ระบบด้วยบัญชีของตัวเอง · ระบบแค่เปิดหน้าเว็บ ไม่ดึงเนื้อหา | **ไม่ได้ตรวจเงื่อนไข** | — | 2026-10-19 |
| Widevine CDM (`libwidevinecdm0` 4.10.2662.3 ของ Raspberry Pi + ที่ Chromium ดาวน์โหลดเอง 4.10.3057.0) | ไลเซนส์กรรมสิทธิ์ของ Google (proprietary) · มากับ OS/เบราว์เซอร์ ไม่ได้แจกจ่ายโดยโปรเจกต์ | ไม่เกี่ยว (ไม่ได้แจกจ่าย) · **ไม่ได้อ่านข้อความไลเซนส์** | `dpkg -l` + ไฟล์ในโปรไฟล์บน Pi | 2026-10-19 |
| onnxruntime 1.30.0 | MIT | ได้ | `pip show onnxruntime` บน Pi | 2026-10-01 |
