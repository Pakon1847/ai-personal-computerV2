# เลือกสกิลบน Pi 5: กฎ + AI ในเครื่อง (ADR-007 เกณฑ์ข้อ 6)

- **ชุดประโยค:** `tests/data/skill_selection.json` 58 ข้อ (commit ก่อนวัด · ไม่แก้หลังวัด)
- **เกณฑ์ (ประกาศก่อนวัด):** เลือกถูก ≥ 80% · เรียกสกิลทั้งที่ไม่ควร ≤ 10% (ของข้อที่ควรเป็น "none" 18 ข้อ)
- **ตัววัด:** `python -m aipc.spikes.skill_select` · เรียกจาก `scripts/pi/measure-llm.sh` ขั้น 4

## รอบ 1 (2026-09-29 · `typhoon25-4b-q4km.json`) — **ใช้ไม่ได้**

ผลในไฟล์: ถูก 35/58 · เรียกผิด 7/18 · ถาม AI 21 ข้อ · **AI เรียกเครื่องมือ 0 ครั้ง** (`raw_tool` ว่างทุกข้อ)

สาเหตุ (ตรวจบน Pi 5 วันเดียวกัน):

| สิ่งที่ตรวจ | ผล |
|---|---|
| `GET /props` → `chat_template` | ยาว 208 ตัวอักษร · ChatML ธรรมดา ไม่มีคำว่า `tools` |
| `chat_template_caps.supports_tools` | `false` |
| `POST /apply-template` พร้อมรายการสกิล 5 ตัว | prompt 165 token · **ไม่มีชื่อสกิลสักตัว** (llama-server ทิ้งรายการเงียบ ๆ ไม่ขึ้น error) |
| ถามซ้ำด้วย template ต้นฉบับจาก `typhoon-ai/typhoon2.5-qwen3-4b` (`--chat-template-file`) | `supports_tools: true` · prompt 1,020 token · เรียก `summarize-text` / `letter-writer` ถูก 3 จาก 3 ข้อที่ลอง |

ไฟล์รอบ 1 จึงเท่ากับ "กฎอย่างเดียว" (ตรงกับ [ผลกฎอย่างเดียว](../2026-09-29-skill-selection-rules/README.md) 35/58 ทุกข้อ) ·
เก็บไว้เป็นหลักฐานของปัญหา ไม่ใช้ตัดสิน ADR-007 · แก้แล้ว: template ต้นฉบับอยู่ใน `scripts/pi/chat-templates/`
และตัววัดหยุดเองถ้า `/props` ตอบ `supports_tools: false`

## รอบ 2 (ประกาศก่อนวัด 2026-09-29)

ชุดประโยคและเกณฑ์เดิม · server: `llama-server -c 4096 -t 4 --chat-template-file scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja`
(llama.cpp `86ea01d`) · sampling `temperature 0.6 · top_p 0.95 · max_tokens 48` · วัด 2 แบบ ต่อเนื่องใน server ตัวเดียวกัน:

| แบบ | ทำอะไร | ไฟล์ |
|---|---|---|
| `rules-first` | แอปตอนนี้: ตัวแปลคำสั่ง → กฎนัดหมาย → คะแนนคำสำคัญ → ถาม AI เฉพาะข้อที่กฎไม่เจออะไร | `typhoon25-4b-q4km-rules-first.json` |
| `ai-first` | ตัวแปลคำสั่งเครื่องก่อน (ชื่อแอป/เว็บต้องแน่นอน) → ที่เหลือถาม AI ทุกข้อ | `typhoon25-4b-q4km-ai-first.json` |

ทำไมวัดแบบที่ 2: ผลกฎอย่างเดียว ประโยคหลอก 6 ข้อ กฎตัดสินผิดหมด **ก่อน** ถึง AI → แบบ `rules-first` ผ่านข้อ 6 ไม่ได้
ไม่ว่า AI จะเก่งแค่ไหน (เรียกผิดขั้นต่ำ 7/18 = 39% จากกฎล้วน) · แบบที่ผ่านเกณฑ์ = แบบที่แอปควรใช้ (แก้ `SkillsController` ตามผล)

บันทึกเพิ่ม: เวลาต่อข้อ (ข้อแรก = prompt ยังไม่อยู่ใน cache) · `server` = sha256 ของ template ที่ server ใช้จริง ·
RAM ของ llama-server หลังวัด (`typhoon25-4b-q4km-server-ram.txt` · VmHWM · ADR-007 ข้อ 4)
