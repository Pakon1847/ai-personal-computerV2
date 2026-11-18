# งานข้ามคืนบน Pi 5 กับ AI จริง · 2026-11-18

การ์ด [0081 ทำข้ามคืน](../../design/0081-overnight-jobs.md) หัวข้อ 8 · Pakon สั่ง "คืนนี้เลย" (2026-11-18)

## ประกาศก่อนรัน (commit ก่อนวัด · รันครั้งเดียว)

- **เครื่อง:** Pi 5 8GB (`ai-pc`) · รันในบัญชี `aipc2030` ผ่าน SSH · ไม่มีคนใช้จอ
- **โค้ด:** สาขา `feature/0081-overnight-jobs` (commit ที่มีไฟล์นี้) · ใช้ venv ของ `/opt/aipc-v2` (รุ่น `f6f794db`) · ตัวรันไม่มีหน้าจอ [`aipc.spikes.overnight_night`](../../../src/aipc/spikes/overnight_night.py) ใช้ `Plan` `Job` `Runner` `LocalAi` ตัวเดียวกับแอป
- **AI:** llama-server เริ่มด้วย `/opt/aipc-v2/scripts/pi/session/aipc-llm-start` ตามค่าใน `/etc/aipc/llm.conf` (Gemma 4 E2B Q4_K_M · 3 thread · context 4096)
- **ชุดเอกสาร (ชุดพัฒนา · ผู้ช่วย AI เลือก):** การ์ดออกแบบภาษาไทย 20 ไฟล์จาก master `57407ba` (`docs/design/0051`–`0058` และ `0060`–`0071`) · sha256 ใน [`docs.sha256`](docs.sha256) · `plan_folder` บนวินโดวส์: 20 ไฟล์ · **57 ก้อน** · ข้าม 0
- ไม่มีการปรับ prompt ก่อนหรือหลังรอบนี้

| # | เกณฑ์ (จากการ์ด) | วัดอย่างไร | ผ่านเมื่อ |
|---|---|---|---|
| J1 | ทำครบ 20/20 · ไม่มีก้อนซ้ำหรือหาย | `result.json` → `j1`: ทุกไฟล์ `done` · จำนวนสรุปก้อน = จำนวนก้อน · ไม่มีก้อนว่าง · มีสรุปภาพรวม | 20/20 |
| J6 | ไม่ออกนอกเครื่อง | sha256 ของ `~/.local/share/aipc/outbound.json` ก่อน = หลัง · `run.log` บันทึก `Seccomp: 2` และการ์ดเครือข่ายที่ตัวรันเห็น (คาดว่าเห็นแค่ `lo`) | ไม่เปลี่ยน · เห็นแค่ `lo` |
| J7 | ถึง 80°C แล้วพักจริง 100% · รายงานเวลารวมและอุณหภูมิสูงสุด | `samples.csv` ทุก 10 วิ · `events.csv` สถานะ `resting` · `rest_seconds` | ถ้าไม่ถึง 80°C เลย = **J7 ไม่ได้ถูกทดสอบ** (ไม่นับว่าผ่าน) · รายงานเวลารวมและอุณหภูมิสูงสุดเสมอ |

**ต่างจากในแอป:** ตัวรันอยู่ใน unit เดียวกับ AI ซึ่งตั้ง `RestrictAddressFamilies=AF_UNIX` + `PrivateNetwork=yes` (ค่าเดียวกับ `aipc-llm.service`) · ในแอป งานรันในโปรเซสหน้าจอซึ่งต่อเน็ตได้ แต่โค้ดงานไม่มีส่วนที่เรียกคลาวด์ · J6 รอบนี้จึงยืนยันได้แค่ว่า "AI กับตัวงานทำงานครบโดยไม่ต้องใช้เน็ต"

**ไม่วัดคืนนี้:** J2 ดึงปลั๊กจริง (ต้องถาม Pakon ก่อนทุกครั้ง) · J3 แชทแทรก และ J8 ออกจากระบบระหว่างงาน (ต้องมีคนที่จอ · นัด 2026-11-23) · J4 ต้องใช้ชุดทดสอบที่คนอื่นเขียน · J5 คำสั่งแฝงในเอกสาร

**กันเหตุ:** มีคนเข้าระบบที่จอระหว่างคืน → `run.sh` ส่ง SIGTERM ให้งานหยุด (job.json = paused ทำต่อได้) เพราะ memory cgroup ปิดอยู่ AI สองตัวพร้อมกันเสี่ยง RAM หมด · หยุดแบบนี้ = บันทึกตามจริง ไม่รันใหม่ทั้งหมด (ทำต่อจากงานเดิมได้)

**ทดลองระบบก่อนรัน (ไม่นับผล):** 1 ไฟล์ (`0068` · 1 ก้อน) ในโฟลเดอร์ผลแยก `smoke/` เพื่อดูว่าสคริปต์ต่อ AI ได้ · ไม่ใช้ปรับอะไร

## วิธีรัน

```bash
# บน Pi · ชุดเอกสารจาก checkout ของ master
mkdir -p ~/overnight-1118/docs && cd ~/aipc-master/docs/design && cp 005[1-8]-*.md 006[0-9]-*.md 007[01]-*.md ~/overnight-1118/docs/
cd ~/overnight-1118/docs && sha256sum -c ~/aipc-0081/docs/benchmarks/2026-11-18-overnight-pi5/docs.sha256
# unit ชั่วคราวของ systemd (ไม่ตายเมื่อปิด SSH เพราะ KillUserProcesses=yes)
sudo systemd-run --unit=aipc-night-1118 --uid=aipc2030 --property=RestrictAddressFamilies=AF_UNIX \
  --property=PrivateNetwork=yes --property=Nice=5 --setenv=HOME=/home/aipc2030 \
  /bin/sh /home/aipc2030/aipc-0081/docs/benchmarks/2026-11-18-overnight-pi5/run.sh
```

ผลอยู่ที่ `~/overnight-1118/out/` (`run.log` `events.csv` `samples.csv` `result.json` `summaries/` `jobs/`) → คัดมาไว้ที่ `result-2026-11-18/`

## บันทึกการตั้งเวลา (ไม่เปลี่ยนเกณฑ์/ชุดข้อมูล/โค้ด)

- 2026-11-18 ~08:25 ทดลองระบบ 1 ไฟล์ (`smoke/` · ไม่นับผล): 1/1 · 143 วิ · `Seccomp: 2` · เห็นแค่ `lo` · outbound ไม่เปลี่ยน · ขึ้นถึง 83.7°C (throttled `0xe0008`)
- ตั้ง timer ชั่วคราว `aipc-night-1118` 22:00 · **Pi รีบูตราว 18:00 (ไม่ทราบสาเหตุ · journal ไม่เก็บข้ามบูต) → timer หาย งานไม่ได้เริ่ม** (พบ 19:32)
- Pakon สั่งเลื่อน (2026-11-18 19:30): **เริ่ม 2026-11-19 06:30** · timer `aipc-night-1119` · ถ้ามีคนเข้าระบบที่จอระหว่างรัน = งานหยุดเอง (ทำต่อได้)

## ผล

(ยังไม่รัน)
