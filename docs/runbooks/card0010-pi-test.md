# ทดสอบการ์ด 0010 กับคนจริงบน Pi 4 (ลงทะเบียน 5 ท่า + ภาพสด + เทียบ 3 vs 5 ท่า)

เกณฑ์อยู่ใน [การ์ด 0010 ข้อ 8](../design/0010-face-enroll-preview.md) · ประกาศก่อนสร้างแล้ว ห้ามแก้หลังเห็นผล

## 0. อัปเดตแอปที่หน้าจอใช้ (ครั้งเดียว · ต้องใช้รหัส sudo)

ที่ตัว Pi: **Ctrl+Alt+F2** → login → 

```bash
cd ~/aipc && ./scripts/pi/update-app.sh            # ดูก่อน (ไม่เปลี่ยนอะไร)
sudo ./scripts/pi/update-app.sh --apply           # ทำจริง ~1–2 นาที (ต้องมีเน็ต)
cat /opt/aipc-v2/.installed-commit                # ต้องตรงกับ git log --oneline -1
exit
```

**Ctrl+Alt+F7** กลับหน้าจอ V2 → กด **ออก** → login ใหม่ (หน้าจอโหลดรุ่นใหม่) · พังเมื่อไร: `sudo ./scripts/pi/update-app.sh --rollback`

## 1. เริ่มตัวบันทึก (ผู้ช่วยทำผ่าน SSH)

```bash
cp ~/.local/state/aipc/face-scans.log ~/scans-before-0010.log 2>/dev/null
setsid ~/aipc/scripts/pi/sample-session.sh ~/card0010.tsv </dev/null >/dev/null 2>&1 &
```

## 2. ในหน้าจอ V2 (Pakon)

1. ตั้งค่า → ใบหน้าของฉัน → **ลงทะเบียนใหม่** → ยินยอม
2. ทำตามลูกศร: ตรง → ซ้าย → ขวา → เงย → ก้ม · ดูว่า **ภาพกลับด้านเหมือนกระจก** และ **ติ๊กถูกท่า** (หันซ้ายของตัวเอง = ช่อง "ซ้าย")
3. จดความรู้สึก: ภาพกระตุกไหม · ลูกศรเข้าใจง่ายไหม · ท่าไหนทำยาก
4. **ทดลองสแกน 10 ครั้ง**

## 3. เทียบ 3 vs 5 ท่า (ที่ tty2 · หน้าจอ V2 ต้องไม่ใช้กล้องอยู่)

```bash
cd ~/aipc && ./.venv/bin/python -m aipc.vision.camera compare --times 10
```

ยินยอม → ทำ 5 ท่า → นั่งหน้าตรงให้สแกน 10 ครั้ง · **ไม่บันทึกแม่แบบ** · ผลอยู่ใน `~/.local/state/aipc/face-compare.log`

## 4. เก็บผล (ผู้ช่วยทำผ่าน SSH)

- `~/card0010.tsv` → เวลาลงทะเบียน (กล้องเปิด → แม่แบบบันทึก), RSS สูงสุด/หลังจบ
- `face-enroll.log` บรรทัดล่าสุด → ผล, ท่าที่ขาด, `frames_seen ÷ seconds` = อัตราภาพสด
- `face-scans.log` บรรทัดหลัง `~/scans-before-0010.log` → สแกน 10 ครั้ง
- `face-compare.log` → ตัดสินข้อ 1 ของ Pakon: ใส่เงย/ก้มในแม่แบบ **เฉพาะเมื่อ** `five_not_worse = true`
- เขียนผลใน `docs/benchmarks/<วันที่>-card0010-pi4/README.md` แล้ว commit
