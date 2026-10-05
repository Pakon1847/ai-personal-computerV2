#!/bin/bash
# ทดสอบความร้อนขณะ AI ตอบต่อเนื่อง (ก่อน/หลังแก้ Active Cooler · 2026-10-05) · อ่านอย่างเดียว ไม่แตะค่าระบบ
#
#   ./scripts/pi/thermal-test.sh <ชื่อรอบ> [วินาที=300]
#
# โหลด = llama-server Gemma 4 E2B ค่าเดียวกับแอป (-t 3 -c 4096 -fa off) ตอบคำถามเดิมซ้ำ (max_tokens 512) ไม่หยุด
# บันทึกทุก 5 วิ: อุณหภูมิ · ความถี่ CPU · get_throttled · รอบพัดลม → docs/benchmarks/<วันที่>-thermal/<ชื่อรอบ>.csv
# ต้องรันค้างใน SSH (KillUserProcesses=yes: ออกจาก SSH = โปรเซสถูกปิด)
set -u
LABEL=${1:?ชื่อรอบ เช่น before}
SECS=${2:-300}
cd "$(dirname "$0")/../.."
OUT=docs/benchmarks/$(date +%F)-thermal
mkdir -p "$OUT"
CSV=$OUT/$LABEL.csv
[ -e "$CSV" ] && { echo "มี $CSV แล้ว · ตั้งชื่อรอบใหม่"; exit 1; }
PORT=8093
fan() { cat /sys/class/hwmon/hwmon*/fan1_input 2>/dev/null | head -1; }
sample() { echo "$(date +%s),$1,$(vcgencmd measure_temp | tr -dc '0-9.'),$(( $(vcgencmd measure_clock arm | cut -d= -f2) / 1000000 )),$(vcgencmd get_throttled | cut -d= -f2),$(fan)"; }

echo "t,phase,temp_c,arm_mhz,throttled,fan_rpm" > "$CSV"
sample idle >> "$CSV"
/opt/aipc-llm/bin/llama-server -m /opt/aipc-models/gemma-4-E2B-it-Q4_K_M.gguf --host 127.0.0.1 --port $PORT \
  -c 4096 -np 1 -t 3 -fa off -cram 512 --no-webui > /tmp/thermal-server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
BODY='{"messages":[{"role":"user","content":"อธิบายประวัติศาสตร์ของอาณาจักรสุโขทัยอย่างละเอียด"}],"max_tokens":512,"temperature":0.6,"chat_template_kwargs":{"enable_thinking":false}}'
( while true; do curl -s -o /dev/null -H 'Content-Type: application/json' -d "$BODY" http://127.0.0.1:$PORT/v1/chat/completions; done ) &
LOAD=$!
trap 'kill $LOAD $SRV 2>/dev/null' EXIT
END=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt "$END" ]; do sample load >> "$CSV"; sleep 5; done
kill $LOAD; kill $SRV; wait 2>/dev/null
for i in 1 2 3 4 5 6; do sleep 10; sample cool >> "$CSV"; done

awk -F, 'NR>1 && $2=="idle"{print "เริ่ม (ว่าง): " $3 " °C · throttled " $5}
  NR>1 && $2=="load"{n++; if($3>mx)mx=$3; all[n]=$3; mhz[n]=$4; if($5!~/0x0$/ && $5!="0x0") th++; if(!(f>0)||$6>f)f=$6}
  NR>1 && $2=="cool"{c=$3}
  END{s=0;m=0;k=0; for(i=n-11;i<=n;i++) if(i>0){s+=all[i];m+=mhz[i];k++}
      printf "โหลด %d ตัวอย่าง: สูงสุด %.1f °C · เฉลี่ย 1 นาทีสุดท้าย %.1f °C · ความถี่เฉลี่ย 1 นาทีสุดท้าย %.0f MHz · ตัวอย่างที่ throttled ไม่ใช่ 0 = %d · พัดลมสูงสุด %s rpm\n", n, mx, s/k, m/k, th, f
      print "หลังหยุด 60 วิ: " c " °C"}' "$CSV"
echo "ไฟล์: $CSV"
