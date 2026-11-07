#!/bin/sh
# การ์ด 0074 ขั้น 0 · S2 (เลือกสกิลเมื่อมีสกิลผู้ใช้มากขึ้น) บน Pi 5 · docs/benchmarks/2026-11-05-skill-guard/README.md
#   sh scripts/bench/run_skill_guard.sh              # ทั้ง 4 ชุด
#   sh scripts/bench/run_skill_guard.sh s2b-user50   # เฉพาะชุดที่ระบุ (ต่อท้าย log เดิม ไม่ลบ)
#   R=r2 sh scripts/bench/run_skill_guard.sh s2a-user0 s2a-user50 s2b-user50   # รอบ 2
# llama-server ค่าเดียวกับแอป (อ่าน /etc/aipc/llm.conf อย่างเดียว) บน TCP 127.0.0.1:18080 ชั่วคราว
# (แอปจริงคุยผ่าน Unix socket ในกล่องตัดเน็ต) · ai-first = ทางของแอปเมื่อ AI พร้อม · ทุกชุดถาม 3 รอบ
# ไม่แตะหน้า Login · service ของระบบ · /etc · /opt · ผลอยู่ใน O · ไม่ commit เอง
set -u
RUNS="${*:-s2a-user0 s2a-user20 s2a-user50 s2b-user50}"
# รอบ 2 (การ์ด 0074 หัวข้อ 14 ข้อ 6): R=r2 = ชุดอิสระรอบ 2 + ผลในโฟลเดอร์ 2026-11-07-skill-guard-r2
R="${R:-}"
cd "$(dirname "$0")/../.."
. /etc/aipc/llm.conf
if [ "$R" = r2 ]; then
  O=docs/benchmarks/2026-11-07-skill-guard-r2 POOL=tests/data/skill_guard_r2_pool.json
  S2A=tests/data/skill_guard_r2_s2a.json S2B=tests/data/skill_guard_r2_s2b.json
else
  O=docs/benchmarks/2026-11-05-skill-guard POOL=tests/data/skill_guard_pool.json
  S2A=tests/data/skill_guard_s2a.json S2B=tests/data/skill_guard_s2b.json
fi
PY="${PY:-$HOME/aipc-0025/.venv/bin/python}"
LOG="$O/s2.log"
export LD_LIBRARY_PATH=/opt/aipc-llm/lib PYTHONPATH=src AIPC_CLOUD=0 PYTHONIOENCODING=utf-8
mkdir -p "$O"

temp() { vcgencmd measure_temp | tr -dc '0-9.'; }
cool() {  # รอ < 65°C (สูงสุด 15 นาที)
  for _ in $(seq 1 90); do
    [ "$(temp | cut -d. -f1)" -lt 65 ] && return 0
    sleep 10
  done
}
state() { echo "$(date -Iseconds) temp=$(temp) $(vcgencmd get_throttled) avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"; }

echo "== S2 $(date -Iseconds) model=$MODEL threads=${THREADS:-4} ctx=${CTX:-4096} template=${TEMPLATE:-} runs=$RUNS" | tee -a "$LOG"
cool
echo "before-server $(state)" >> "$LOG"
if [ -n "${TEMPLATE:-}" ]; then
  set -- --chat-template-file "$TEMPLATE"
else
  set --
fi
/opt/aipc-llm/bin/llama-server -m "$MODEL" "$@" --host 127.0.0.1 --port 18080 -c "${CTX:-4096}" -np 1 \
    -t "${THREADS:-4}" -fa "${FLASH_ATTN:-off}" -cram "${CACHE_RAM:-512}" --no-webui --no-slots --swa-full \
    > "$O/s2-server.log" 2>&1 &
PID=$!
READY=""
for _ in $(seq 1 150); do
  curl -sf http://127.0.0.1:18080/health >/dev/null 2>&1 && { READY=1; break; }
  kill -0 $PID 2>/dev/null || break
  sleep 2
done
[ -n "$READY" ] || { echo "SERVER-FAIL" | tee -a "$LOG"; kill $PID 2>/dev/null; exit 1; }

run() {  # <label> <ชุดประโยค> <จำนวนสกิลผู้ใช้>
  case " $RUNS " in *" $1 "*) ;; *) return 0 ;; esac
  cool
  echo "start $1 $(state)" >> "$LOG"
  $PY -m aipc.spikes.skill_select --label "$1" --server http://127.0.0.1:18080 --mode ai-first \
      --dataset "$2" --user-skills "$POOL" --user-count "$3" --repeat 3 --out "$O/$1.json" >> "$LOG" 2>&1 \
      || echo "FAIL $1" | tee -a "$LOG"
  echo "end $1 $(state)" >> "$LOG"
}
run s2a-user0 "$S2A" 0
run s2a-user20 "$S2A" 20
run s2a-user50 "$S2A" 50
run s2b-user50 "$S2B" 50
grep -E "^(VmHWM|VmRSS)" /proc/$PID/status | tr -s ' \t' ' ' | sed 's/^/server-/' >> "$LOG"
kill $PID 2>/dev/null
wait $PID 2>/dev/null
echo "ALL-DONE $(date -Iseconds)" | tee -a "$LOG"
