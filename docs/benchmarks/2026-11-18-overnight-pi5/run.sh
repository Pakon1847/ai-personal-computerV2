#!/bin/sh
# งานข้ามคืนบน Pi 5 (การ์ด 0081 · J1 J6 J7) · รันเป็น aipc2030 ใน transient unit ของ systemd (ดู README "วิธีรัน")
# unit ตั้ง RestrictAddressFamilies=AF_UNIX + PrivateNetwork=yes เหมือน aipc-llm.service → ทั้ง AI และตัวรันต่อเน็ตไม่ได้ (J6)
# ทำ: เริ่ม llama-server ด้วยสคริปต์ของแอป → เก็บอุณหภูมิ/RAM ทุก 10 วิ → รันงาน → มีคนเข้าระบบที่จอ = หยุดงาน (ทำต่อได้)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$HOME/aipc-0081/src}"
DATA="${DATA:-$HOME/overnight-1118/docs}"
OUT="${OUT:-$HOME/overnight-1118/out}"
PY=/opt/aipc-v2/.venv/bin/python
mkdir -p "$OUT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/aipc-night-$(id -u)}"
mkdir -p "$XDG_RUNTIME_DIR" && chmod 0700 "$XDG_RUNTIME_DIR"
SOCK="$XDG_RUNTIME_DIR/aipc/llm.sock"
LOG="$OUT/run.log"
say() { echo "$(date -Is) $*" >> "$LOG"; }

say "เริ่ม · src=$SRC · data=$DATA · commit=$(git -C "$SRC/.." log --oneline -1 2>/dev/null)"
say "กันเน็ต: $(grep Seccomp: /proc/self/status | tr -s '\t ' ' ') · การ์ดเครือข่ายที่เห็น: $(awk -F: 'NR > 2 {gsub(/ /, "", $1); printf "%s ", $1}' /proc/self/net/dev)"
OUTBOUND="$HOME/.local/share/aipc/outbound.json"
say "outbound ก่อน: $(sha256sum "$OUTBOUND" 2>/dev/null || echo 'ไม่มีไฟล์')"

/opt/aipc-v2/scripts/pi/session/aipc-llm-start >> "$OUT/llama.log" 2>&1 &
LLAMA=$!
i=0
until [ -S "$SOCK" ] || [ $i -ge 120 ]; do sleep 1; i=$((i + 1)); done
say "llama pid=$LLAMA · socket หลัง ${i} วิ"

# เก็บค่าเครื่องทุก 10 วิ: เวลา · °C · throttled · RSS ของ llama (MB) · MemAvailable (MB)
(
  echo "time,temp_c,throttled,llama_rss_mb,mem_avail_mb" > "$OUT/samples.csv"
  while kill -0 $LLAMA 2>/dev/null; do
    T=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
    TH=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
    R=$(awk '/VmRSS/ {printf "%d", $2/1024}' /proc/$LLAMA/status 2>/dev/null)
    A=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)
    echo "$(date -Is),$T,$TH,$R,$A" >> "$OUT/samples.csv"
    sleep 10
  done
) &
SAMPLER=$!

PYTHONPATH="$SRC" "$PY" -m aipc.spikes.overnight_night --folder "$DATA" --out "$OUT" >> "$LOG" 2>&1 &
JOB=$!

# มีคนเข้าระบบที่จอ (seat0 ไม่ใช่ _greetd) = หยุดงาน · AI ของเขาจะได้ RAM เต็ม (memory cgroup ปิดอยู่ · MemoryMax ไม่มีผล)
while kill -0 $JOB 2>/dev/null; do
  WHO=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$4 == "seat0" && $3 != "_greetd" {print $3}' | head -1)
  if [ -n "$WHO" ]; then
    say "มีคนเข้าระบบที่จอ ($WHO) → หยุดงาน"
    kill -TERM $JOB
    break
  fi
  sleep 15
done
wait $JOB
RC=$?
say "งานจบ rc=$RC"
say "outbound หลัง: $(sha256sum "$OUTBOUND" 2>/dev/null || echo 'ไม่มีไฟล์')"
kill $LLAMA $SAMPLER 2>/dev/null
wait 2>/dev/null
say "จบ"
exit $RC
