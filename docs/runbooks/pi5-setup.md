# Runbook: ตั้ง Pi 5 วันแรก + วัด LLM (ROADMAP 0.2–0.4, 0.7, 0.8)

Pakon ทำเองบน Pi 5 · **ไม่แตะหน้า Login, greetd, ไฟล์บูต, พาร์ทิชัน หรือ /etc/fstab** · สิ่งที่ทำมีแค่ติดตั้งแพ็กเกจ,
สร้างไฟล์ใน home, อ่านค่าเครื่อง และวัดผล · การเปลี่ยนหน้า Login ของ Pi 5 เป็นของ V2 ทำในขั้น 9
(บั๊กหน้า Login ที่พบ 2026-09-28 และแป้นไทยที่หน้า Login ที่พบ 2026-09-29 แก้ในโค้ดแล้ว)

ทุกขั้นบอก: ทำที่เครื่องไหน · คำสั่ง · ผลที่ควรเห็น · ถ้าไม่เห็นให้ทำอะไร

## 0. ก่อนเริ่ม (ที่ตัวเครื่อง)

- ต่อ **อะแดปเตอร์ 27W** และ **Active Cooler** · ปิดโปรแกรมอื่นที่ไม่เกี่ยว
- ตรวจ OS บน Pi 5:

```bash
grep PRETTY /etc/os-release   # ควรเห็น: Debian GNU/Linux 13 (trixie)
uname -m                      # ควรเห็น: aarch64
ldd --version | head -1       # ต้องเป็น 2.39 ขึ้นไป (PySide6 จาก pip ต้องใช้)
```

ไม่ใช่ trixie 64-bit → **หยุด** แล้วส่งผลสามบรรทัดนี้มา

## 1. เอา repo ขึ้น Pi 5

บนวินโดวส์ (สร้าง bundle ใหม่ทุกครั้ง — ไฟล์เก่าในโฟลเดอร์เป็นของ 24 ก.ย.):

```powershell
cd D:\ai-personal-computerV2
git bundle create aipc.bundle --all
```

คัดลอก `aipc.bundle` ไป home ของ Pi 5 (USB หรือ `scp`) แล้วบน Pi 5:

```bash
git clone ~/aipc.bundle ~/aipc
cd ~/aipc
git log --oneline -1          # commit ต้องตรงกับบนวินโดวส์
```

## 2. ติดตั้งแบบล็อกเวอร์ชัน

```bash
sudo apt install -y libthai0 libxkbcommon0 libegl1
cd ~/aipc
python3 -m venv .venv
./.venv/bin/pip install -c constraints.txt -e ".[dev,ui,vision]"
./.venv/bin/python -m aipc.vision.models fetch
./.venv/bin/python -m unittest discover -s tests -t .
./.venv/bin/pip freeze > ~/pi5-freeze.txt
```

- `-c constraints.txt` = ใช้ไลบรารีรุ่นเดียวกับที่วัดผลไว้ (OpenCV 5.0.0, PySide6 6.11.2) ไม่ใช่รุ่นล่าสุด
- **ผลที่ควรเห็น:** เทสต์ขึ้น `OK` · จด **จำนวนที่ข้าม (skipped)** ไว้ (บน Pi 4 เคยเป็น 0)
- pip บอกหาเวอร์ชันไม่เจอ หรือเทสต์ไม่ผ่าน → หยุด ส่งข้อความ error มา
- `~/pi5-freeze.txt` ส่งกลับมาด้วย (ใช้ยืนยันว่าเวอร์ชันตรง)

## 3. ตรวจเครื่อง (อ่านอย่างเดียว)

```bash
cd ~/aipc
./.venv/bin/python -m aipc.doctor --save
sudo ./.venv/bin/python -m aipc.doctor --audit --save
git add docs/benchmarks && git commit -m "bench(pi5): doctor + audit ครั้งแรก"
```

- ข้อ **ไฟเลี้ยง** เป็น "ไม่ผ่าน" → หยุด ห้ามวัดต่อ · เปลี่ยนสาย/อะแดปเตอร์ แล้วรีบูต
- ข้อที่เครื่องมือแนะนำให้แก้ไฟล์บูต (เช่น `rtc_bbat_vchg`) **ยังไม่ต้องแก้** ส่งผลมาก่อน

ตรวจ autologin (อ่านอย่างเดียว · **ยังไม่ต้องลบอะไร** ส่งผลมา):

```bash
ls /etc/systemd/system/getty@tty1.service.d/ 2>/dev/null
grep -rn autologin /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.d/ 2>/dev/null
```

มีผลออกมา = เครื่องนี้เข้าเองโดยไม่ถามรหัส → ต้องปิดก่อนติดตั้งหน้า Login ของ V2 (ผมจะเพิ่มขั้นนี้ในสคริปต์ติดตั้ง)

**ต้อง commit หลังทุกขั้นที่สร้างผลใหม่** ไม่งั้นการวัดครั้งถัดไปจะถูกนับว่า "มีไฟล์ค้างแก้" และไม่นับเป็นระดับ 4

## 4. กล้อง ใบหน้า และหน้าจอ (ROADMAP 0.8)

```bash
cd ~/aipc
./.venv/bin/python -m aipc.vision.camera test --seconds 5
```

ควรเห็น: `1280×720 · MJPG` และภาพ/วิ ≥ 15 · ส่งข้อความที่พิมพ์ออกมาทั้งหมด (คำสั่งนี้ไม่เขียนไฟล์)

เวลาเปิดหน้าจอ V2 (เทียบกับที่วัดบน Pi 4):

```bash
./.venv/bin/python -m aipc.bench run --topic ui-start-shell --runs 10 \
    --meta screen=shell --meta mode=session-offscreen-software --meta note=includes-600ms-screenshot-delay \
    -- ./.venv/bin/python -m aipc.ui --session --software --screenshot /tmp/ui-start.png
git add docs/benchmarks && git commit -m "bench(pi5): เวลาเปิดหน้าจอ V2"
```

เวลา/RAM ของระบบใบหน้า (ทำเมื่อคัดลอก `lfw.tgz` จาก `D:\aipc-datasets` มาแล้ว · **ภาพ LFW ห้ามเข้า git**):

```bash
mkdir -p ~/datasets && tar -xzf ~/lfw.tgz -C ~/datasets
D=docs/benchmarks/$(date +%F)-face-pi5 && mkdir -p $D
./.venv/bin/python -m aipc.vision.bench ~/datasets/lfw --limit 200 --rounds 5 --out $D/bench.json
git add docs/benchmarks && git commit -m "bench(pi5): เวลาและ RAM ของระบบใบหน้า"
```

## 5. สร้าง llama.cpp บน Pi 5 (ROADMAP 0.7)

build บนเครื่องเองเท่านั้น (binary สำเร็จรูปช้ากว่าหลายเท่า — ข้อเสนอรอบ 3 หัวข้อ 7.1) · ใช้เวลาราว 15–30 นาที

```bash
sudo apt install -y git cmake build-essential libcurl4-openssl-dev
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cmake -S ~/llama.cpp -B ~/llama.cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build ~/llama.cpp/build --config Release -j4
git -C ~/llama.cpp rev-parse --short HEAD     # จด commit นี้ · ใช้ commit เดียวกันตลอดการวัด
~/llama.cpp/build/bin/llama-server --help | grep -n "\.sock"   # ต้องเห็นว่ารองรับ UNIX socket (ADR-008)
```

build ไม่ผ่าน → ส่งข้อความ error 30 บรรทัดสุดท้ายมา · บรรทัดสุดท้ายไม่มีคำว่า `.sock` → บอกผม (ต้องเปลี่ยนแผน ADR-008)

## 6. โหลดโมเดล 3 ตัว + ตรวจ sha256

**อ่านไลเซนส์ของแต่ละตัวบนหน้า Hugging Face ก่อนโหลด** (ADR-014 — ทั้ง 3 ตัวแจ้งว่า Apache-2.0) แล้วบอกผมให้เพิ่มแถวในตาราง ADR-014:
[Typhoon2.5-Qwen3-4B](https://huggingface.co/typhoon-ai/typhoon2.5-qwen3-4b) ·
[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) ·
[Gemma 4 E2B-it](https://huggingface.co/google/gemma-4-E2B-it)

ใช้พื้นที่รวมราว 8.1 GB · โฟลเดอร์ `models/` ไม่เข้า git · ฟังก์ชันข้างล่างโหลดไฟล์แล้วเทียบ sha256 กับค่าที่ Hugging Face ประกาศ

```bash
cd ~/aipc && mkdir -p models
fetch() {  # fetch <repo> <ไฟล์>
  curl -L --fail -C - -o "models/$2" "https://huggingface.co/$1/resolve/main/$2" || return 1
  want=$(curl -sL "https://huggingface.co/api/models/$1/tree/main" | python3 -c \
    "import json,sys; print(next(f['lfs']['oid'] for f in json.load(sys.stdin) if f['path']=='$2'))")
  got=$(sha256sum "models/$2" | cut -d' ' -f1)
  if [ "$want" = "$got" ]; then echo "ตรง: $2 $got"; else echo "ไม่ตรง! $2 ต้องเป็น $want ได้ $got"; fi
}
fetch typhoon-ai/typhoon2.5-qwen3-4b-gguf typhoon2.5-qwen3-4b-q4_k_m.gguf   # ย้ายจาก scb10x/ (พบ 2026-09-29)
fetch unsloth/Qwen3-4B-Instruct-2507-GGUF Qwen3-4B-Instruct-2507-Q4_K_M.gguf
fetch unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-Q4_K_M.gguf
```

ควรเห็นคำว่า **"ตรง"** ครบ 3 บรรทัด · "ไม่ตรง" → ลบไฟล์นั้นแล้วโหลดใหม่ · ขึ้น 401/403 → บอกผม (อาจต้องกดยอมรับเงื่อนไขบนเว็บ)

## 7. วัดความเร็ว (threads 4 ก่อน)

ตามเกณฑ์ที่ประกาศไว้ใน [ADR-007](../adr/0007-default-llm.md) · รันทีละโมเดล แล้ว commit ทุกครั้ง

```bash
cd ~/aipc
B=~/llama.cpp/build/bin/llama-bench
L=$(git -C ~/llama.cpp rev-parse --short HEAD)

./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/typhoon2.5-qwen3-4b-q4_k_m.gguf \
    --label typhoon25-4b-q4km --size 3-4b --threads 4 --meta llama_cpp=$L
git add docs/benchmarks && git commit -m "bench(pi5): llm typhoon2.5-4b threads 4"

./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf \
    --label qwen3-4b-2507-q4km --size 3-4b --threads 4 --meta llama_cpp=$L
git add docs/benchmarks && git commit -m "bench(pi5): llm qwen3-4b-2507 threads 4"

./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/gemma-4-E2B-it-Q4_K_M.gguf \
    --label gemma4-e2b-q4km --size 1b --threads 4 --meta llama_cpp=$L
git add docs/benchmarks && git commit -m "bench(pi5): llm gemma4-e2b threads 4"
```

ครบ 3 ตัวแล้วรันซ้ำด้วย `--threads 3` (label เดิม + `-t3`) · แล้ว soak 10 นาทีกับตัวที่เร็วที่สุดในแต่ละชั้น:

```bash
./.venv/bin/python -m aipc.spikes.llm --bench $B --model models/<ไฟล์>.gguf \
    --label <label>-soak --size <ชั้น> --soak-minutes 10 --meta llama_cpp=$L
git add docs/benchmarks && git commit -m "bench(pi5): llm <label> soak 10 นาที"
```

เครื่องมือหยุดพร้อมบอกว่าไม่เจอฟิลด์ของ llama-bench → ส่งข้อความนั้นมา ผมจะแก้ตัวแปลง

**ความเร็วอย่างเดียวยังตัดสิน ADR-007 ไม่ได้** · ต่อด้วยขั้น 7.1

## 7.1 วัดคุณภาพภาษาไทย (ADR-007 เกณฑ์ข้อ 1)

ชุดคำถาม 30 ข้อ `tests/data/llm_thai_questions.json` commit ไว้ก่อนวัดแล้ว (2026-09-28) · รันทีละโมเดล:

```bash
cd ~/aipc
S=~/llama.cpp/build/bin/llama-server
$S -m models/typhoon2.5-qwen3-4b-q4_k_m.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4 --no-webui &
sleep 60   # รอโหลดโมเดลจาก microSD
./.venv/bin/python -m aipc.spikes.llm_quality ask --label typhoon25-4b-q4km \
    --out docs/benchmarks/$(date +%F)-llm-thai/typhoon25-4b-q4km.json
kill %1
# ทำซ้ำกับ Qwen3-4B-Instruct-2507-Q4_K_M.gguf (label qwen3-4b-2507-q4km)
# และ gemma-4-E2B-it-Q4_K_M.gguf (label gemma4-e2b-q4km)
git add docs/benchmarks && git commit -m "bench(pi5): คำตอบ LLM 3 ตัวสำหรับให้คะแนน"
```

สร้างแบบให้คะแนนที่ไม่มีชื่อโมเดล แล้วส่งกลับมาวินโดวส์:

```bash
D=docs/benchmarks/$(date +%F)-llm-thai
./.venv/bin/python -m aipc.spikes.llm_quality sheet $D/*.json --out $D/rating
```

- ให้คน 2 คน (Pakon + อีก 1 คน) เปิด `rating/rate-me.csv` คนละสำเนา (`rater1.csv`, `rater2.csv`) แล้วใส่คะแนน 1–5
  ในคอลัมน์ score ตามเกณฑ์ใน `rubric` ของไฟล์คำถาม · **ห้ามเปิด `key.json` ก่อนให้คะแนนเสร็จ**
- รวมคะแนน: `python -m aipc.spikes.llm_quality score --key $D/rating/key.json $D/rating/rater1.csv $D/rating/rater2.csv`

## 8. ส่งผลกลับ

```bash
cd ~/aipc
git bundle create ~/results-pi5.bundle --all
```

เอา `~/results-pi5.bundle` และ `~/pi5-freeze.txt` กลับมาวินโดวส์ พร้อมข้อความจากขั้น 0, 3 (autologin) และ 4 (`camera test`) แล้วบอกผม
ผมจะดึงผลเข้า repo (`git pull <path>\results-pi5.bundle master`) อัปเดต STATUS แล้วบอกว่าข้อไหนขึ้นระดับ 4

## 9. ติดตั้งหน้า Login + สมัคร + AI (หลังขั้น 1–8)

ลำดับเดียวกับที่ทดสอบผ่านบน Pi 4 แล้ว 2026-09-28 ([ผล](../benchmarks/2026-09-28-card0012-pi4/README.md),
[ผล AI](../benchmarks/2026-09-28-card0013-pi4/README.md)) · ทุกสคริปต์รันแบบไม่ใส่ `--apply` ก่อนเพื่อดูว่าจะทำอะไร ·
ตรวจทางเข้าสำรอง (Ctrl+Alt+F2 และ SSH) ก่อนขั้นแรก

```bash
cd ~/aipc
sudo ./scripts/pi/install-greeter.sh --apply --session v2   # หน้า Login ของ V2 (ถาม YES)
sudo ./scripts/pi/update-app.sh --apply                     # ย้ายเข้าโครงสร้างโฟลเดอร์ต่อรุ่น
sudo ./scripts/pi/install-accounts.sh --apply               # สมัคร/กู้คืน + ปิด autologin tty1
sudo -l -U _greetd                                          # ต้องเห็นคำสั่งเดียว
sudo ./scripts/pi/install-llm.sh --apply --model models/<โมเดลที่ชนะตาม ADR-007>.gguf --threads <3|4>
sudo reboot                                                 # ให้ KillUserProcesses มีผล
```

หลังรีบูต: สมัครบัญชีทดสอบที่หน้า Login → เข้าใช้ → ป้าย "โมเดล" ต้องเป็นสีเขียว → ถามอะไรก็ได้ → กดหยุด/Esc ได้
