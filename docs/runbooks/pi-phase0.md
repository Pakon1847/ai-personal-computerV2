# Runbook: รันเฟส 0 บน Pi

ขั้นตอนที่ Pakon ทำเองบนเครื่อง Pi · **ทุกคำสั่งในไฟล์นี้ไม่แตะไฟล์บูต พาร์ทิชัน หรือ /etc/fstab**
สิ่งที่ทำมีแค่ ติดตั้งแพ็กเกจ, สร้างไฟล์ใน home, อ่านค่าเครื่อง

ทำบน Pi 5 ก่อน (เครื่องจริง) · Pi 4 ใช้ซ้อมได้ แต่ผลจาก Pi 4 ไม่นับเป็นระดับ 4

## 1. เอา repo ขึ้น Pi

repo นี้ยังไม่มีบน GitHub · วิธีที่ไม่ต้องตั้งอะไรเพิ่มคือ git bundle (ไฟล์เดียวที่มีประวัติ commit ครบ)

บนวินโดวส์:

```powershell
cd D:\ai-personal-computerV2
git bundle create aipc.bundle --all
```

คัดลอก `aipc.bundle` ไปที่ Pi (USB หรือ `scp`) แล้วบน Pi:

```bash
git clone ~/aipc.bundle ~/aipc
cd ~/aipc
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m unittest discover -s tests -t .   # ต้องผ่าน (บน Pi เทสต์สิทธิ์ไฟล์ 2 ข้อจะรันด้วย)
```

> ถ้าอยากใช้ GitHub (private repo) แทน บอกได้ — สะดวกกว่าตอนส่งผลกลับ แต่เป็นการเอาโค้ดขึ้นบริการภายนอก จึงต้องให้ Pakon ตัดสินเอง

## 2. ตรวจเครื่อง (ROADMAP 0.3, 0.4)

```bash
./.venv/bin/python -m aipc.doctor --save
sudo ./.venv/bin/python -m aipc.doctor --audit --save
```

ดูผลด้วยตา โดยเฉพาะ:

- **ไฟเลี้ยง** ถ้า "ไม่ผ่าน" = เคยไฟตก → เปลี่ยนสาย/อะแดปเตอร์ แล้วรีบูตก่อนวัดอะไรทั้งนั้น
- **ไฟเลี้ยง/นาฬิกา RTC** ถ้า "ไม่รู้" → path ที่เครื่องมือใช้อาจไม่ตรงกับเครื่องจริง บอกผมพร้อมผลของ
  `ls /proc/device-tree/chosen/power/` และ `ls /sys/class/rtc/rtc0/` จะแก้เครื่องมือให้
- ข้อที่เครื่องมือแนะนำให้แก้ไฟล์บูต (เช่น `rtc_bbat_vchg`) **ยังไม่ต้องแก้** ส่งผลมาก่อน

## 3. สร้าง llama.cpp (ROADMAP 0.7)

```bash
sudo apt install -y git cmake build-essential
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cmake -S ~/llama.cpp -B ~/llama.cpp/build
cmake --build ~/llama.cpp/build --config Release -j4
git -C ~/llama.cpp rev-parse HEAD      # จด commit นี้ไว้ ใส่ใน --meta
```

ดูหน้าตาผลจริงหนึ่งครั้งก่อน (ตรวจว่ามีฟิลด์ `n_prompt`, `n_gen`, `avg_ts`):

```bash
~/llama.cpp/build/bin/llama-bench -m <ไฟล์.gguf> -p 16 -n 8 -r 1 -o json
```

ถ้าไม่มีฟิลด์นั้น เครื่องมือจะหยุดพร้อมบอกฟิลด์ที่เจอ — ส่งผลมาให้ผมแก้ตัวแปลง

## 4. โมเดลที่จะวัด (ADR-007)

ตัวเลือกจาก BRIEF 5.4 · ใช้ไฟล์ GGUF แบบ Q4_K_M ให้เหมือนกันทุกตัว · **เปิดอ่านไลเซนส์ของแต่ละตัวบนหน้า
Hugging Face ก่อนดาวน์โหลด แล้วเพิ่มแถวในตาราง ADR-014** (ห้ามเพิ่มถ้ายังไม่ได้อ่านเอง)

| ชั้น | ตัวเลือก |
|---|---|
| 1b | Gemma 3 1B, Llama-3.2-Typhoon2-1B |
| 3-4b | Typhoon2.5-Qwen3-4B, Typhoon2.1-Gemma3-4B, Qwen3-4B |

brief ขอ 3 ตัว → เสนอ: Gemma 3 1B, Typhoon2.5-Qwen3-4B, Qwen3-4B (ตัวหลังใช้เทียบว่าการปรับจูนภาษาไทยช่วยไหม)
เก็บไฟล์ไว้ใน `~/aipc/models/` (โฟลเดอร์นี้ไม่เข้า git)

## 5. วัด

ปิดโปรแกรมอื่น ต่อพัดลม แล้วรันทีละโมเดล:

```bash
B=~/llama.cpp/build/bin/llama-bench
L=$(git -C ~/llama.cpp rev-parse --short HEAD)

./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/<ไฟล์>.gguf \
    --label <ชื่อสั้น> --size 1b --threads 4 --meta llama_cpp=$L

# ทดลอง threads 3 เทียบ 4 (BRIEF 5.4) — รันซ้ำด้วย --threads 3
# soak 10 นาที ดูว่าร้อนแล้วช้าลงไหม
./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/<ไฟล์>.gguf \
    --label <ชื่อสั้น> --size 1b --soak-minutes 10
```

**ต้อง commit ก่อนวัดทุกครั้ง** ไม่งั้นรายงานจะบอกว่า "มีไฟล์ค้างแก้" และไม่นับเป็นระดับ 4
(ไฟล์โมเดลไม่นับ เพราะ `models/` ถูก ignore)

## 5.1 Spike PostgreSQL + RLS (ADR-004) — ทำบน Pi 4 ได้

เป็นเรื่องความถูกต้อง ไม่ใช่ความเร็ว จึงรันบน Pi 4 ได้ แล้วค่อยยืนยันซ้ำบน Pi 5

```bash
sudo apt install -y postgresql
bash spikes/pg-rls/run.sh            # ดูก่อนว่าจะทำอะไร (ไม่ทำอะไรจริง)
bash spikes/pg-rls/run.sh --apply    # สร้างผู้ใช้ทดสอบ 2 คน + ฐานข้อมูลทดสอบ แล้วรัน 15 กรณี
bash spikes/pg-rls/run.sh --cleanup  # ลบของทดสอบทั้งหมด
```

ไม่แก้ pg_hba.conf (ถ้าไม่มีบรรทัด peer สคริปต์จะหยุดเอง) · ถ้าไม่อยากเก็บ PostgreSQL ไว้บนเครื่องหลังทดสอบ: `sudo apt remove postgresql`

## 5.2 เปิดหน้าจอของระบบบน Pi

```bash
sudo apt install -y libthai0 libxkbcommon0 libegl1   # libthai = ตัดคำไทยให้ถูก (BRIEF 5.7 ข้อ 4)
./.venv/bin/python -m pip install -e ".[ui]"          # PySide6-Essentials ต้องใช้ glibc >= 2.39 (Trixie มี)
./.venv/bin/python -m aipc.ui                         # หน้า Login จริง (ยังไม่มีระบบใบหน้า/รหัสผ่านจริง)
./.venv/bin/python -m aipc.ui --dev                   # เดินหน้าจอได้ครบ มีแถบเตือนโหมดพัฒนา
./.venv/bin/python -m aipc.ui --screen shell --page health   # ดูผลตรวจเครื่องบนหน้าจอ
```

ถ่ายภาพหน้าจอไว้ใส่เล่มโดยไม่ต้องมีจอ: `--screenshot docs/benchmarks/<ชื่อ>.png` (ภาพ .png ไม่เข้า git ตาม .gitignore — เก็บแยก)

สิ่งที่ต้องดูบน Pi: ข้อความไทยยาว ๆ ตัดบรรทัดตามคำไหม (ถ้าตัดกลางคำ = ไม่มี libthai) · หน้าจอลื่นไหม (ยังไม่วัด fps)

## 6. ส่งผลกลับ

```bash
git add docs/benchmarks
git commit -m "bench: <อะไรที่วัด> บน Pi 5"
git bundle create ~/results.bundle --all
```

เอา `results.bundle` กลับมาวินโดวส์ แล้ว `git pull <path>/results.bundle master`
