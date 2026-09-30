#!/bin/sh
# T11 ใช้นาน (ขอบเขตรอบ 3 หัวข้อ 9): soak 12 ชม. · แชททุก 5 นาที + สแกนหน้าทุก 15 นาที
# ผ่านเมื่อ (ประกาศก่อนรัน): ไม่ล่ม (บริการไม่ restart · แชทตอบได้ทุกครั้งที่ไม่ใช่ช่วงเครื่องยุ่ง ≥ 95%)
#   · RAM ไม่โตต่อเนื่อง (RSS ของ llama-server / visiond ชั่วโมงสุดท้าย ≤ ชั่วโมงแรก + 10%) · ไม่ throttle (บิต "ตอนนี้" ของ get_throttled = 0 ทุกครั้งที่วัด)
# รันด้วย sudo: systemd-run --unit=aipc-soak sh soak.sh <ชั่วโมง> <โฟลเดอร์ผล>
# แชท: บัญชีทดสอบ t12a (เปิด linger ชั่วคราว · ปิดคืนตอนจบ) ผ่าน socket ของ AI ตัวจริง (aipc-llm-start)
# สแกนหน้า: ขอ identify จาก visiond ในนาม _greetd (เหมือนหน้า Login) · ไม่มีคนอยู่หน้ากล้อง = ได้ unknown/no-face ก็นับว่าทำงาน
set -u
HOURS=${1:-12}
OUT=${2:-/var/tmp/aipc-soak}
U=t12a
UID_=$(id -u $U)
PY=/opt/aipc-v2/.venv/bin/python
mkdir -p "$OUT"
LOG="$OUT/metrics.csv"
EV="$OUT/events.log"
loginctl enable-linger $U
for i in $(seq 1 30); do systemctl is-active -q user@$UID_.service && break; sleep 1; done
systemctl --user -M $U@ start aipc-llm.service
echo "time,mem_avail_mb,swap_used_mb,temp_c,throttled,llama_rss_mb,visiond_rss_mb,ui_rss_mb,llm_restarts,visiond_restarts" > "$LOG"
rss() { ps -C "$1" -o rss= 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}'; }
rss_pat() { pgrep -f "$1" | xargs -r ps -o rss= -p 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}'; }
END=$(( $(date +%s) + HOURS * 3600 ))
N=0
echo "$(date -Is) start hours=$HOURS" >> "$EV"
while [ "$(date +%s)" -lt "$END" ]; do
  M=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)
  SW=$(free -m | awk '/Swap/ {print $3}')
  T=$(vcgencmd measure_temp | sed 's/[^0-9.]//g')
  TH=$(vcgencmd get_throttled | cut -d= -f2)
  LR=$(systemctl --user -M $U@ show -p NRestarts --value aipc-llm.service 2>/dev/null)
  VR=$(systemctl show -p NRestarts --value aipc-visiond.service)
  echo "$(date +%H:%M),$M,$SW,$T,$TH,$(rss llama-server),$(rss_pat 'aipc.vision.daemon'),$(rss_pat 'aipc.ui'),$LR,$VR" >> "$LOG"
  if [ $((N % 5)) -eq 0 ]; then
    R=$(sudo -u $U XDG_RUNTIME_DIR=/run/user/$UID_ PYTHONPATH=/opt/aipc-v2/src timeout 300 $PY /tmp/soak_chat.py 2>&1 | tail -1)
    echo "$(date -Is) chat $R" >> "$EV"
  fi
  if [ $((N % 15)) -eq 0 ]; then
    R=$(sudo -u _greetd PYTHONPATH=/opt/aipc-v2/src timeout 60 $PY -c 'from aipc.vision import client; r = client.request({"op": "identify", "timeout_s": 5}); print(r.get("state"), r.get("ok"))' 2>&1 | tail -1)
    echo "$(date -Is) scan $R" >> "$EV"
  fi
  N=$((N + 1))
  sleep 60
done
systemctl --user -M $U@ stop aipc-llm.service
loginctl disable-linger $U
systemctl stop user@$UID_.service
echo "$(date -Is) done linger=$(loginctl show-user $U -p Linger 2>&1 | head -1)" >> "$EV"
