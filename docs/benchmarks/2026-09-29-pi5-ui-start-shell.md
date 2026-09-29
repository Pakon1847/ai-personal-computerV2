# 2026-09-29-pi5-ui-start-shell

**ใช้เป็นหลักฐานระดับ 4 ได้** (Pi 5, ไม่ throttle, ผูกกับ commit)


## ผล (วินาที ไม่รวม warm-up)

| n | median | p95 | min | max |
|---|---|---|---|---|
| 10 | 1.1963 | 1.2213 | 1.1868 | 1.2213 |

p95 คำนวณแบบ nearest-rank · เมื่อ n = 10 p95 คือลำดับที่ 10 จาก 10 ของค่าที่เรียงแล้ว

## เครื่อง

- บอร์ด: Raspberry Pi 5 Model B Rev 1.0 (pi5)
- RAM: 8062 MB
- OS: Debian GNU/Linux 13 (trixie) · kernel 6.18.50+rpt-rpi-2712 · Python 3.13.5
- commit: e7426ceb5ced6ad7fd305fe72118409d427f1b8c (มีไฟล์ค้างแก้: False)
- อุณหภูมิตอนเริ่ม: 54.0 °C

## คำสั่งที่วัด

```
./.venv/bin/python -m aipc.ui --session --software --screenshot /tmp/ui-start.png
```

## ค่าที่ตั้ง

- screen: shell
- mode: session-offscreen-software
- note: includes-600ms-screenshot-delay

## หมายเหตุของผู้วัด

(เขียนเพิ่มเองด้วยมือ: ไฟ, cooler, รุ่น SD/SSD, สิ่งที่เห็นผิดปกติ)
