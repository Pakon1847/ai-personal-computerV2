# ติดตั้ง visiond บน Pi 5 + ตรวจสิทธิ์ (การ์ด 0015 ⑥ ส่วนที่ไม่ต้องใช้กล้อง) · 2026-09-30

รุ่นแอป `e2528b5d` (update-app.sh) · `sudo ./scripts/pi/install-visiond.sh --apply` · เทสต์ทั้งชุดบน Pi 5 ผ่าน ·
**ยังไม่มีกล้องต่อ** (มีแต่โหนดวิดีโอของชิป) → การสแกนจริง/เวลา/ความแม่นยำ ยังไม่ได้วัด

## ติดตั้ง

- ผู้ใช้ `_aipcvision` · `aipc-visiond.service` active · log "visiond พร้อม"
- `/run/aipc-vision/visiond.sock` 0666 · `/run/aipc-vision/visiond-root.sock` 0600 (เจ้าของ `_aipcvision`)
- `sudo -l -U _aipcvision` = `(root) NOPASSWD: /usr/local/sbin/aipc-accounts ""` คำสั่งเดียว
- `/etc/pam.d/greetd`: บรรทัดที่ 2 `auth [success=done default=ignore] pam_exec.so quiet /usr/local/sbin/aipc-face-pass` ·
  บรรทัดท้าย `session optional pam_exec.so ...` · สำรองเดิมที่ `/var/lib/aipc/greetd.pam.before-visiond`

## ตรวจ (ผ่านทุกข้อ)

| # | ทำ | ผล |
|---|---|---|
| 1 | ผู้ใช้ทั่วไป (aipc2030) สั่ง identify | ปฏิเสธ "ใช้ได้ที่หน้า Login เท่านั้น" |
| 2 | ถามสถานะของตัวเอง | `disabled` |
| 3 | aipc2030 สั่งปิดใบหน้าของ pakon2 | ปฏิเสธ "ทำได้เฉพาะบัญชีของตัวเอง" |
| 4 | ปิดใบหน้าของตัวเองด้วยรหัสผิด (visiond → sudo → ตัวช่วย root → PAM) | `bad-password` |
| 5 | รหัสถูก | `removed` |
| 6 | ผู้ใช้ทั่วไปต่อ socket ของ root | `PermissionError` |
| 7 | `aipc-face-pass` (root) ไม่มีตั๋ว | exit 1 (PAM ไปถามรหัสผ่าน) |
| 8 | PAM service `greetd` ด้วยรหัสผ่าน ถูก / ผิด | `True` / `False` (บรรทัดใบหน้าไม่ทำให้รหัสผ่านพัง) |
| 9 | log ของ visiond | มีแต่ชื่อบัญชีและผล ไม่มีคะแนนหรือเวกเตอร์ |

## หลักฐานข้างเคียง

- บัญชี `pakon2` สมัครจากหน้า Login และล็อกอินที่จออยู่ (seat0 tty7) → L1 + L2 ของ runbook ทดสอบ Login ผ่านโดย Pakon

## ยังไม่ได้ (ต้องต่อกล้อง)

สมัคร → ขั้นใบหน้า → ออก → หน้า Login สแกนแล้วเข้าเอง · กด "ไม่ใช่ฉัน" · ผิด 5 ครั้ง · ตั๋ว 30 วิ บนเครื่องจริง ·
เวลาระบุบัญชี (เกณฑ์ BRIEF มัธยฐาน ≤ 1.5 วิ) · checklist `docs/runbooks/face-accuracy-checklist.md`
