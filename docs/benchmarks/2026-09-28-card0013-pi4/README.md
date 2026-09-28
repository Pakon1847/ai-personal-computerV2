# การ์ด 0013 กับ llama-server ตัวจริงบน Pi 4 (ทดสอบความถูกต้อง · ไม่ใช่ผลวัด)

- **วันที่:** 2026-09-28 · **commit:** `6dcfdce` · **ฮาร์ดแวร์:** Raspberry Pi 4 Model B 4 GB · trixie aarch64 · **(Pi 4)**
- **llama.cpp:** `6c7a87f` build บนเครื่อง (`-DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF`)
- **โมเดลทดสอบ:** Qwen2.5-0.5B-Instruct Q4_K_M · sha256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` (ตรงกับ Hugging Face)
  — **ไม่ใช่ผู้สมัคร ADR-007** ใช้แค่ยืนยันว่าโค้ดคุยกับ llama-server จริงได้ · ห้ามใช้ตัวเลขความเร็วในบทที่ 4

| สิ่งที่ตรวจ | ผล |
|---|---|
| llama-server รองรับ Unix socket (`--host …/llm.sock`), `--no-slots`, `--no-webui` | มีใน `--help` และเปิดได้จริง → ADR-008 ใช้ได้กับ build นี้ |
| `/health` ผ่าน socket | ready หลังโหลดโมเดล |
| stream คำตอบภาษาไทยทีละ token | 46 token จบปกติ (reason ว่าง) |
| หยุดกลางคำตอบ (abort หลัง 2 วิ) | หยุดที่ 2.0 วิ · server ยัง ready ต่อ |
| สิทธิ์โฟลเดอร์ socket | `/run/user/1000/aipc` 0700 ของผู้ใช้คนนั้น (ผู้ใช้อื่นเข้าไม่ถึง) |
| เทสต์ทั้งชุดบน Pi 4 | 402 ผ่าน · ไม่ข้าม |

**ยังไม่ได้ทดสอบ:** user service `aipc-llm` ผ่าน systemd (ต้องติดตั้งด้วย `install-llm.sh`) · หน้าจอจริง ·
`kill -9` ระหว่างตอบ (T7) · ผู้ใช้อื่นลองต่อ socket (T12) · โมเดลผู้สมัครบน Pi 5
