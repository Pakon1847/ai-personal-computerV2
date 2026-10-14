---
name: pi-deploy
description: ส่งโค้ดของโปรเจกต์ AI Personal Computer V2 ขึ้น Raspberry Pi 5 / รันเทสต์บน Pi / ติดตั้งด้วยสคริปต์ scripts/pi (--apply) / ย้อนรุ่น / restart หน้าเข้าสู่ระบบ อย่างปลอดภัยตามกฎเหล็กข้อ 1 ใช้เมื่อ ส่งโค้ดขึ้น Pi · deploy · ติดตั้งบน Pi · update-app · รันเทสต์บน Pi · ย้อนรุ่นบน Pi
argument-hint: "[สาขาหรือ commit] [แค่ทดสอบ | ติดตั้งแอป | ติดตั้งสคริปต์ <ชื่อ>]"
---

# ส่งโค้ดและติดตั้งบน Pi 5

**กฎที่ห้ามข้าม** (CLAUDE.md กฎเหล็กข้อ 1–2):
- ทุกสคริปต์ที่แตะระบบรัน **โหมดดูก่อน** (ไม่มี `--apply`) → แสดงผลให้ Pakon → ได้ "ใช่" ในบทสนทนานี้ก่อนจึง `--apply`
- ฟีเจอร์บนสาขาที่ **ยังไม่ผ่านเกณฑ์ในการ์ด** ติดตั้งได้เมื่อ Pakon อนุมัติชัด ๆ เท่านั้น และบันทึกการอนุมัติลงการ์ด
- **ห้าม restart หน้าเข้าสู่ระบบ** ระหว่างมีคนใช้หน้าจอ
- **รหัส sudo ส่งทาง stdin เท่านั้น** (`sudo -S -p ""`) · ห้ามเขียนลงไฟล์ สคริปต์ commit เอกสาร หรือหน่วยความจำ ·
  ถ้าบทสนทนานี้ยังไม่มีรหัส ให้ขอ Pakon (อย่าเดา อย่าค้นจากไฟล์)

## 0. หา Pi และดูว่ามีคนใช้อยู่ไหม

```bash
ssh -o BatchMode=yes -o ConnectTimeout=6 aipc2030@<IP> 'hostname; uptime -p; vcgencmd measure_temp; who; loginctl list-sessions --no-legend'
```
- IP เปลี่ยนได้ (hotspot) · ลอง IP ล่าสุดในหน่วยความจำ/บทสนทนาก่อน · `ai-pc.local` มักติด host key → อย่าแก้ known_hosts เองโดยไม่ถาม
- `seat0` เป็น `_greetd` = ไม่มีใครเข้าระบบที่จอ · เป็นชื่อผู้ใช้ = **มีคนใช้อยู่**

## 1. ส่งโค้ด (git bundle · Pi ไม่ดึงจาก GitHub)

```bash
# บนโน้ตบุ๊ก (Git Bash) · <base> = commit ที่ Pi มีอยู่แล้ว (ดูด้วย ssh … 'cd ~/<checkout> && git log --oneline -1')
B="$(mktemp -d)/x.bundle"; git bundle create "$B" <base>..<สาขา>
scp -q "$B" aipc2030@<IP>:/tmp/x.bundle        # scp ของวินโดวส์อ่าน path แบบ C:/… ไม่ใช่ /c/…
ssh aipc2030@<IP> 'cd ~/<checkout> && git status --short && git fetch -q /tmp/x.bundle <สาขา> && git merge -q --ff-only FETCH_HEAD && git log --oneline -1 && rm /tmp/x.bundle'
```
- `git status` บน Pi มีไฟล์ค้างแก้ → **อย่าทิ้งทันที** · เทียบ sha256 กับใน commit ก่อน · ไม่ตรง = ถาม Pakon
- `--ff-only` ไม่ผ่าน = ประวัติแยกทาง → หยุดแล้วถาม (ห้าม reset --hard)
- โฟลเดอร์ชั่วคราว (scratchpad / mktemp) อาจหายระหว่าง session → อย่าเก็บของที่ต้องใช้ต่อไว้ที่นั่น

## 2. รันเทสต์บน Pi (หลักฐานเกณฑ์ "ไม่กระทบของเดิม")

```bash
ssh aipc2030@<IP> 'cd ~/<checkout> && QT_QPA_PLATFORM=offscreen PYTHONPATH=src timeout 900 <venv>/bin/python -m unittest discover -s tests -t . 2>&1 | grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)"'
```
รายงานเป็นตัวเลข: ผ่าน / ล้ม / **ถูกข้าม** (ถูกข้าม ≠ ผ่าน) · บอก commit ที่รัน

## 3. ติดตั้ง (เฉพาะเมื่อ Pakon อนุมัติ)

| อะไร | ดูก่อน | ทำจริง |
|---|---|---|
| แอป (โฟลเดอร์ต่อรุ่น · ADR-009) | `./scripts/pi/update-app.sh` | `sudo -S -p "" ./scripts/pi/update-app.sh --apply` |
| ย้อนรุ่นแอป (ไม่ใช้เน็ต) | — | `sudo -S -p "" ./scripts/pi/update-app.sh --rollback` |
| สคริปต์ติดตั้งอื่น (`install-*.sh`) | `./scripts/pi/install-<ชื่อ>.sh [ตัวเลือก]` | เติม `--apply` |

รูปแบบส่งรหัส: `ssh aipc2030@<IP> 'cd ~/<checkout> && sudo -S -p "" <คำสั่ง>' <<< "<รหัสจาก Pakon>"`

- `update-app.sh --apply` ลองเปิดหน้าเข้าสู่ระบบ + หน้าจอเซสชันแบบไม่มีจอก่อนสลับรุ่นเอง · จดรุ่นก่อนหน้าไว้บอก Pakon (ทางย้อนกลับ)
- หน้าเข้าสู่ระบบที่เปิดค้างยังเป็นรุ่นเดิม: ไม่มีใครใช้จอ → `sudo systemctl restart greetd` · มีคนใช้ → บอกให้ออกจากระบบแล้วเข้าใหม่ (รอจนว่างค่อย restart)

## 4. งานที่รันนาน / วัดผล

- Pi ตั้ง `KillUserProcesses=yes` → ปิด SSH แล้วโปรเซสตาย · ใช้ Bash แบบ `run_in_background` ให้ SSH ค้างไว้ หรือ `sudo systemd-run --unit=<ชื่อ> --uid=aipc2030 …`
- วัดเวลา/RAM: บันทึก `vcgencmd measure_temp` + `vcgencmd get_throttled` ก่อน/หลัง · รอให้ < 65°C ก่อนแต่ละรอบ · ใช้ skill `measure-h9`

## 5. หลังทำเสร็จ

- อัปเดต `docs/STATUS.md` (รุ่นที่ติดตั้ง · ผลเทสต์บน Pi) และการ์ดที่เกี่ยว · commit
- บอก Pakon: ติดตั้งอะไร รุ่นไหน · ต้องออกจากระบบ/เข้าใหม่ไหม · **คำสั่งย้อนกลับ**
