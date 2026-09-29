# chat template ของโมเดล (ใช้แทนตัวที่ฝังมาใน GGUF)

ชื่อไฟล์ = ชื่อไฟล์โมเดล โดยเปลี่ยน `.gguf` เป็น `.jinja` · `install-llm.sh` และ `measure-llm.sh` หยิบให้เองถ้ามีไฟล์ชื่อตรงกัน
แล้วส่งให้ `llama-server --chat-template-file`

## ทำไมต้องมี

template ที่ฝังใน GGUF บางตัวถูกตัดส่วน tool calling ออก · llama-server **ทิ้งรายการเครื่องมือเงียบ ๆ** ไม่ขึ้น error
AI จึงไม่เคยเห็นรายการสกิล (วัดบน Pi 5 วันที่ 2026-09-29 · [ผลวัด](../../../docs/benchmarks/2026-09-29-skill-select-pi5/README.md))

ตรวจได้เอง: `curl -s http://127.0.0.1:8080/props | python3 -m json.tool | grep supports_tools` ต้องได้ `true`

## ที่มาของแต่ละไฟล์

| ไฟล์ | มาจาก | revision | sha256 | ไลเซนส์ |
|---|---|---|---|---|
| `typhoon2.5-qwen3-4b-q4_k_m.jinja` | `https://huggingface.co/typhoon-ai/typhoon2.5-qwen3-4b/resolve/main/chat_template.jinja` (repo ต้นฉบับของโมเดล ไม่ใช่ repo GGUF) | `ce0a7416fe82d4404b2b4a253ce3ac095ab1252c` | `64f85b198065d0fba2a81f37e10ed68161ce2c19a754c7100e67e0ca2ee9c326` | Apache-2.0 (เดียวกับโมเดล · ADR-014) |

template ใน GGUF ของ Typhoon (`typhoon-ai/typhoon2.5-qwen3-4b-gguf`) ยาว 208 ตัวอักษร มีแค่ ChatML ธรรมดา
(`/props` ตอบ `supports_tools: false`) · ตัวต้นฉบับยาว 2,630 ตัวอักษร (`supports_tools: true`)
