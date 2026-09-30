#!/bin/sh
# T7 AI พัง + T14 อัปเดตพัง · รันด้วย sudo บน Pi หลังคิววัด AI จบ (ต้องไม่มี llama-server ตัวอื่น)
set -u
echo "===== T7 AI พัง: kill -9 llama-server ของผู้ใช้ → กลับมาเองภายใน 60 วิ"
U=t12a; UID_=$(id -u $U)
# user manager ที่ไม่มีเซสชันถูก logind ปิดใน 10 วิ (รอบแรก 16:19 AI ถูกหยุดก่อนโหลดเสร็จ) → เปิด linger ชั่วคราว
loginctl enable-linger $U
for i in $(seq 1 30); do systemctl is-active -q user@$UID_.service && break; sleep 1; done
systemctl --user -M $U@ start aipc-llm.service
SOCK=/run/user/$UID_/aipc/llm.sock
for i in $(seq 1 300); do curl -sf --unix-socket $SOCK http://x/health >/dev/null 2>&1 && break; sleep 1; done
echo "เริ่มครั้งแรกพร้อมใน ${i} วิ"
P=$(pgrep -u $U -f llama-server)
echo "llama-server pid=$P → kill -9"
kill -9 $P
t0=$(date +%s)
for i in $(seq 1 120); do
  N=$(pgrep -u $U -f llama-server)
  if [ -n "$N" ] && [ "$N" != "$P" ] && curl -sf --unix-socket $SOCK http://x/health >/dev/null 2>&1; then break; fi
  sleep 1
done
t1=$(date +%s)
echo "กลับมาตอบได้ใน $((t1 - t0)) วิ (pid ใหม่ $N) · เกณฑ์ ≤ 60 วิ"
systemctl --user -M $U@ stop aipc-llm.service
loginctl disable-linger $U
systemctl stop user@$UID_.service

echo "===== T14 อัปเดตพัง: รุ่นที่หน้า Login เปิดไม่ขึ้น → ต้องไม่สลับ"
BEFORE=$(readlink /opt/aipc-v2)
rm -rf /tmp/t14 && git -c safe.directory='*' clone -q /home/aipc2030/aipc /tmp/t14
cd /tmp/t14
printf '#!/bin/sh\nexit 1 (\n' > scripts/pi/session/aipc-greeter    # sh -n ไม่ผ่าน = ตัวเปิดหน้า Login พัง
git -c user.name=t14 -c user.email=t14@local commit -qam "T14: ตัวเปิดหน้า Login พังโดยตั้งใจ"
./scripts/pi/update-app.sh --apply 2>&1 | tail -4
AFTER=$(readlink /opt/aipc-v2)
echo "ก่อน: $BEFORE · หลัง: $AFTER"
[ "$BEFORE" = "$AFTER" ] && echo "T14 PASS: ไม่สลับรุ่น" || echo "T14 FAIL: สลับไปรุ่นที่พัง"
ls /opt/aipc-releases/ | grep -c building && echo "!! มีโฟลเดอร์สร้างค้าง" || echo "ไม่มีของค้าง"
rm -rf /tmp/t14
