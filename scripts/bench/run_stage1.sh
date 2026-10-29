#!/bin/sh
# เทียบ LLM ขั้น 1 (ทุกโมเดล) บน Pi 5 · 2026-10-29 · docs/benchmarks/2026-10-29-llm-compare/README.md
#   ./scripts/bench/run_stage1.sh <label> [<label> ...]
# ต่อโมเดล: รอ < 65°C → llama-bench (pp200 / tg64 · 3 thread · 5 รอบ) → llama-server ค่าเดียวกับแอป
# (TCP 127.0.0.1:18080 ชั่วคราว) → เวลาเริ่มตอบ 9 ข้อจากชุดพัฒนา (A01–A09) → RAM สูงสุดของ llama-server → ปิด
# ชุดทดสอบอิสระไม่รันบน Pi (รันบนโน้ตบุ๊ก · README หัวข้อ "แก้ก่อนรัน")
# ไม่แตะหน้า Login · service ของระบบ · /etc · /opt (อ่านอย่างเดียว) · ผลอยู่ใน OUT · ไม่ commit เอง
set -u
cd "$(dirname "$0")/../.."
MODELS="$HOME/bench-models"
USB=/mnt/bench-usb/bench-models   # microSD ที่ว่างไม่พอ (19 GB < 24 GB) · อ่านจากแฟลชไดรฟ์ (ro) · ตรวจ sha256 แล้วบนโน้ตบุ๊ก
OUT="docs/benchmarks/2026-10-29-llm-compare/raw"
PY="${PY:-$HOME/aipc-0025/.venv/bin/python}"
BENCH="$HOME/llama.cpp/build/bin/llama-bench"
SERVER=/opt/aipc-llm/bin/llama-server   # ตัวเดียวกับแอป
export LD_LIBRARY_PATH=/opt/aipc-llm/lib PYTHONPATH=src
mkdir -p "$OUT"

file_of() {  # label → ชื่อไฟล์ใน models.json
  python3 -c "import json,sys;print(next(r['file'] for r in json.load(open('$MODELS/models.json')) if r['label']==sys.argv[1]))" "$1"
}
temp() { vcgencmd measure_temp | tr -dc '0-9.'; }
cool() {  # รอ < 65°C (สูงสุด 15 นาที)
  for _ in $(seq 1 90); do
    [ "$(temp | cut -d. -f1)" -lt 65 ] && return 0
    sleep 10
  done
}
state() { echo "$(date -Iseconds) temp=$(temp) $(vcgencmd get_throttled) avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"; }

for LABEL in "$@"; do
  F="$(file_of "$LABEL")"
  M="$MODELS/$F"
  [ -f "$M" ] || M="$USB/$F"
  [ -f "$M" ] || M="/opt/aipc-models/$F"
  [ -f "$M" ] || { echo "SKIP $LABEL: ไม่มีไฟล์ $F"; continue; }
  LOG="$OUT/$LABEL.log"
  echo "== $LABEL ($F) $(date +%T)" | tee "$LOG"
  cool
  echo "before-bench $(state)" >> "$LOG"
  $PY -m aipc.spikes.llm --bench "$BENCH" --model "$M" --label "$LABEL" --size 3-4b --threads 3 \
      --prompt 200 --gen 64 --runs 5 --meta "llama_cpp=$(git -C "$HOME/llama.cpp" rev-parse --short HEAD)" \
      --out "$OUT" >> "$LOG" 2>&1 || echo "BENCH-FAIL $LABEL" | tee -a "$LOG"
  echo "after-bench $(state)" >> "$LOG"
  cool
  echo "before-server $(state)" >> "$LOG"
  T0=$(date +%s)
  "$SERVER" -m "$M" --host 127.0.0.1 --port 18080 -c 4096 -np 1 -t 3 -fa off -cram 512 \
      --no-webui --no-slots --swa-full > "$OUT/$LABEL-server.log" 2>&1 &
  PID=$!
  READY=""
  for _ in $(seq 1 150); do
    curl -sf http://127.0.0.1:18080/health >/dev/null 2>&1 && { READY=1; break; }
    kill -0 $PID 2>/dev/null || break
    sleep 2
  done
  if [ -z "$READY" ]; then
    echo "SERVER-FAIL $LABEL (ดู $LABEL-server.log)" | tee -a "$LOG"
    kill $PID 2>/dev/null; wait $PID 2>/dev/null
    continue
  fi
  echo "server-ready-s $(( $(date +%s) - T0 ))" >> "$LOG"
  $PY -m aipc.spikes.exam --label "$LABEL" --model-name "" --server http://127.0.0.1:18080 \
      --only A0 --out "$OUT/$LABEL-ttft-dev.json" >> "$LOG" 2>&1 \
      || echo "EXAM-FAIL $LABEL" | tee -a "$LOG"
  grep -E "^(VmHWM|VmRSS)" /proc/$PID/status | tr -s ' \t' ' ' | sed 's/^/server-/' >> "$LOG"
  echo "after-exam $(state)" >> "$LOG"
  kill $PID 2>/dev/null; wait $PID 2>/dev/null
  echo "DONE $LABEL $(date +%T)" | tee -a "$LOG"
done
echo "ALL-DONE $(date +%T)"
