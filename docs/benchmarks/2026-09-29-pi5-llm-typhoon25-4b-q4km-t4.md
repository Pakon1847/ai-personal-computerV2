# 2026-09-29-pi5-llm-typhoon25-4b-q4km-t4

**ยังใช้เป็นหลักฐานระดับ 4 ไม่ได้**

- คำเตือน: ไฟตกหรือร้อนเกินระหว่างรอบ [0, 1, 2, 3, 4, 5] — ผลชุดนี้ใช้ไม่ได้ ต้องวัดใหม่

## ผล (วินาที ไม่รวม warm-up)

| n | median | p95 | min | max |
|---|---|---|---|---|
| 5 | 43.3571 | 43.7547 | 41.8242 | 43.7547 |

p95 คำนวณแบบ nearest-rank · เมื่อ n = 5 p95 คือลำดับที่ 5 จาก 5 ของค่าที่เรียงแล้ว

## ค่าที่โปรแกรมรายงาน (ไม่รวม warm-up)

| ค่า | n | median | p95 | min | max |
|---|---|---|---|---|---|
| peak_rss_mb | 5 | 4866 | 4866 | 4866 | 4866 |
| pp_tok_s | 5 | 17.87 | 18.11 | 17.79 | 18.11 |
| prefill_s | 5 | 11.19 | 11.24 | 11.04 | 11.24 |
| tg_tok_s | 5 | 4.387 | 4.403 | 4.319 | 4.403 |

ค่าที่ "ยิ่งสูงยิ่งดี" (เช่น tok/s) ให้ดู min แทน p95 — p95 ของ tok/s คือรอบที่เร็ว ไม่ใช่รอบที่แย่

## เครื่อง

- บอร์ด: Raspberry Pi 5 Model B Rev 1.0 (pi5)
- RAM: 8062 MB
- OS: Debian GNU/Linux 13 (trixie) · kernel 6.18.50+rpt-rpi-2712 · Python 3.13.5
- commit: 86e7ab8b99456ee065f8a577c26bf97e4e1ffbd6 (มีไฟล์ค้างแก้: False)
- อุณหภูมิตอนเริ่ม: 51.25 °C

## คำสั่งที่วัด

```
/home/aipc2030/llama.cpp/build/bin/llama-bench -m models/typhoon2.5-qwen3-4b-q4_k_m.gguf -t 4 -p 200 -n 64 -r 1 -o json
```

## ค่าที่ตั้ง

- threads: 4
- prompt_tokens: 200
- gen_tokens: 64
- size_class: 3-4b
- ttft_target_s: 10.0
- llama_cpp: 86ea01d

## ไฟล์ที่ใช้ (sha256)

- `models/typhoon2.5-qwen3-4b-q4_k_m.gguf` b365302922688f3a3c9ac8e3c00ab97a152cac0cdbf4eb5a734ecb483ae3e511

## หมายเหตุของผู้วัด

(เขียนเพิ่มเองด้วยมือ: ไฟ, cooler, รุ่น SD/SSD, สิ่งที่เห็นผิดปกติ)
