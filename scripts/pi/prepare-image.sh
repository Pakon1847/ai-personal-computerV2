#!/usr/bin/env bash
# ล้างข้อมูลผู้ใช้ก่อนอ่านการ์ดเป็น image สำหรับแจก (การ์ด 0077 หัวข้อ 3 ข้อ 3 · เกณฑ์ I2)
#
#   sudo ./scripts/pi/prepare-image.sh                         ตรวจอย่างเดียว: บอกว่ามีข้อมูลผู้ใช้อะไรเหลือ (ไม่ลบอะไร)
#   sudo ./scripts/pi/prepare-image.sh --apply --yes-wipe-users  ลบบัญชีผู้ใช้ทั้งหมด + ข้อมูลส่วนตัว แล้วตรวจซ้ำ
#   ./scripts/pi/prepare-image.sh --root /mnt/sd               ทำกับการ์ดที่ต่อเข้ามา (ไม่ใช่เครื่องที่ใช้อยู่)
#
# อันตราย: --apply ลบทุกบัญชีที่ uid 1000–59999 พร้อม home · ใช้กับการ์ดที่จะทำ image เท่านั้น ห้ามใช้กับเครื่องที่ใช้งาน
# ผลตรวจ: ไม่เหลือ = exit 0 · ยังเหลือ = exit 1 (ใช้เป็นหลักฐาน I2) · ใช้ผิดวิธี = exit 2
# รายการที่ลบตรงกับที่ตัวลบบัญชีลบ (src/aipc/accounts/helper.py) + ของที่ระบบปฏิบัติการจำไว้ (Wi-Fi · SSH · log · machine-id)
set -u

ROOT="/"
APPLY=0
SURE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --yes-wipe-users) SURE=1; shift ;;
    *) echo "ไม่รู้จักตัวเลือก: $1" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT%/}"

if [ "$APPLY" = 1 ] && [ "$SURE" != 1 ]; then
  echo "ต้องใส่ --yes-wipe-users คู่กับ --apply (ยืนยันว่าจะลบทุกบัญชีผู้ใช้ในการ์ดนี้)"
  exit 2
fi
if [ "$APPLY" = 1 ] && [ "$(id -u)" != 0 ]; then
  echo "ต้องรันด้วย sudo (ลบบัญชีและไฟล์ของ root)" >&2
  exit 2
fi

# บัญชีผู้ใช้จริง = uid 1000–59999 (บัญชีระบบ เช่น _greetd และ nobody 65534 ไม่ใช่)
users() {
  awk -F: '$3 >= 1000 && $3 < 60000 { print $1 }' "$ROOT/etc/passwd" 2>/dev/null
}

# ข้อมูลส่วนตัวที่ต้องไม่อยู่ใน image (เนื้อหาในโฟลเดอร์ ไม่ใช่ตัวโฟลเดอร์ระบบ)
PRIVATE_GLOBS=(
  "home/*"
  "root/.bash_history" "root/.ssh/authorized_keys" "root/.claude" "root/.config/claude"
  "var/lib/aipc/recovery/*" "var/lib/aipc/password-checks/*" "var/lib/aipc/greeter-user.json"
  "var/lib/aipc-vision/face-login/*"
  "var/spool/cron/crontabs/*" "var/mail/*" "var/spool/mail/*" "var/lib/systemd/linger/*"
  "etc/NetworkManager/system-connections/*" "etc/wpa_supplicant/wpa_supplicant.conf"
  "etc/ssh/ssh_host_*"
  "var/log/journal/*"
)

found() {  # พิมพ์สิ่งที่ยังเหลือทีละบรรทัด
  local u g p
  for u in $(users); do echo "บัญชี: $u"; done
  shopt -s nullglob dotglob
  for g in "${PRIVATE_GLOBS[@]}"; do
    for p in "$ROOT"/$g; do
      # ชื่อที่ไม่มี * bash คืนชื่อเดิมแม้ไม่มีไฟล์ (nullglob ไม่ช่วย) → ตรวจว่ามีจริง
      if [ -e "$p" ] || [ -L "$p" ]; then echo "ไฟล์: ${p#"$ROOT"/}"; fi
    done
  done
  shopt -u nullglob dotglob
  if [ -s "$ROOT/etc/machine-id" ]; then echo "ไฟล์: etc/machine-id (ต้องว่าง ให้เครื่องที่แฟลชสร้างใหม่)"; fi
}

if [ "$APPLY" = 1 ]; then
  for u in $(users); do
    echo "ลบบัญชี $u"
    userdel --root "$ROOT" -r "$u" 2>/dev/null || userdel --root "$ROOT" "$u"
  done
  shopt -s nullglob dotglob
  for g in "${PRIVATE_GLOBS[@]}"; do
    for p in "$ROOT"/$g; do rm -rf -- "$p"; done
  done
  shopt -u nullglob dotglob
  if [ -f "$ROOT/etc/machine-id" ]; then : > "$ROOT/etc/machine-id"; fi
  echo "ลบแล้ว · ตรวจซ้ำ"
  echo "หมายเหตุ: ลบกุญแจ SSH ของเครื่องแล้ว · ถ้าจะเปิด SSH บนเครื่องที่แฟลช ต้องรัน sudo ssh-keygen -A ก่อน"
fi

LEFT="$(found)"
if [ -n "$LEFT" ]; then
  echo "ยังมีข้อมูลผู้ใช้ $(printf '%s\n' "$LEFT" | wc -l | tr -d ' ') รายการ (ไม่ผ่าน I2):"
  printf '%s\n' "$LEFT"
  [ "$APPLY" = 1 ] || echo "ถ้าเป็นการ์ดที่จะทำ image: เติม --apply --yes-wipe-users"
  exit 1
fi
echo "ไม่มีข้อมูลผู้ใช้เหลือ (ผ่าน I2) · ราก: ${ROOT:-/}"
exit 0
