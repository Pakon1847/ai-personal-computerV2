# Architecture — สิ่งที่มีอยู่จริงตอนนี้

ไฟล์นี้อธิบายเฉพาะของที่ **มีโค้ดแล้ว** · สถาปัตยกรรมเป้าหมายอยู่ใน [BRIEF หัวข้อ 7](BRIEF.md#7-สถาปัตยกรรมที่แนะนำ-โต้แย้งได้ด้วยหลักฐาน) · ลำดับงานอยู่ใน [ROADMAP](ROADMAP.md) · ระดับหลักฐานอยู่ใน [STATUS](STATUS.md)

## เครื่องมือเฟส 0

| แพ็กเกจ | ทำอะไร |
|---|---|
| `aipc.bench` | จับเวลาและเก็บค่าดิบตามกติกา BRIEF หัวข้อ 9 |
| `aipc.doctor` | ตรวจฮาร์ดแวร์และช่องโหว่ image แบบอ่านอย่างเดียว |
| `aipc.spikes.llm`, `spikes/pg-rls/` | spike ของ ADR-007 และ ADR-004 |

## เปิดเครื่องถึงหน้าจอ V2 (การ์ด 0003, 0004 · ติดตั้งบน Pi 4 แล้ว)

```text
เปิดเครื่อง → systemd → greetd ─► aipc-greeter (ผังแป้นอังกฤษ/ไทย) ─► cage -s ─► aipc.ui --greeter <เซสชัน>     (ผู้ใช้ _greetd, /opt/aipc-v2)
                          │  socket $GREETD_SOCK  (aipc.login.greetd: create_session → answer → start)
                          │  PAM ของ OS ตรวจรหัสผ่าน · โค้ดเราไม่ตรวจเอง
                          ▼ ผ่าน
          scripts/pi/session/aipc-session  (ผู้ใช้คนนั้น)
             └ labwc -C session/labwc (ค่าตั้งของเรา: Alt+Tab เท่านั้น, เมนูว่าง, แป้น us/th สลับด้วย ~)
                 └ -S aipc-shell-loop ─► aipc.ui --session --fullscreen
                        ล่ม → เปิดใหม่ · ล่ม 3 ครั้ง/60 วิ → จบเซสชัน
                 "ออก" ─► labwc --exit ─► greetd กลับหน้า Login
```

ติดตั้ง/ย้อนกลับ: `scripts/pi/install-greeter.sh [--apply] [--session v2] | --rollback` · ทางเข้าสำรอง: SSH, tty2
อัปเดตแอป (ADR-009): `scripts/pi/update-app.sh [--apply] | --rollback` · `/opt/aipc-v2` เป็น symlink → `/opt/aipc-releases/<commit>`
(แต่ละรุ่นมี venv ของตัวเอง) · ลองเปิดหน้า Login ด้วย `_greetd` ก่อนสลับ · rollback = สลับ symlink

## สมัครบัญชีและลืมรหัสผ่าน (การ์ด 0012)

```text
หน้า Login (_greetd) ── sudo -n /usr/local/sbin/aipc-accounts (ไม่มีอาร์กิวเมนต์ · JSON ทาง stdin)
                           └ aipc.accounts.helper (root): ตรวจกฎซ้ำ → useradd/chpasswd (สมัครเสรี · ไม่ใส่กลุ่ม sudo)
                              → home 0700 → PIN กู้คืน (hash scrypt ใน /var/lib/aipc/recovery, root 0600)
```

ติดตั้ง: `scripts/pi/install-accounts.sh [--apply] | --rollback` (ตัวช่วย + PAM + sudoers ผ่าน visudo + ปิด autologin tty1)

## AI ในเครื่อง (การ์ด 0013 · ปรับ 2026-10-05)

```text
aipc-session ── systemctl --user start aipc-llm ── llama-server -m /opt/aipc-models/gemma-4-E2B-it-Q4_K_M.gguf
                                                     --host $XDG_RUNTIME_DIR/aipc/llm.sock (0700 ของผู้ใช้)
                                                     -c 4096 -t 3 -fa off --swa-full --slot-save-path ~/.cache/aipc/llm-slots
พร้อมแล้ว → อุ่นแคช (system prompt + รายการสกิล) แล้วบันทึกลงดิสก์ · เริ่มใหม่ = โหลดคืน 0.24 วิ
ประวัติ: ~/.local/share/aipc/chats/<id>.json (atomic) · แชทชั่วคราวไม่เขียนดิสก์ · ทุกคำขอส่ง enable_thinking=false
```

ติดตั้ง: `scripts/pi/install-llm.sh --model <ไฟล์.gguf> [--apply] | --rollback` · ค่าที่ใช้อยู่ใน `/etc/aipc/llm.conf` ·
service: `Restart=on-failure`, `MemoryMax=4G` (**ไม่มีผลจนกว่าจะเปิด memory cgroup** · `aipc.doctor` ข้อ memcg) ·
**ต่อเน็ตไม่ได้ด้วยกลไกของ OS:** `RestrictAddressFamilies=AF_UNIX` (seccomp) + `PrivateNetwork=yes` (network namespace ของตัวเอง) ([ผล](benchmarks/2026-10-07-llm-netsandbox-pi5/README.md)) ·
`KillUserProcesses=yes` อยู่ใน `install-accounts.sh` (ออกจากระบบแล้วปิดทุกโปรเซสของผู้ใช้)

## เส้นทางของข้อความ (`aipc.skills.router` · `aipc.ui.backend`)

```text
ข้อความ ─► กฎ (โค้ด ไม่ผ่าน LLM · H6)
             ├─ command.parse → สั่งเครื่อง (allow-list · list args · ยืนยันก่อนถ้าไม่แน่ใจ) · ปุ่มย้อนกลับเสียง
             ├─ นัด/นัดซ้ำ (when.py) · อากาศ (weather.py) · หาไฟล์/ไฟล์ตามช่วงเวลา · แปล/สรุปที่ชัด
             ├─ ประโยคเดิมของสกิล → สกิลนั้น · ตั้งโหมด/งานประจำที่ยังไม่มี → ให้ Claude สร้างสกิล
             └─ ไม่ตรงกฎ ─► AI ในเครื่อง + เครื่องมือ: สกิลในตัว + สกิลของผู้ใช้ top-5 (การ์ด 0018) [+ ask-cloud + create-skill ถ้าเปิด Claude]
                              ├─ เลือกสกิล → โค้ดทำตามขั้นตอนในไฟล์ .md (การ์ดยืนยันถ้าแตะเครื่อง)
                              ├─ ตอบเอง → ข้อความ (ตอบว่าไม่รู้ + เปิด Claude = ส่งต่อ)
                              └─ ask-cloud / create-skill → หัวข้อ "ไฮบริด"
ใต้ทุกคำตอบ: "ทำไมได้คำตอบนี้" สร้างจากสิ่งที่เกิดจริง (ใครตอบ · ทำไมทางนี้ · ข้อมูลออกนอกเครื่องไหม · เวลา)
```

ไฟล์สกิลเป็นข้อมูล (`.md` · ADR-011) ผ่านตัวตรวจก่อนใช้เสมอ · ขั้นตอนที่ทำได้กำหนดในโค้ดเท่านั้น · สกิลห้ามเรียกเน็ต

**สกิลประจำเว็บ** (การ์ด 0046 · `aipc.skills.sitecmd`): หัวข้อ `## คำสั่ง` = คำพูด → `กดคีย์ <คีย์>` / `คลิก <ตัวเลือก CSS>` ·
ไม่เข้าตัวคัดสกิลของแชท · ใช้ทางคีย์ลัดเสียงเมื่อหน้าที่เปิดในเบราว์เซอร์ของผู้ช่วยเป็นเว็บนั้น (เทียบโดเมนในโค้ดทั้งตอนเลือกและตอนกด) ·
คำสั่งของระบบมาก่อน · สกิลประจำเว็บตรงเป๊ะ = มาก่อนทางที่ AI เดา (นัด · งานภาษา) · มี "ยืนยันก่อน"/ได้ยินใกล้เคียง = ถามก่อน · ไม่รู้จัก = ถามว่าให้ Claude เพิ่มเข้าสกิลของผู้ใช้ประจำเว็บนั้นไหม

## ไฮบริด (การ์ด 0016, 0017 · ข้อมูลออกนอกเครื่อง)

```text
หน้าจอของผู้ใช้ ─► claude -p (Claude Code ที่ผู้ใช้คนนั้นติดตั้ง/เข้าสู่ระบบเอง · ~/.local/bin/claude) จากโฟลเดอร์ว่าง
   ถาม Claude:    --tools WebSearch · ส่งคำถาม + ≤ 4 ข้อความล่าสุด (ไม่รวมรอบถามไฟล์) · ไม่ส่งนัด/ไฟล์/ใบหน้า/ชื่อบัญชี
   สร้างสกิล:     ไม่มีเครื่องมือ · ส่งคำขอ + รายชื่อสกิล/แอป · ผลต้องผ่านประตูตรวจก่อนติดตั้ง
หน้าจอ ─► Open-Meteo (urllib) ส่งชื่อเมือง/พิกัด เมื่อถามอากาศ
ทุกครั้ง → ~/.local/share/aipc/outbound.json (0600 · ข้อความที่ส่งจริง · หน้าตั้งค่าแสดง/ล้างได้) · เพดานเงินต่อวัน (cloud-usage.json)
ปิด: สวิตช์ Claude ในหน้าตั้งค่า (ui.json use_claude) · ไม่เข้าสู่ระบบ Claude · AIPC_CLOUD=0 · อากาศยังไม่มีสวิตช์
```

## เสียง (การ์ด 0019)

อ่านออกเสียง: Piper `th_TH-tsync2-medium` (โหลดค้างในโปรเซสแยก) · กดพูด/แตะพูด: `pw-record` → ตัวจับจุดจบเสียง (เงียบ 1 วิ) →
whisper.cpp distill-small `-ac 512` → ข้อความใส่ช่องพิมพ์ (ไม่ส่งเอง) · ทั้งหมดในเครื่อง · ติดตั้ง `scripts/pi/install-voice.sh`

## ใบหน้า (`aipc.vision` · การ์ด 0005, 0006 · หน้า Login ผ่าน visiond การ์ด 0015)

```text
กล้อง ─► models.Detector (YuNet) ─► quality.check ─► models.Liveness (MiniFASNet ×2) ─► align.crop 112×112
      ─► models.Embedder (SFace) ─► matching.average (3–5 เฟรม) ─► matching.match (threshold + margin)
pipeline.FaceScanner: process (ต่อเฟรม, จับเวลาทุกขั้น) · scan (1:N) · enroll (ตรง/ซ้าย/ขวา)
store.FaceStore: แม่แบบ 128 ค่า + ความยินยอม + sha256 โมเดล · ~/.local/share/aipc/face-template.json (0600)
pipeline.ScanLog: ~/.local/state/aipc/face-scans.log (ไม่มีภาพ ไม่มี embedding)
pipeline.EnrollLog: ~/.local/state/aipc/face-enroll.log (ผล ท่าที่ขาด เหตุผลที่พบบ่อย เวลา · การ์ด 0010)
```

โมเดลโหลดผ่าน OpenCV อย่างเดียว ตรวจ sha256 ทุกครั้ง (`models/NOTICE.md`) · SFace ดาวน์โหลดด้วย `python -m aipc.vision.models fetch`
เครื่องมือ: `aipc.vision.camera` (ทดลองกับกล้อง) · `aipc.vision.evaluate` (FAR/FRR/EER/ROC/DET) · `aipc.vision.bench` (เวลา/RAM)

**ในหน้าจอ (การ์ด 0006, 0010):** `ui/face.py` `FaceController` ห่อ pipeline ให้ QML (`FacePanel.qml` ในหน้าตั้งค่า) ·
ลงทะเบียน 5 ท่า (ตรง ซ้าย ขวา เงย ก้ม) แต่แม่แบบใช้เฉพาะ `template_poses` (ค่าเริ่มต้น ตรง/ซ้าย/ขวา) ·
ภาพสดขณะลงทะเบียนผ่าน `image://face/<เลขภาพ>` (`FacePreviewProvider`) · ภาพล่าสุด 1 ภาพในหน่วยความจำ ล้างเมื่อจบ

```text
FacePanel (QML) ── startEnroll(ยินยอม) / tryScan / cancel / deleteTemplate ──► FaceController (เธรดหลัก)
                                                                                 │ เปิดเธรดงาน
   ◄── state · advice · posesDone · busy (ข้อความเท่านั้น ไม่มีภาพ/embedding) ── เธรดงาน: กล้อง + FaceScanner
                                                                                 │ เสร็จ/ยกเลิก/กล้องหลุด
                                                                                 └ ปิดกล้อง ปล่อยโมเดล · บันทึกเฉพาะเมื่อสำเร็จ
```

ผลจากเธรดงานส่งกลับเธรดหลักผ่าน signal เท่านั้น · หน้า Login (`--greeter`) สร้าง `FaceController(active=False)` จึงไม่แตะกล้อง

## ล็อกเมื่อไม่ได้ใช้ + กล้องดูว่าเจ้าของยังอยู่ (`ui/idle.py` · `ui/presence.py` · 2026-10-06)

```text
aipc.ui --session (Wayland เท่านั้น) ── swayidle -w (ext-idle-notify ของ labwc · ไม่มีคีย์บอร์ด/เมาส์)
   ├ ครบ "ล็อก" (ค่าเริ่มต้น 5 นาที · 0 = ปิด)      → swaylock -f (ext-session-lock: บังทุกหน้าต่าง · ภาพข้อความไทยจากฟอนต์ของแอป · ปลดด้วยรหัสผ่านผ่าน PAM)
   ├ ครบ "ออกหลังล็อก" (ค่าเริ่มต้น 10 นาที)       → labwc --exit (เหมือนปุ่ม "ออก" · KillUserProcesses ปิดทุกโปรเซส)
   └ (เปิดกล้อง · ต้องมี "ใบหน้าของฉัน") ไม่แตะ 10 วิ → ไฟล์ธง → python -m aipc.ui.presence run (โปรเซสแยก)
        กล้อง 640×480 · 2 ภาพ/วิ · YuNet ทุกภาพ · SFace ทุก 2 วิ · เทียบทุกหน้า (≤ 3) กับแม่แบบเจ้าของ · cosine ≥ 0.363
        ไม่เห็นเจ้าของ 30 วิ → ล็อก · ล็อกแล้วไม่เห็นหน้าใครต่อเนื่องอีก 30 วิ → ออก
        เห็นคนอื่น 3 ครั้ง (คั่นได้ ≤ 6 วิ) และไม่มีเจ้าของ → ล็อกอย่างเดียว ไม่ออก (ขั้น B ข้อ M3 ไม่ผ่าน)
        แตะเครื่อง = ปิดกล้อง · ไม่บันทึกภาพ · สถานะเป็นตัวเลขใน $XDG_RUNTIME_DIR/aipc/presence.json · หน้าใบหน้าขอกล้องคืนก่อนใช้
```

ตั้งค่าในหน้าตั้งค่า (`ui.json`: `lock_min` `logout_min` `presence` `presence_lock_s` `presence_logout_s`) · ผล: [ขั้น A](benchmarks/2026-10-06-idle-lock-pi5/README.md) ·
[ขั้น B](benchmarks/2026-10-06-presence-b/README.md) · [ขั้น C](benchmarks/2026-10-06-presence-c-pi5/README.md)

**เบราว์เซอร์:** Chromium ใช้ `--password-store=basic` (`/etc/chromium.d/aipc-password-store` จาก `scripts/pi/install-browser.sh`) เพราะเข้าด้วยใบหน้าแล้ว keyring ไม่ถูกปลด ·
กู้รหัสด้วย PIN ลบ `login.keyring` ของบัญชีนั้น (เข้ารหัสด้วยรหัสเก่า) · ความเสี่ยงใน [THREAT_MODEL](THREAT_MODEL.md)

## หน้าจอ (`aipc.ui`)

```text
python -m aipc.ui
   │
   ▼
app.py ── โหลดฟอนต์ (fonts/, OFL) ── ส่งวัตถุ Python ให้ QML ────────────┐
   │                                                                   │
   ▼                                                                   ▼
qml/AipcUi/Main.qml  ── AppState.screen ──►  LoginScreen      backend.py
                                            SignupFlow         ├ uiSettings  ธีม/ขนาดตัวอักษร → settings.py (บันทึกแบบ atomic)
                                            ShellScreen        ├ system      นาฬิกา สถานะเครื่อง → aipc.doctor, aipc.bench.machine
                                              ├ StatusBar      ├ login       สถานะสแกนหน้า, signIn
                                              ├ Sidebar        ├ signup      กฎตรวจฟอร์ม → aipc.accounts.validation
                                              └ 5 หน้า          ├ filesBrowser ไฟล์ใน home → files.py (ห้ามออกนอก home)
                                                                 └ face        ใบหน้าของฉัน → face.py → aipc.vision (การ์ด 0006)
```

**หลักการแบ่งงาน:** QML วาดอย่างเดียว · การตัดสินใจ ตัวเลข และการตรวจข้อมูลอยู่ใน Python ซึ่งมีเทสต์
หน้าจอตรวจข้อมูลเพื่อบอกผู้ใช้เร็ว ๆ เท่านั้น ตัวตัดสินจริงต้องเป็น backend (BRIEF หัวข้อ 7 ข้อ 1)

**สีและขนาดอยู่ใน `Theme.qml` ที่เดียว** · ชื่อ token ตรงกับบอร์ดออกแบบ · สลับธีมด้วย `Theme.dark`

### อะไรจริง อะไรยังไม่มี

| ส่วน | สถานะในโค้ด |
|---|---|
| ธีมสว่าง/มืด, ขนาดตัวอักษร 100–200% | ทำงานจริง บันทึกที่ `~/.config/aipc/ui.json` |
| แถบสถานะ, หน้าสุขภาพเครื่อง | ค่าจริงจาก `aipc.doctor` ทุก 10 วิ |
| หน้าไฟล์ของฉัน | รายการไฟล์จริงใน home แบบอ่านอย่างเดียว |
| ฟอร์มสมัคร / ลืมรหัสผ่าน | หน้า Login จริง: สร้างบัญชีจริงผ่านตัวช่วย root (สมัครเสรี ไม่มีผู้ดูแลอนุมัติ · 2026-09-29) · กู้คืนด้วยรหัสกู้คืน (การ์ด 0012) · หน้าต่างพัฒนา: แบบจำลองที่เขียนว่า "จำลอง" |
| ช่องพิมพ์แชท | Enter/Shift+Enter/IME/Esc ทำงานจริง · ทุกข้อความผ่านตัวคัดสกิลก่อน · ที่เหลือและสกิลแปลส่งให้ llama-server ของผู้ใช้ (การ์ด 0013) · AI ไม่พร้อม = บอกตามจริง · ป้ายโมเดลจาก `/health` |
| นัดหมาย | แปลงวันเวลาด้วยโค้ด ยืนยันก่อนบันทึก เก็บที่ `~/.local/share/aipc/reminders.json` (atomic + .bak) · เตือนเด้งบนจอทุกรอบ 30 วิ · แจ้งนัดที่พลาดตอนเข้าใช้ · นัดซ้ำ (ทุกวัน/วันธรรมดา/เสาร์อาทิตย์/ทุก<วัน>) · อ่านเตือนออกเสียงได้ (ตั้งค่า) · ไม่ใช้ DB (ADR-004) |
| สั่งงานเครื่อง | บน Linux รัน `xdg-open` / `gtk-launch` (Pi 5 ไม่มี → `gio launch <ไฟล์ .desktop>`) / `wpctl` จริง (แบบ list ไม่ผ่าน shell) · **บนวินโดวส์เป็นแบบจำลอง และการ์ดเขียนว่า "จำลอง"** |
| เข้าสู่ระบบ | โหมด greeter (`--greeter`): ส่งให้ greetd/PAM ตรวจจริง · หน้าต่างพัฒนา: ปฏิเสธเสมอนอกโหมดพัฒนา |
| หลังเข้าระบบ | โหมดเซสชัน (`--session`): เริ่มที่ Shell, "ออก" จบเซสชันจริง, ไม่มีโหมดพัฒนา |
| ใบหน้าในหน้าตั้งค่า | ลงทะเบียน 5 ท่าพร้อมภาพสดแบบกระจก / ทดลองสแกน 1:1 (ไม่มีภาพ) / ลบ (การ์ด 0006, 0010) · ขอความยินยอมทุกครั้ง · แถบบนขึ้น "กล้องกำลังใช้" · **หน้าจอบน Pi ยังเป็นรุ่นการ์ด 0006 จนกว่าจะรัน `update-app.sh`** |
| สแกนหน้าที่หน้า Login | `aipc-visiond` (ผู้ใช้ `_aipcvision`) สแกนแล้วออกตั๋ว → greetd/PAM (`pam_exec` `aipc-face-pass`) · แม่แบบสำหรับเข้าเครื่องอยู่ที่ `/var/lib/aipc-vision/face-login/` (**ไม่ได้อยู่ใน home** · ผู้ใช้เปิด/ปิดเองในหน้าตั้งค่า) · รหัสผ่านใช้ได้เสมอ |
| หน้า Skill | สกิลในตัว + สกิลที่ Claude สร้าง (ดูขั้นตอน/ที่มา · เปิด-ปิด · ย้อนรุ่น · ลบ) · ส่งออก/นำเข้าไฟล์ `.md` (ผ่านตัวตรวจ) |
| สำรองลง USB · ลบบัญชี | สำรอง/กู้ข้อมูลแอป + ไฟล์ของฉันลงไดรฟ์ USB พร้อม sha256 (`aipc.backup`) · ลบบัญชีที่หน้า Login พร้อมใบยืนยัน (ตัวช่วย root เดียวกับสมัคร) |
| ล็อกเมื่อไม่ได้ใช้ · กล้องดูว่าเจ้าของยังอยู่ | มีแล้ว (หัวข้อด้านบน · 2026-10-06) · ปลดด้วยรหัสผ่านเท่านั้น · **ไม่มี** "ปิดบัง" ที่ปลดด้วยใบหน้า |
| หน้าความเป็นส่วนตัวแยก | **ไม่มีในรุ่นนี้** (ขอบเขตรอบ 3) · สิ่งที่ส่งออกนอกเครื่องดูได้ในหน้าตั้งค่า |

โหมดพัฒนา (`--dev` หรือ `--demo-scan`) มีแถบเตือนสีส้มด้านบนตลอดเวลา
