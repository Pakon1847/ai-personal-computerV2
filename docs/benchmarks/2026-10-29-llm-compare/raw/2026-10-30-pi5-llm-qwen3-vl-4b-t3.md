# 2026-10-30-pi5-llm-qwen3-vl-4b-t3

**ยังใช้เป็นหลักฐานระดับ 4 ไม่ได้**

- คำเตือน: ไฟตกหรือร้อนเกินระหว่างรอบ [1, 2, 5] — ผลชุดนี้ใช้ไม่ได้ ต้องวัดใหม่
- คำเตือน: get_throttled ก่อนวัด = 0xe0000 (เคยลดความเร็วตั้งแต่บูต) — ตรวจไม่ได้ว่าเกิดซ้ำระหว่างวัดไหม · ไม่นับเป็นระดับ 4 · รีบูตแล้ววัดใหม่
- คำเตือน: มีไฟล์ที่ยังไม่ commit ตอนวัด — ผลนี้ไม่ได้ผูกกับ commit ใดจริง

## ผล (วินาที ไม่รวม warm-up)

| n | median | p95 | min | max |
|---|---|---|---|---|
| 5 | 48.9311 | 49.3390 | 47.4017 | 49.3390 |

p95 คำนวณแบบ nearest-rank · เมื่อ n = 5 p95 คือลำดับที่ 5 จาก 5 ของค่าที่เรียงแล้ว

## ค่าที่โปรแกรมรายงาน (ไม่รวม warm-up)

| ค่า | n | median | p95 | min | max |
|---|---|---|---|---|---|
| peak_rss_mb | 5 | 4870 | 4870 | 4869 | 4870 |
| pp_tok_s | 5 | 14.45 | 14.8 | 14.36 | 14.8 |
| prefill_s | 5 | 13.84 | 13.93 | 13.51 | 13.93 |
| tg_tok_s | 5 | 4.353 | 4.388 | 4.348 | 4.388 |

ค่าที่ "ยิ่งสูงยิ่งดี" (เช่น tok/s) ให้ดู min แทน p95 — p95 ของ tok/s คือรอบที่เร็ว ไม่ใช่รอบที่แย่

## เครื่อง

- บอร์ด: Raspberry Pi 5 Model B Rev 1.0 (pi5)
- RAM: 8062 MB
- OS: Debian GNU/Linux 13 (trixie) · kernel 6.18.50+rpt-rpi-2712 · Python 3.13.5
- commit: 7ea91916ab8a47c19ed5ff1f14168f68ca3fb370 (มีไฟล์ค้างแก้: True)
- อุณหภูมิตอนเริ่ม: 62.8 °C

## คำสั่งที่วัด

```
/home/aipc2030/llama.cpp/build/bin/llama-bench -m /mnt/bench-usb/bench-models/Qwen3-VL-4B-Instruct-Q4_K_M.gguf -t 3 -p 200 -n 64 -r 1 -o json
```

## ค่าที่ตั้ง

- threads: 3
- prompt_tokens: 200
- gen_tokens: 64
- size_class: 3-4b
- ttft_target_s: 10.0
- llama_cpp: 86ea01d

## ไฟล์ที่ใช้ (sha256)

- `/mnt/bench-usb/bench-models/Qwen3-VL-4B-Instruct-Q4_K_M.gguf` d4dcd426bfba75752a312b266b80fec8136fbaca13c62d93b7ac41fa67f0492b

## หมายเหตุของผู้วัด

(เขียนเพิ่มเองด้วยมือ: ไฟ, cooler, รุ่น SD/SSD, สิ่งที่เห็นผิดปกติ)
