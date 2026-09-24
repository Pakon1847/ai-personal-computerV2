# Runbook: ลง Pi 4 ใหม่หมด แล้วใช้หน้า Login ของ V2

ผู้ใช้สั่ง (2026-09-23): "ทำใหม่ เอาของเดิมออกให้หมด"

**ทำไมลง OS ใหม่ ดีกว่าไล่ลบทีละชิ้น:** ระบบเก่า `ai computer` แก้ไฟล์ระบบไว้หลายที่ (greetd, PAM,
lightdm, `/boot/firmware/cmdline.txt`, `/usr/local/bin`, `/opt`, systemd) และ `ai-pc-2` แก้ `/etc/fstab`
การไล่ลบทีละไฟล์เสี่ยงลืมบางชิ้นหรือลบผิด · ลง OS ใหม่ = ของเก่าหายหมดในครั้งเดียว และ **ลงซ้ำได้เสมอ**
ถ้าอะไรพัง (เครื่องไม่มีทางเสียถาวรจากขั้นนี้) · และได้ glibc ใหม่พอสำหรับ PySide6

> สคริปต์ `check-old-system.sh` / `remove-ai-pc-2.sh` ไม่ต้องใช้แล้วถ้าลงใหม่ · เก็บไว้เผื่อเครื่องอื่น

## ขั้นที่ 0 · เก็บของที่อยากเก็บ (ข้ามได้)

ทุกอย่างบนการ์ด SD จะหายหมด · repo เก่าบนวินโดวส์ (`D:\ai computer`, `D:\ai-pc-2`) **ไม่หาย**
ถ้ามีผลวัดบน Pi ที่ยังไม่ได้ส่งกลับ ให้คัดลอกออกก่อน เช่น:

```bash
tar -czf ~/pi4-old-results.tar.gz ~/ai-pc-2/benchmarks ~/ai-pc/benchmarks 2>/dev/null
```

แล้วคัดลอก `~/pi4-old-results.tar.gz` ใส่ USB

## ขั้นที่ 1 · ลง Raspberry Pi OS ใหม่ (ทำบนวินโดวส์)

1. ปิด Pi ถอดการ์ด SD มาเสียบคอม
2. เปิด **Raspberry Pi Imager** → Device: **Raspberry Pi 4** → OS: **Raspberry Pi OS (64-bit)** (มีเดสก์ท็อป)
3. Storage: เลือกการ์ด SD — ⚠️ **ดูขนาดให้ตรงกับการ์ด อย่าเลือกไดรฟ์อื่นของคอม** (ขั้นนี้ลบทุกอย่างในไดรฟ์ที่เลือก)
4. Edit settings: ตั้งชื่อผู้ใช้ + รหัสผ่าน · hostname · Wi-Fi · แท็บ Services: **เปิด SSH** (ทางเข้าสำรอง)
5. Write → รอเสร็จ → เสียบการ์ดคืน Pi → เปิดเครื่อง → login ให้ถึงเดสก์ท็อป

ตรวจรุ่น OS (ต้องได้ trixie และ glibc ≥ 2.39):

```bash
grep VERSION_CODENAME /etc/os-release
ldd --version | head -1
```

ถ้ายังเป็น bookworm / glibc 2.36 → หยุด ส่งผลมาก่อน (PySide6 จาก pip ใช้ไม่ได้)

## ขั้นที่ 2 · เอา repo V2 ขึ้น Pi

บนวินโดวส์ `aipc.bundle` อยู่ที่ `D:\ai-personal-computerV2\aipc.bundle` (สร้างใหม่ทุกครั้งที่ commit สำคัญ)
คัดลอกไปที่ Pi (USB หรือ `scp aipc.bundle <ผู้ใช้>@<hostname>.local:~`) แล้ว:

```bash
git clone ~/aipc.bundle ~/aipc
cd ~/aipc
python3 -m venv .venv && ./.venv/bin/pip install -e ".[ui,vision]"
./.venv/bin/python -m aipc.vision.models fetch          # โมเดลใบหน้า SFace (การ์ด 0005)
./.venv/bin/python -m unittest discover -s tests -t .      # ต้องผ่าน
./.venv/bin/python -m aipc.ui --dev --fullscreen            # ลองดูหน้าจอ · ออกด้วย Ctrl+Alt+Q
```

## ขั้นที่ 3 · ตรวจทางเข้าสำรอง (ต้องทำก่อนขั้นที่ 4)

- กด **Ctrl+Alt+F2** → login ด้วยชื่อ/รหัสผ่านในหน้าจอตัวหนังสือได้ → **Ctrl+Alt+F7** กลับ
- จากคอมเครื่องอื่น: `ssh <ผู้ใช้>@<hostname>.local` เข้าได้

## ขั้นที่ 4 · ให้หน้า Login ของ V2 เป็นหน้า login จริง

> ภาพ OS ตั้งแต่ 2026-04-13 **ไม่มี sudo แบบไม่ใส่รหัสผ่านแล้ว** — `sudo` จะถามรหัสผ่าน เป็นเรื่องปกติ
> เซสชันเดสก์ท็อปที่สคริปต์เลือก: `/usr/share/wayland-sessions/rpd-labwc.desktop` → `Exec=/usr/bin/labwc-pi` (trixie)

```bash
./scripts/pi/install-greeter.sh                # ดูก่อน · ไม่เปลี่ยนอะไร · อ่านว่าเซสชันถูกตัวไหม
sudo ./scripts/pi/install-greeter.sh --apply   # ทำจริง · จะถามให้พิมพ์ YES ยืนยันขั้นที่ 3
# หลัง login เข้าหน้าจอ V2 เลย ไม่ใช่เดสก์ท็อป Pi (การ์ด 0004) — ที่ใช้อยู่บน Pi 4 ตอนนี้:
sudo ./scripts/pi/install-greeter.sh --apply --session v2
sudo reboot
```

ตรวจตามเกณฑ์การ์ด 0003 ข้อ 9 แล้วจดผล:

| ทดสอบ | ผล |
|---|---|
| เปิดเครื่องแล้วขึ้นหน้า Login ของ V2 (ไม่มีแถบส้ม) | |
| รหัสผิด → อยู่หน้าเดิม ข้อความ "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" ช่องรหัสว่าง | |
| รหัสถูก → เข้าเดสก์ท็อป | |
| รีบูต 3 ครั้ง ขึ้นหน้า Login ของ V2 ทุกครั้ง | |
| Ctrl+Alt+F2 ใช้ได้ขณะอยู่หน้า Login ของ V2 | |
| `--rollback` แล้วรีบูต กลับเป็นหน้า login เดิมได้ | |

**ถ้าหน้า Login ใหม่ไม่ขึ้นหรือเข้าไม่ได้:** Ctrl+Alt+F2 (หรือ SSH) → login →
`sudo ~/aipc/scripts/pi/install-greeter.sh --rollback` → `sudo reboot`

## ขั้นที่ 5 (ทางเลือก) · หน้าจอ V2 เปิดเองหลังเข้าเดสก์ท็อป

```bash
./scripts/pi/install-ui.sh && ./scripts/pi/install-ui.sh --apply
```
