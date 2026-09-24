#!/usr/bin/env bash
# บันทึกสถานะหน้าจอ V2 ทุก 0.5 วิ ระหว่างทดสอบกับคนจริง (ใช้ในการ์ด 0006, 0010) · อ่านอย่างเดียว ไม่แก้อะไร
#
#   ./scripts/pi/sample-session.sh <ไฟล์ผล.tsv> [นาที]      (ค่าเริ่มต้น 120 นาที แล้วหยุดเอง)
#   รันค้างไว้เบื้องหลังผ่าน SSH:  setsid ./scripts/pi/sample-session.sh ~/test.tsv </dev/null >/dev/null 2>&1 &
#
# คอลัมน์: เวลา · PID ของหน้าจอ V2 (--session) · RSS (kB) · กล้องเปิดอยู่ไหม (มี fd ไปที่ /dev/video*) · มีแม่แบบใบหน้าไหม
# อ่านจาก /proc ของผู้ใช้คนเดียวกันเท่านั้น · ไม่เปิดกล้อง ไม่อ่านภาพ ไม่อ่านแม่แบบ (ดูแค่ว่าไฟล์มีไหม)
set -u
OUT="${1:?ต้องบอกไฟล์ผล เช่น ~/card0010.tsv}"
END=$(( $(date +%s) + ${2:-120} * 60 ))
TEMPLATE="${XDG_DATA_HOME:-$HOME/.local/share}/aipc/face-template.json"
printf "time\tpid\trss_kb\tcamera_open\ttemplate\n" > "$OUT"
while [ "$(date +%s)" -lt "$END" ]; do
  # จับเฉพาะโปรเซส python ของหน้าจอ (คำสั่ง SSH ที่มีข้อความเดียวกันต้องไม่ถูกนับ)
  pid=$(pgrep -u "$USER" -f "python[0-9.]* -m aipc[.]ui --session" | head -1)
  rss=-; cam=0
  if [ -n "$pid" ]; then
    rss=$(awk '/^VmRSS/{print $2}' "/proc/$pid/status" 2>/dev/null)
    ls -l "/proc/$pid/fd" 2>/dev/null | grep -q "/dev/video" && cam=1
  fi
  tpl=0; [ -f "$TEMPLATE" ] && tpl=1
  printf "%s\t%s\t%s\t%s\t%s\n" "$(date +%H:%M:%S.%N | cut -c1-12)" "${pid:--}" "$rss" "$cam" "$tpl" >> "$OUT"
  sleep 0.5
done
