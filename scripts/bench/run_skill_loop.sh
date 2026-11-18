#!/bin/sh
# การ์ด 0083 วงจรเรียนรู้สกิล บน Pi 5 · docs/benchmarks/<วันที่>-skill-loop/README.md
#   sh scripts/bench/run_skill_loop.sh <ชุดข้อมูล.txt> <โฟลเดอร์ผล> [user0] [user50]   # ค่าเริ่มต้น = ทั้งสองสภาพ
#   FAKE=1 sh scripts/bench/run_skill_loop.sh tests/data/skill_loop_dev.txt /tmp/loop-smoke user0   # Claude ปลอม · ไม่นับผล
# ใช้ Claude จริง (ไม่มี FAKE) = ต้องรันในบัญชีที่เข้าสู่ระบบ Claude Code → Pakon เป็นคนรัน
# llama-server ค่าเดียวกับแอป (อ่าน /etc/aipc/llm.conf อย่างเดียว) บน TCP 127.0.0.1:18080 ชั่วคราว
# ไม่แตะหน้า Login · service ของระบบ · /etc · /opt · ผลอยู่ในโฟลเดอร์ผล · ไม่ commit เอง
set -u
DATA="${1:?ต้องระบุไฟล์ชุดข้อมูล}"
O="${2:?ต้องระบุโฟลเดอร์ผล}"
shift 2
RUNS="${*:-user0 user50}"
POOL=tests/data/skill_guard_r2_pool90.json
cd "$(dirname "$0")/../.."
. /etc/aipc/llm.conf
PY="${PY:-/opt/aipc-v2/.venv/bin/python}"
LOG="$O/run.log"
export LD_LIBRARY_PATH=/opt/aipc-llm/lib PYTHONPATH=src PYTHONIOENCODING=utf-8 QT_QPA_PLATFORM=offscreen
mkdir -p "$O"
EXTRA=""
[ -n "${FAKE:-}" ] && EXTRA="--fake-claude"

temp() { vcgencmd measure_temp | tr -dc '0-9.'; }
cool() {  # รอ < 65°C (สูงสุด 15 นาที)
  for _ in $(seq 1 90); do
    [ "$(temp | cut -d. -f1)" -lt 65 ] && return 0
    sleep 10
  done
}
state() { echo "$(date -Iseconds) temp=$(temp) $(vcgencmd get_throttled) avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"; }

echo "== skill-loop $(date -Iseconds) commit=$(git log --oneline -1) data=$DATA sha256=$(sha256sum "$DATA" | cut -c1-16) model=$MODEL runs=$RUNS fake=${FAKE:-}" | tee -a "$LOG"
cool
echo "before-server $(state)" >> "$LOG"
if [ -n "${TEMPLATE:-}" ]; then set -- --chat-template-file "$TEMPLATE"; else set --; fi
/opt/aipc-llm/bin/llama-server -m "$MODEL" "$@" --host 127.0.0.1 --port 18080 -c "${CTX:-4096}" -np 1 \
    -t "${THREADS:-4}" -fa "${FLASH_ATTN:-off}" -cram "${CACHE_RAM:-512}" --no-webui --no-slots --swa-full \
    > "$O/server.log" 2>&1 &
PID=$!
READY=""
for _ in $(seq 1 150); do
  curl -sf http://127.0.0.1:18080/health >/dev/null 2>&1 && { READY=1; break; }
  kill -0 $PID 2>/dev/null || break
  sleep 2
done
[ -n "$READY" ] || { echo "SERVER-FAIL" | tee -a "$LOG"; kill $PID 2>/dev/null; exit 1; }

run() {  # <label> <จำนวนสกิลผู้ใช้>
  case " $RUNS " in *" $1 "*) ;; *) return 0 ;; esac
  cool
  echo "start $1 $(state)" >> "$LOG"
  $PY -m aipc.spikes.skill_loop_eval --server http://127.0.0.1:18080 --data "$DATA" \
      --user-skills "$POOL" --user-count "$2" $EXTRA --out "$O/$1.json" 2>&1 | tee -a "$LOG" \
      || echo "FAIL $1" | tee -a "$LOG"
  echo "end $1 $(state)" >> "$LOG"
}
run user0 0
run user50 50
grep -E "^(VmHWM|VmRSS)" /proc/$PID/status | tr -s ' \t' ' ' | sed 's/^/server-/' >> "$LOG"
kill $PID 2>/dev/null
wait $PID 2>/dev/null
echo "ALL-DONE $(date -Iseconds)" | tee -a "$LOG"
