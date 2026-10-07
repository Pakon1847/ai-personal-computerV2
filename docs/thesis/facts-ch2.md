# ชุดข้อมูลบทที่ 2 ทฤษฎีและงานที่เกี่ยวข้อง · เตรียม 2026-10-07

> ข้อเท็จจริงพร้อมที่มา ไม่ใช่เนื้อหาเล่ม · **[Rn]** = แหล่งในหัวข้อสุดท้าย ซึ่งผู้ช่วย**เปิดตรวจแล้ว 2026-10-07** (ชื่อเรื่อง ผู้แต่ง ปี และข้อความที่อ้าง) ·
> แปลงรูปแบบอ้างอิงตามคู่มือคณะ [Pakon กรอก: APA / IEEE / แบบของคณะ] · ห้ามเพิ่มแหล่งที่ยังไม่ได้เปิดอ่าน ·
> ผลวัดของเราเองอยู่บทที่ 4 · บทนี้ใช้แค่ "ทำไมเลือก" และ "ทำงานอย่างไร"

## 2.1 Raspberry Pi 5 และ Raspberry Pi OS

- Pi 5: Broadcom BCM2712 · Arm Cortex-A76 64 บิต 4 แกน 2.4 GHz พร้อม cryptography extensions · LPDDR4X-4267 (1–16 GB) · ไฟ 5V/5A ผ่าน USB-C (Power Delivery) [R1]
- Raspberry Pi OS รุ่น Trixie ใช้ฐาน **Debian 13** · ประกาศ 2 ต.ค. 2025 (Simon Long) · ใช้ Wayland + **labwc** เป็น compositor · เปิด zram-swap เป็นค่าเริ่มต้นผ่านแพ็กเกจ `rpi-swap` (แบบ zram+file · จากคำตอบของเจ้าหน้าที่ใต้ประกาศ) [R2]
- labwc รองรับโปรโตคอล ext-session-lock และ ext-idle-notify · ใช้ swaylock ล็อกจอ และ swayidle ล็อกเมื่อไม่ได้ใช้ได้ (ตัวอย่างในเอกสาร: `timeout 300 'swaylock -f -c 000000'`) [R3]
- ทำไมไม่มี GPU สำหรับ LLM: งาน LLM รันบน CPU (llama.cpp) · เครื่องร้อนจนถูกลดความเร็วได้ → ต้องมี Active Cooler และอ่าน `vcgencmd get_throttled` ทุกครั้งที่วัด ([BRIEF หัวข้อ 2, 9](../BRIEF.md))

## 2.2 LLM ขนาดเล็กบน CPU

- **GGUF:** "file format for storing models for inference with GGML and executors based on GGML" · ไฟล์เดียวมีทุกอย่างที่ต้องใช้รันโมเดล [R21]
- **Quantization แบบ k-quants** (llama.cpp PR #1684 · Iwan Kawrakow · รวมเข้า 5 มิ.ย. 2023): Q4_K เก็บน้ำหนักเป็น super-block 8 บล็อก × 32 ค่า · scale/min 6 บิต → **4.5 บิตต่อน้ำหนัก** · มี "quantization mix" (เช่น `_M`) ที่ใช้ความละเอียดต่างกันตามชนิด tensor [R22] → เราใช้ Q4_K_M ทุกโมเดล ([ADR-007](../adr/0007-default-llm.md))
- **llama-server:** HTTP server ที่มี API แบบ OpenAI · `--host` รับ "UNIX socket paths ending in .sock" · function calling ใช้ได้เมื่อเปิด `--jinja` [R16] → เราต่อผ่าน Unix socket ใน `$XDG_RUNTIME_DIR` (ADR-008) และใช้ tool calling ให้ AI เลือกสกิล
- **อ่าน prompt (prefill) กับสร้างข้อความ (generation):** บน CPU ของ Pi 5 การอ่าน prompt เป็นคอขวด (โมเดล 4B อ่านได้ราว 8–12 token/วิ · ผลของผู้อื่น) → ใช้ system prompt สั้น + บันทึกแคชของ prompt ลงดิสก์ (โหลดคืน 0.24 วิ) ·
  ที่มา: [ข้อเสนอรอบ 3 หัวข้อ 7.1](../reviews/2026-09-28-scope-cut.md) · [ARCHITECTURE](../ARCHITECTURE.md)
- **Speculative decoding:** ใช้โมเดล/ตัวเดาที่ถูกกว่าร่างคำล่วงหน้าแล้วให้โมเดลหลักตรวจ ได้ผลลัพธ์เหมือนเดิม [R23] · ของเราลองแบบ n-gram ได้แค่ 1.04 เท่า → ไม่ใช้ ([ผล](../benchmarks/2026-10-01-llm-speed-ideas-pi5/README.md))
- **FlashAttention:** อัลกอริทึม attention แบบรู้จักการเข้าถึงหน่วยความจำ ลดการอ่าน/เขียน HBM บน GPU [R24] · บน CPU ของ Pi 5 ทำให้ generation **ช้าลง** → ปิด (`-fa off`) ([ผล](../benchmarks/2026-09-30-flash-attn-pi5/README.md))
- **โหมดคิด:** Gemma 4 / Qwen3 ถ้าไม่ปิดจะคิดจนหมด max_tokens แล้วคำตอบว่าง (พบ 2026-09-30) → ทุกคำขอส่ง `enable_thinking=false` (`src/aipc/spikes/llm_quality.py`)

## 2.3 LLM ภาษาไทยที่เป็นผู้สมัคร ([ADR-007](../adr/0007-default-llm.md) · ไลเซนส์ Apache-2.0 ทุกตัว · [ADR-014](../adr/0014-licensing.md))

| โมเดล | ข้อเท็จจริงจาก model card / รายงาน | แหล่ง |
|---|---|---|
| **Gemma 4 E2B-it** (ใช้ในแอป) | "E" = effective parameters · **2.3B effective (5.1B with embeddings)** · ใช้ Per-Layer Embeddings เพื่อรันบนอุปกรณ์ · context 128K · รองรับ 35+ ภาษา (ฝึกล่วงหน้า 140+ ภาษา) · **ไม่ระบุภาษาไทย** | [R10] [R11] |
| **Typhoon2.5-Qwen3-4B** | โดย typhoon-ai (SCB 10X) · ฐาน Qwen3 4B · instruct ไทย/อังกฤษ · context 256K · รองรับ function calling | [R12] · ตระกูล Typhoon 2: [R13] |
| **Qwen3-4B-Instruct-2507** | 4.0B (3.6B ไม่นับ embedding) · 36 ชั้น · GQA 32/8 · context 262,144 · **non-thinking เท่านั้น** | [R15] · ตระกูล Qwen3: [R14] |

ทำไมมี Qwen3-4B-2507: ฐานเดียวกับ Typhoon2.5 → วัดได้ตรง ๆ ว่าการปรับจูนไทยช่วยแค่ไหน ([ข้อเสนอรอบ 3 หัวข้อ 7.2](../reviews/2026-09-28-scope-cut.md)) ·
ADR-007 **ยังไม่ได้ตัดสินอย่างเป็นทางการ** (รอคะแนนไทยของ Pakon) · แอปใช้ Gemma 4 E2B ตั้งแต่ 2026-09-30

## 2.4 การจดจำใบหน้า

- **ตรวจหาหน้า YuNet:** ตัวตรวจหน้าแบบ anchor-free สำหรับอุปกรณ์ขนาดเล็ก · มีพารามิเตอร์ 75,856 ตัว (เล็กกว่าตัวตรวจขนาดเล็กอื่นราว 5 เท่า) · Machine Intelligence Research 20 (2023) [R25]
- **เทียบหน้า SFace:** ฟังก์ชัน loss "sigmoid-constrained hypersphere" คุมแรงดึงภายในคลาสและระหว่างคลาสแบบพอดี ลด overfitting · IEEE TIP 30 (2021) [R26] ·
  เกณฑ์ของ OpenCV: **cosine ≥ 0.363** = คนเดียวกัน (หรือ L2 ≤ 1.128) [R27] → ระบบเราใช้ 0.363 ทั้งสแกนเข้าเครื่องและกล้องดูเจ้าของ (`src/aipc/ui/presence.py`)
- **ตรวจหน้าปลอม (PAD) MiniFASNet:** จาก Silent-Face-Anti-Spoofing (Minivision · Apache-2.0) · MiniFASNetV1/V2 = MobileFaceNet ที่ตัดให้เล็กลง · ใช้สเปกตรัมฟูเรียร์ช่วยฝึก [R28] · ระบบเราใช้ 2 ตัว ([ARCHITECTURE](../ARCHITECTURE.md) หัวข้อใบหน้า)
- **ชุดข้อมูล LFW:** 13,233 ภาพ · 5,749 คน · ภาพในสภาพจริง (ท่า แสง อุปกรณ์ ฉากหลังต่างกัน) · รายงานเทคนิค UMass 07-49 (ต.ค. 2007) [R29] · โพรโทคอลมาตรฐาน 6,000 คู่ 10 ชุด (ใช้ในบทที่ 4)
- **ตัวชี้วัด:** FMR/FNMR (เทียบ 1:1) และ FAR/FRR (ระดับระบบ รวมการจับภาพไม่ได้) ตาม ISO/IEC 19795-1:2021 [R32] · EER = จุดที่ FAR = FRR ·
  การทดสอบ PAD (APCER/BPCER และประเภทการโจมตี) ตาม ISO/IEC 30107-3:2023 ซึ่ง**ไม่ครอบคลุม**การป้อนภาพปลอมเข้าทางอุปกรณ์ (T9 · CEN/TS 18099) [R30] · [THREAT_MODEL](../THREAT_MODEL.md)
- **ใบหน้าไม่ใช่รหัสผ่าน:** Howdy (face login บน Linux) เตือน "DO NOT USE HOWDY AS THE SOLE AUTHENTICATION METHOD FOR YOUR SYSTEM" และ "is in no way as secure as a password" [R33]
- **กฎหมาย:** ข้อมูลชีวภาพเป็นข้อมูลอ่อนไหวตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 มาตรา 26 [R31]

## 2.5 การยืนยันตัวตนและเซสชันบน Linux

- **PAM:** ระบบยืนยันตัวตนแบบต่อโมดูล · `pam_exec` "can be used to run an external command" ใช้ได้กับ auth/account/password/session [R34] → สแกนหน้าเข้าเครื่องใช้ `pam_exec` เรียก `aipc-face-pass` ([การ์ด 0015](../design/0015-face-login.md))
- **greetd:** "a minimal and flexible login manager daemon that makes no assumptions about what you want to launch" · คุยกับหน้า Login (greeter) ผ่าน IPC แบบ JSON · GPL-3.0 [R8] → หน้า Login ของเราเป็น greeter (ผู้ใช้ `_greetd`)
- **ปิดโปรเซสเมื่อออก:** `KillUserProcesses=` ของ systemd-logind = ปิด scope ของเซสชันและทุกโปรเซสในนั้นเมื่อผู้ใช้ออก [R9] → ตั้ง `yes` ใน `install-accounts.sh` (ไม่พึ่งค่าเริ่มต้นของ distro)
- **ล็อกจอ:** ext-session-lock-v1 กำหนดว่า compositor ต้อง "stop rendering and providing input to normal clients" และ "If the client dies while the session is locked, the compositor must not unlock the session" [R4] · swaylock เป็นตัวล็อกที่ใช้โปรโตคอลนี้ (MIT) [R6]
- **ไม่ได้ใช้เครื่อง:** ext-idle-notify-v1 แจ้งเมื่อไม่มีการใช้งานครบเวลาที่ตั้ง และแจ้งอีกครั้งเมื่อกลับมาใช้ · ถ้ามี idle inhibitor (เช่น วิดีโอกำลังเล่น) จะไม่ถือว่าไม่ได้ใช้ [R5] · swayidle (MIT) [R7] →
  อธิบายผลขั้น A ที่ "ไม่ล็อกระหว่างวิดีโอเล่น" ได้ตรงกับสเปก ([ผล](../benchmarks/2026-10-06-idle-lock-pi5/README.md))
- **keyring:** เข้าด้วยใบหน้า PAM ข้าม `pam_gnome_keyring` → keyring ไม่ถูกปลด · Chromium จึงใช้ `--password-store=basic` (ข้อมูลของเราเอง · [THREAT_MODEL](../THREAT_MODEL.md))

## 2.6 Qt Quick/QML + PySide6

- PySide6 = Qt for Python (ไลบรารี Qt ทางการสำหรับ Python) [R45] · **PySide6-Essentials 6.11.2: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`** (อ่านจาก metadata ของ wheel ที่ติดตั้งจริง 2026-10-07)
- หลักแบ่งงานของเรา: QML วาดอย่างเดียว · ตัดสินใจ/ตรวจข้อมูลใน Python ที่มีเทสต์ ([ARCHITECTURE](../ARCHITECTURE.md) หัวข้อหน้าจอ · [การ์ด 0007](../design/0007-ui-base.md))

## 2.7 งานที่เกี่ยวข้อง

| แนวทาง | งาน | ต่างจากของเราอย่างไร |
|---|---|---|
| ส่งต่อระหว่างโมเดลถูกกับแพง | FrugalGPT (cascade · Chen, Zaharia, Zou 2023) [R17] · Hybrid LLM (router ตามความยากของคำถาม · ICLR 2024) [R18] · RouteLLM (router ที่ฝึกจากข้อมูลความชอบ · 2024) [R19] | งานเหล่านี้ใช้ตัวเลือกที่**ฝึกจากข้อมูล** · ของเราให้โมเดลเล็กตัดสินเองผ่าน tool call + กฎ "ตอบว่าไม่รู้ = ส่งต่อ" (ไม่มีตัวเลือกที่ฝึก) → เทียบตัวเลขตรง ๆ ไม่ได้ เขียนเป็นแนวคิดเดียวกัน ([ผลไฮบริด](../benchmarks/2026-10-06-exam-hybrid-gemma/README.md)) |
| โมเดลใหญ่สร้างเครื่องมือ โมเดลเล็กใช้ | LATM (Cai et al. 2023) [R20] · คลังทักษะที่โตขึ้นเรื่อย ๆ Voyager (Wang et al. 2023) [R48] | ของเรา "เครื่องมือ" = ไฟล์สกิล `.md` ที่ไม่มีโค้ด และต้องผ่านประตูตรวจก่อนติดตั้ง ([การ์ด 0017](../design/0017-auto-skill.md)) |
| ค้นเครื่องมือก่อนส่งให้ LLM | RAG-MCP (Gan, Sun 2025) [R46] · Tool2Vec (Moon et al. 2024) [R47] | ของเราใช้ TF-IDF ของ n-gram ตัวอักษร 2–3 ตัว (ภาษาไทยไม่เว้นวรรค · ไม่ใช้โมเดล) ส่งเฉพาะสกิลผู้ใช้ 5 ตัวที่เกี่ยว ([การ์ด 0018](../design/0018-skill-retrieval.md)) |
| Prompt injection | indirect prompt injection ผ่านเนื้อหาภายนอก (Greshake et al. 2023) [R35] · OWASP Top 10 for LLM Applications 2025 ข้อ LLM01 [R36] | เรากัน: ข้อมูลไม่ใช่คำสั่ง (H8) · Action ใน allow-list · ไม่ผ่าน shell · ยืนยันก่อนทำ ([DESIGN](../DESIGN.md)) |
| ใช้ LLM ให้คะแนน | LLM-as-a-Judge (Zheng et al. · NeurIPS 2023 D&B): ลำเอียงตามตำแหน่ง ความยาว และเข้าข้างตัวเอง [R37] | ใช้เป็นหลักฐานเสริมเท่านั้น ไม่แทนคน ([ผล](../benchmarks/2026-10-05-llm-thai/README.md)) |
| ใบหน้าเข้าเครื่องบน Linux | Howdy [R33] | ของเรามี PAD + รหัสผ่านใช้ได้เสมอ + เปิดเองต่อบัญชี |

**Pakon ต้องค้นเพิ่ม (ยังไม่มีแหล่งที่ตรวจแล้ว):** งานวิจัย/ปริญญานิพนธ์ไทยที่ใกล้เคียง · ผู้ช่วยเสียง/AI ในเครื่องบน Raspberry Pi ที่มีอยู่ ·
ระบบหลายผู้ใช้บนเครื่องเดียวที่ใช้ใบหน้า → เปิดอ่านแหล่งก่อนอ้างทุกครั้ง

## 2.8 เสียงภาษาไทย ([การ์ด 0019](../design/0019-thai-voice.md))

- **Whisper:** ถอดเสียงจากการฝึกแบบ weak supervision ขนาดใหญ่ (Radford et al. 2022) [R41] · **Distil-Whisper:** ย่อโมเดลด้วย knowledge distillation (Gandhi et al. 2023) [R42]
- **Thonburian Whisper:** Whisper ที่ปรับจูนและย่อสำหรับภาษาไทย (Aung et al. · ICNLSP 2024 หน้า 149–156) [R43] → แอปใช้รุ่น distill-small f16 ผ่าน whisper.cpp (`src/aipc/voice/stt.py`)
- **Piper:** "A fast and local neural text-to-speech engine" (GPL-3.0) [R44] · เสียง `th_TH-tsync2-medium` ไลเซนส์ **CC BY-NC-SA 3.0 (ห้ามเชิงพาณิชย์)** ([ADR-014](../adr/0014-licensing.md))

## 2.9 ไฮบริดกับ Claude Code และบริการภายนอก

- **`claude -p`:** โหมดไม่โต้ตอบของ Claude Code · อ่าน prompt ทำงานจนจบ พิมพ์ผล แล้วออก · `--output-format json` ให้ `total_cost_usd` (ค่าประมาณฝั่งไคลเอนต์) ·
  `--bare` ข้าม hook/CLAUDE.md/ความจำ **แต่ไม่ใช้การเข้าสู่ระบบแบบ subscription** (ต้องมี API key) [R39] → เราไม่ใช้ `--bare` และรันจากโฟลเดอร์ว่างแทน ([ข้อเสนอ 2026-09-29 หัวข้อ 11.2–11.3](../reviews/2026-09-29-feature-proposal.md))
- **Open-Meteo:** ข้อมูลอากาศไลเซนส์ CC BY 4.0 (ต้องให้เครดิต) · ข้อกำหนดของแบบใช้ฟรี: ไม่เกิน 10,000 ครั้ง/วัน · 5,000/ชม. · 600/นาที [R40]

## 2.10 สถิติสำหรับผลที่ "ไม่พบความผิดพลาด"

- **Rule of three:** ไม่พบเหตุการณ์ใน n ครั้ง → ขอบบนความเชื่อมั่น 95% ของอัตราจริง ≈ 3/n (Hanley & Lippman-Hand 1983) [R38] ·
  ใช้กับผลแบบ injection 0/30 → อัตราจริงยังอาจสูงถึงราว 10% ([BRIEF หัวข้อ 9](../BRIEF.md))

## รายการอ้างอิงที่ตรวจแล้ว

ตรวจ = ผู้ช่วยเปิดหน้าแหล่งนั้นแล้วเทียบชื่อเรื่อง ผู้แต่ง ปี และข้อความที่อ้าง เมื่อ 2026-10-07 (ยกเว้นที่ระบุ) · หน้าเว็บอาจเปลี่ยนภายหลัง · ระบุวันที่เข้าถึงในเล่มตามคู่มือคณะ

| # | อ้างอิง | ลิงก์ |
|---|---|---|
| R1 | Raspberry Pi Ltd. *Raspberry Pi 5* (หน้าผลิตภัณฑ์ · สเปก) | https://www.raspberrypi.com/products/raspberry-pi-5/ |
| R2 | S. Long. *Trixie — the new version of Raspberry Pi OS*. Raspberry Pi News, 2 Oct 2025 | https://www.raspberrypi.com/news/trixie-the-new-version-of-raspberry-pi-os/ |
| R3 | labwc. *Integration* (เอกสารโปรเจกต์) | https://labwc.github.io/integration.html |
| R4 | Wayland Protocols. *ext-session-lock-v1* | https://wayland.app/protocols/ext-session-lock-v1 |
| R5 | Wayland Protocols. *ext-idle-notify-v1* | https://wayland.app/protocols/ext-idle-notify-v1 |
| R6 | swaywm. *swaylock* — "a screen locking utility for Wayland compositors" (MIT) | https://github.com/swaywm/swaylock |
| R7 | swaywm. *swayidle* — "Idle management daemon for Wayland" (MIT) | https://github.com/swaywm/swayidle |
| R8 | K. Levinsen. *greetd* (GPL-3.0) | https://github.com/kennylevinsen/greetd (ต้นฉบับ git.sr.ht เปิดไม่ได้วันที่ตรวจ) |
| R9 | systemd. *logind.conf(5)* — KillUserProcesses= | https://man7.org/linux/man-pages/man5/logind.conf.5.html |
| R10 | Google. *gemma-4-E2B-it* (model card) | https://huggingface.co/google/gemma-4-E2B-it |
| R11 | Gemma Team. *Gemma 4 Technical Report*. arXiv:2607.02770, 2 Jul 2026 | https://arxiv.org/abs/2607.02770 |
| R12 | typhoon-ai (SCB 10X). *typhoon2.5-qwen3-4b* (model card) | https://huggingface.co/typhoon-ai/typhoon2.5-qwen3-4b |
| R13 | K. Pipatanakul, P. Manakul, N. Nitarach, W. Sirichotedumrong, S. Nonesung et al. *Typhoon 2: A Family of Open Text and Multimodal Thai Large Language Models*. arXiv:2412.13702, 2024 | https://arxiv.org/abs/2412.13702 |
| R14 | A. Yang et al. (Qwen Team). *Qwen3 Technical Report*. arXiv:2505.09388, 2025 | https://arxiv.org/abs/2505.09388 |
| R15 | Qwen. *Qwen3-4B-Instruct-2507* (model card) | https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507 |
| R16 | ggml-org. *llama.cpp HTTP Server* (README) | https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md |
| R17 | L. Chen, M. Zaharia, J. Zou. *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance*. arXiv:2305.05176, 2023 | https://arxiv.org/abs/2305.05176 |
| R18 | D. Ding, A. Mallick, C. Wang, R. Sim, S. Mukherjee, V. Ruhle, L. V. S. Lakshmanan, A. H. Awadallah. *Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing*. ICLR 2024 (arXiv:2404.14618) | https://arxiv.org/abs/2404.14618 |
| R19 | I. Ong, A. Almahairi, V. Wu, W.-L. Chiang, T. Wu, J. E. Gonzalez, M. W. Kadous, I. Stoica. *RouteLLM: Learning to Route LLMs with Preference Data*. arXiv:2406.18665, 2024 | https://arxiv.org/abs/2406.18665 |
| R20 | T. Cai, X. Wang, T. Ma, X. Chen, D. Zhou. *Large Language Models as Tool Makers*. arXiv:2305.17126, 2023 | https://arxiv.org/abs/2305.17126 |
| R21 | ggml-org. *GGUF* (ข้อกำหนดรูปแบบไฟล์) | https://github.com/ggml-org/ggml/blob/master/docs/gguf.md |
| R22 | I. Kawrakow. *k-quants*. llama.cpp pull request #1684, merged 5 Jun 2023 | https://github.com/ggml-org/llama.cpp/pull/1684 |
| R23 | Y. Leviathan, M. Kalman, Y. Matias. *Fast Inference from Transformers via Speculative Decoding*. ICML 2023 (arXiv:2211.17192) | https://arxiv.org/abs/2211.17192 |
| R24 | T. Dao, D. Y. Fu, S. Ermon, A. Rudra, C. Ré. *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*. arXiv:2205.14135, 2022 | https://arxiv.org/abs/2205.14135 |
| R25 | W. Wu, H. Peng, S. Yu. *YuNet: A Tiny Millisecond-level Face Detector*. Machine Intelligence Research 20, 656–665, 2023. doi:10.1007/s11633-023-1423-y | https://link.springer.com/article/10.1007/s11633-023-1423-y |
| R26 | Y. Zhong, W. Deng, J. Hu, D. Zhao, X. Li, D. Wen. *SFace: Sigmoid-Constrained Hypersphere Loss for Robust Face Recognition*. IEEE Trans. Image Processing 30, 2587–2598, 2021. doi:10.1109/TIP.2020.3048632 | https://doi.org/10.1109/TIP.2020.3048632 |
| R27 | OpenCV. *samples/dnn/face_detect.py* (เกณฑ์ cosine 0.363 · L2 1.128) | https://github.com/opencv/opencv/blob/4.x/samples/dnn/face_detect.py (หน้าเอกสาร docs.opencv.org ตอบ 403 วันที่ตรวจ) |
| R28 | Minivision AI. *Silent-Face-Anti-Spoofing* (Apache-2.0) | https://github.com/minivision-ai/Silent-Face-Anti-Spoofing |
| R29 | G. B. Huang, M. Ramesh, T. Berg, E. Learned-Miller. *Labeled Faces in the Wild: A Database for Studying Face Recognition in Unconstrained Environments*. Tech. Rep. 07-49, University of Massachusetts, Amherst, Oct 2007 | https://people.cs.umass.edu/~elm/papers/lfw.pdf (ตรวจผ่านผลค้นหา · เว็บ LFW เดิมเปิดไม่ได้) |
| R30 | ISO/IEC 30107-3:2023. *Information technology — Biometric presentation attack detection — Part 3: Testing and reporting* (ฉบับที่ 2 · ม.ค. 2023) | https://www.iso.org/standard/79520.html (ตรวจผ่านผลค้นหา · หน้า ISO ตอบ 403) |
| R31 | พระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562. ราชกิจจานุเบกษา เล่ม 136 ตอนที่ 69 ก, 27 พฤษภาคม 2562 (มาตรา 26) | https://www.ratchakitcha.soc.go.th/DATA/PDF/2562/A/069/T_0052.PDF (ตรวจผ่านผลค้นหา) |
| R32 | ISO/IEC 19795-1:2021. *Information technology — Biometric performance testing and reporting — Part 1: Principles and framework* (ฉบับที่ 2 · พ.ค. 2021) | https://www.iso.org/standard/73515.html (ตรวจผ่านผลค้นหา) |
| R33 | boltgolt. *Howdy* (README · คำเตือนด้านความปลอดภัย) | https://github.com/boltgolt/howdy |
| R34 | Linux-PAM. *pam_exec(8)* | https://man7.org/linux/man-pages/man8/pam_exec.8.html |
| R35 | K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, M. Fritz. *Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection*. arXiv:2302.12173, 2023 | https://arxiv.org/abs/2302.12173 |
| R36 | OWASP. *LLM01:2025 Prompt Injection*. OWASP Top 10 for LLM Applications 2025 | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ |
| R37 | L. Zheng, W.-L. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang, J. E. Gonzalez, I. Stoica. *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*. NeurIPS 2023 Datasets and Benchmarks (arXiv:2306.05685) | https://arxiv.org/abs/2306.05685 |
| R38 | J. A. Hanley, A. Lippman-Hand. *If Nothing Goes Wrong, Is Everything All Right? Interpreting Zero Numerators*. JAMA 249(13), 1743–1745, 1983 | https://jamanetwork.com/journals/jama/fullarticle/385438 (ตรวจผ่านผลค้นหา) |
| R39 | Anthropic. *Run Claude Code programmatically* (Claude Code docs) | https://code.claude.com/docs/en/headless |
| R40 | Open-Meteo. *Terms & Privacy* | https://open-meteo.com/en/terms |
| R41 | A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, I. Sutskever. *Robust Speech Recognition via Large-Scale Weak Supervision*. arXiv:2212.04356, 2022 | https://arxiv.org/abs/2212.04356 |
| R42 | S. Gandhi, P. von Platen, A. M. Rush. *Distil-Whisper: Robust Knowledge Distillation via Large-Scale Pseudo Labelling*. arXiv:2311.00430, 2023 | https://arxiv.org/abs/2311.00430 |
| R43 | Z. H. Aung, T. Thavornmongkol, A. Boribalburephan, V. Tangsriworakan, K. Pipatsrisawat, T. Achakulvisut. *Thonburian Whisper: Robust Fine-tuned and Distilled Whisper for Thai*. Proc. ICNLSP 2024, 149–156 | https://aclanthology.org/2024.icnlsp-1.17/ |
| R44 | Open Home Foundation. *Piper* (piper1-gpl · GPL-3.0) | https://github.com/OHF-Voice/piper1-gpl |
| R45 | The Qt Company. *Qt for Python (PySide6) documentation* | https://doc.qt.io/qtforpython-6/ |
| R46 | T. Gan, Q. Sun. *RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation*. arXiv:2505.03275, 2025 | https://arxiv.org/abs/2505.03275 |
| R47 | S. Moon, S. Jha, L. E. Erdogan, S. Kim, W. Lim, K. Keutzer, A. Gholami. *Efficient and Scalable Estimation of Tool Representations in Vector Space* (Tool2Vec). arXiv:2409.02141, 2024 | https://arxiv.org/abs/2409.02141 |
| R48 | G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, A. Anandkumar. *Voyager: An Open-Ended Embodied Agent with Large Language Models*. arXiv:2305.16291, 2023 | https://arxiv.org/abs/2305.16291 |

**แหล่งใน [BRIEF หัวข้อ 13](../BRIEF.md) ที่ไม่ได้อยู่ในตารางนี้ = ยังไม่ได้ตรวจซ้ำ** → ตรวจก่อนใช้ในเล่ม
