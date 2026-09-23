# Runbook: เปลี่ยน Pi 4 จากระบบเก่ามาใช้หน้าจอ V2

ผู้ใช้เลือกแบบปลอดภัย (2026-09-23): **ไม่ลบอะไรทิ้งถาวร · ทุกขั้นย้อนกลับได้ · ดูของจริงก่อนแล้วค่อยเปลี่ยน**

## ทำไมต้องระวัง

ระบบเก่า `D:\ai computer` ไม่ได้เป็นแค่แอป แต่ **เป็นหน้า login ของเครื่องทั้งเครื่อง**
(ตามเอกสารของ repo เก่า — ยังไม่ได้ยืนยันกับเครื่องจริง):

- ปิด lightdm แล้วเปิด **greetd** ที่รัน `/usr/local/bin/ai-pc-greeter` (`deploy/greetd/README.md:22`)
- แก้ **PAM** `/etc/pam.d/greetd` ให้ใบหน้าเข้าเครื่องได้ (`docs/operations.md:150`) · มีสำเนา `.before-006`
- ตั้ง lightdm ให้ autologin เข้า session `ai-pc` ไว้ (ยังค้างอยู่ในไฟล์ แม้ lightdm ถูกปิด)
- ติดตั้งไฟล์ใน `/opt/ai-pc`, `/usr/local/bin/ai-pc-*`, `ai-pc-control.service`, user unit `ai-pc-remote-screen`

ถ้าปิด greetd ผิดวิธี = เปิดเครื่องแล้วไม่มีหน้า login ให้เข้า · จึงต้องมี **ทางเข้าสำรอง** ก่อนทุกครั้ง

`D:\ai-pc-2` ไม่ได้ตั้งให้เปิดเอง แต่สร้างบ้านเข้ารหัส + แก้ `/etc/fstab` และสร้างผู้ใช้ `usera` `userb`
→ ผู้ใช้สั่งเอาออก (2026-09-23): `sudo ./scripts/pi/remove-ai-pc-2.sh --apply` (รันแบบไม่มี --apply ดูก่อน)
· ไม่แตะ greetd/lightdm/PAM · สำรอง /etc/fstab ก่อนแก้ · บีบอัดโค้ด ~/ai-pc-2 เก็บไว้ก่อนลบ

## ขั้นที่ 1 · เอา repo V2 ขึ้น Pi

ตาม [pi-phase0.md ข้อ 1](pi-phase0.md#1-เอา-repo-ขึ้น-pi) (git bundle → `git clone ~/aipc.bundle ~/aipc`)

## ขั้นที่ 2 · ตรวจของจริง (อ่านอย่างเดียว)

```bash
cd ~/aipc
./scripts/pi/check-old-system.sh
```

ส่งไฟล์ `~/aipc-old-system-report.txt` กลับมา · และลองกด **Ctrl+Alt+F2** ที่หน้าจอ Pi ว่า login
ด้วยชื่อ/รหัสผ่านในหน้าจอตัวหนังสือได้ไหม (กด Ctrl+Alt+F7 กลับ) — นี่คือทางเข้าสำรอง

## ขั้นที่ 3 · เอาระบบเก่าออก (ยังไม่เขียน)

จะเขียนหลังเห็นผลขั้นที่ 2 เท่านั้น · หลักที่ใช้:

- **ย้ายไปเก็บ ไม่ลบ** — ทุกไฟล์ย้ายไปที่ `/root/aipc-old-backup-<วันที่>/` พร้อมสคริปต์ย้อนกลับ
- ปิด greetd / `ai-pc-control` ด้วย `systemctl disable` (ไม่ถอนแพ็กเกจ)
- คืน lightdm เป็นหน้า login ปกติของ Raspberry Pi OS (เอาบรรทัด autologin เข้า `ai-pc` ออก)
- คืน `/etc/pam.d/greetd` จากสำเนา `.before-006`
- โหมดดูก่อน (dry-run) เป็นค่าเริ่มต้น · ทำจริงเมื่อ Pakon สั่งเท่านั้น
- ต้องผ่านขั้นที่ 2 เรื่องทางเข้าสำรองก่อน

## ขั้นที่ 4 · ให้หน้าจอ V2 เปิดเองหลังเข้าเดสก์ท็อป

```bash
./scripts/pi/install-ui.sh            # ดูก่อน ไม่เปลี่ยนอะไร
./scripts/pi/install-ui.sh --apply    # ทำจริง: สร้าง .venv + ~/.config/autostart/aipc-ui.desktop
```

- ออกจากแอปเต็มจอ: **Ctrl+Alt+Q**
- เอาออก: `./scripts/pi/install-ui.sh --uninstall`
- สคริปต์หยุดเองถ้า glibc < 2.39 (ติดตั้ง PySide6 จาก pip ไม่ได้) — ต้องดูรุ่น OS จากผลขั้นที่ 2 ก่อน
- เปิดแบบ `--dev` เพราะ Login ของ V2 ยังไม่ตรวจรหัสผ่านจริง (มีแถบส้มบอกตลอด)
  · การให้ V2 เป็นหน้า login ของเครื่องจริง ต้องทำ PAM + greetd ก่อน (การ์ดออกแบบแยก)
