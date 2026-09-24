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
เปิดเครื่อง → systemd → greetd ─► cage -s ─► aipc.ui --greeter <เซสชัน>     (ผู้ใช้ _greetd, /opt/aipc-v2)
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

## Skill (`aipc.skills`)

```text
ข้อความ ─► router.route
             ├─ command.parse (ตัวแปลแบบกฎ, ไม่ผ่าน LLM) ─► actions.Executor (allow-list, list args)
             ├─ คะแนนคำสำคัญของไฟล์สกิล (builtin/*.json) คัดเหลือ ≤ 3
             │     ├─ machine-status ─► machine.diagnose (ค่าจริงจาก aipc.doctor)
             │     └─ สกิลที่ต้องใช้ LLM/STT/VLM ─► บอกว่ายังขาดอะไร
             └─ ไม่ตรงสกิลใด ─► คุยทั่วไป (ยังไม่มีโมเดล)
```

ไฟล์สกิลเป็นข้อมูล ผ่านตัวตรวจ `manifest.validate` ก่อนใช้เสมอ · Action และสิทธิ์ที่ขอได้ถูกกำหนดในโค้ดของระบบเท่านั้น

## ใบหน้า (`aipc.vision` · การ์ด 0005 · ต่อหน้าตั้งค่าแล้วในการ์ด 0006 · ยังไม่ใช้ที่หน้า Login)

```text
กล้อง ─► models.Detector (YuNet) ─► quality.check ─► models.Liveness (MiniFASNet ×2) ─► align.crop 112×112
      ─► models.Embedder (SFace) ─► matching.average (3–5 เฟรม) ─► matching.match (threshold + margin)
pipeline.FaceScanner: process (ต่อเฟรม, จับเวลาทุกขั้น) · scan (1:N) · enroll (ตรง/ซ้าย/ขวา)
store.FaceStore: แม่แบบ 128 ค่า + ความยินยอม + sha256 โมเดล · ~/.local/share/aipc/face-template.json (0600)
pipeline.ScanLog: ~/.local/state/aipc/face-scans.log (ไม่มีภาพ ไม่มี embedding)
```

โมเดลโหลดผ่าน OpenCV อย่างเดียว ตรวจ sha256 ทุกครั้ง (`models/NOTICE.md`) · SFace ดาวน์โหลดด้วย `python -m aipc.vision.models fetch`
เครื่องมือ: `aipc.vision.camera` (ทดลองกับกล้อง) · `aipc.vision.evaluate` (FAR/FRR/EER/ROC/DET) · `aipc.vision.bench` (เวลา/RAM)

**ในหน้าจอ (การ์ด 0006):** `ui/face.py` `FaceController` ห่อ pipeline ให้ QML (`FacePanel.qml` ในหน้าตั้งค่า)

```text
FacePanel (QML) ── startEnroll(ยินยอม) / tryScan / cancel / deleteTemplate ──► FaceController (เธรดหลัก)
                                                                                 │ เปิดเธรดงาน
   ◄── state · advice · posesDone · busy (ข้อความเท่านั้น ไม่มีภาพ/embedding) ── เธรดงาน: กล้อง + FaceScanner
                                                                                 │ เสร็จ/ยกเลิก/กล้องหลุด
                                                                                 └ ปิดกล้อง ปล่อยโมเดล · บันทึกเฉพาะเมื่อสำเร็จ
```

ผลจากเธรดงานส่งกลับเธรดหลักผ่าน signal เท่านั้น · หน้า Login (`--greeter`) สร้าง `FaceController(active=False)` จึงไม่แตะกล้อง

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
                                              └ 6 หน้า          ├ filesBrowser ไฟล์ใน home → files.py (ห้ามออกนอก home)
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
| ฟอร์มสมัคร | ตรวจข้อมูลจริง, รหัสกู้คืนสุ่มจริง (`secrets`) — **แต่ไม่ได้สร้างบัญชีหรือบันทึกอะไร** |
| ช่องพิมพ์แชท | Enter/Shift+Enter/IME ทำงานจริง · ทุกข้อความผ่านตัวคัดสกิล — สั่งงานเครื่อง ถามเครื่อง และจดนัดใช้ได้จริง · **คุยทั่วไป/แปล ไม่มีโมเดลตอบ** |
| นัดหมาย | แปลงวันเวลาด้วยโค้ด ยืนยันก่อนบันทึก เก็บที่ `~/.local/share/aipc/reminders.json` (atomic + .bak) · เตือนเด้งบนจอทุกรอบ 30 วิ · แจ้งนัดที่พลาดตอนเข้าใช้ · **ยังไม่มีหน้ารายการ/ลบนัด ไม่มีเสียงเตือน ไม่มีนัดซ้ำ** · ที่เก็บจริงรอ ADR-004 |
| สั่งงานเครื่อง | บน Linux รัน `xdg-open` / `gtk-launch` / `wpctl` จริง (แบบ list ไม่ผ่าน shell) · **บนวินโดวส์เป็นแบบจำลอง และการ์ดเขียนว่า "จำลอง"** |
| เข้าสู่ระบบ | โหมด greeter (`--greeter`): ส่งให้ greetd/PAM ตรวจจริง · หน้าต่างพัฒนา: ปฏิเสธเสมอนอกโหมดพัฒนา |
| หลังเข้าระบบ | โหมดเซสชัน (`--session`): เริ่มที่ Shell, "ออก" จบเซสชันจริง, ไม่มีโหมดพัฒนา |
| ใบหน้าในหน้าตั้งค่า | ลงทะเบียน 3 ท่า / ทดลองสแกน 1:1 / ลบ ทำงานจริงกับกล้อง (การ์ด 0006) · ขอความยินยอมทุกครั้ง · **ไม่แสดงภาพสดบนจอ** · แถบบนขึ้น "กล้องกำลังใช้" |
| สแกนหน้าที่หน้า Login | **ยังไม่ได้ต่อ** (greeter อ่านแม่แบบใน home ของผู้ใช้ไม่ได้ ต้องมี visiond) · วงกล้องบอก "ยังไม่พร้อม" · ดูหน้าตาได้ด้วย `--demo-scan` |
| หน้า Skill | รายการจากไฟล์สกิลจริง พร้อมบอกว่าตัวไหนใช้ได้ ตัวไหนยังขาดอะไร · **นำเข้า/ให้ AI ช่วยสร้าง ยังไม่มี** |
| ปิดบัง/ล็อก, ความเป็นส่วนตัว, เสียง | **ไม่มี** · หน้าจอบอกว่ายังไม่พร้อมและอยู่เฟสไหน |

โหมดพัฒนา (`--dev` หรือ `--demo-scan`) มีแถบเตือนสีส้มด้านบนตลอดเวลา
