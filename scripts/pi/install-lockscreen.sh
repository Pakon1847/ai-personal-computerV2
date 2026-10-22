#!/usr/bin/env bash
# จอล็อกรุ่น 2: ปลดด้วยใบหน้า (การ์ด 0055) · ใช้หลัง install-visiond.sh และติดตั้ง gtklock แล้ว
#
#   ./scripts/pi/install-lockscreen.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-lockscreen.sh --apply     ทำจริง
#   sudo ./scripts/pi/install-lockscreen.sh --rollback  คืน /etc/pam.d/gtklock เดิม และลบตัวตรวจใบหน้า
#
# ทำอะไร:
#   1. /usr/local/sbin/aipc-face-unlock (root 0755) = เรียก python -I -m aipc.vision.face_unlock จาก /opt/aipc-v2
#      (PAM รันเป็นผู้ใช้เจ้าของจอล็อก ไม่ใช่ root · ตัวนี้แค่ถาม visiond ว่าหน้าตรงเจ้าของไหม)
#   2. /etc/pam.d/gtklock: ลองใบหน้าก่อน (ช่องรหัสว่าง) → ไม่ผ่าน/พิมพ์รหัสมา = รหัสผ่านตามเดิม (auth include login)
#      เก็บไฟล์เดิมไว้ที่ /var/lib/aipc/gtklock.pam.orig ก่อนเขียน
# ไม่แตะ: PAM ของ login / greetd / swaylock · ไฟล์แม่แบบใบหน้า · ไม่รีบูต
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

DEST=/opt/aipc-v2
WRAPPER=/usr/local/sbin/aipc-face-unlock
PAMFILE=/etc/pam.d/gtklock
BACKUP=/var/lib/aipc/gtklock.pam.orig

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

WRAPPER_TEXT='#!/bin/sh
# ปลดจอล็อกด้วยใบหน้า (การ์ด 0055) · PAM ของ gtklock เรียก · รหัสที่พิมพ์มาทาง stdin
# -I = ไม่อ่าน PYTHONPATH และ site ของผู้ใช้ → โหลดโค้ดจาก /opt/aipc-v2 ที่ root เป็นเจ้าของเท่านั้น
exec /opt/aipc-v2/.venv/bin/python -I -m aipc.vision.face_unlock'
PAM_TEXT='# จอล็อก gtklock ของ AI PC (การ์ด 0055 · install-lockscreen.sh)
# ช่องรหัสว่าง → ลองปลดด้วยใบหน้า (visiond · เจ้าของบัญชีเท่านั้น · มีตรวจรูปปลอม)
# พิมพ์รหัสมา หรือใบหน้าไม่ผ่าน → ตรวจรหัสผ่านตามเดิม
auth [success=done default=ignore] pam_exec.so quiet expose_authtok /usr/local/sbin/aipc-face-unlock
auth include login'

if [ "$MODE" = "rollback" ]; then
  need_root
  if [ -f "$BACKUP" ]; then
    install -o root -g root -m 0644 "$BACKUP" "$PAMFILE" && say "+ คืน $PAMFILE จาก $BACKUP"
  else
    printf '%s\n' "auth include login" > "$PAMFILE" && say "+ ไม่มีไฟล์สำรอง · เขียน $PAMFILE ค่าเดิมของแพ็กเกจ (auth include login)"
  fi
  rm -f "$WRAPPER" && say "+ ลบ $WRAPPER"
  say "เสร็จ · จอล็อกปลดได้ด้วยรหัสผ่านอย่างเดียว"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
command -v gtklock >/dev/null || { say "หยุด: ยังไม่ได้ติดตั้ง gtklock (apt install gtklock gtklock-playerctl-module playerctl)"; exit 1; }
[ -x "$DEST/.venv/bin/python" ] || { say "หยุด: ไม่มี $DEST/.venv · รัน install-greeter.sh ก่อน"; exit 1; }
"$DEST/.venv/bin/python" -I -c "import aipc.vision.face_unlock" \
  || { say "หยุด: แอปใน $DEST ยังไม่มีตัวปลดด้วยใบหน้า (อัปเดตแอปก่อน)"; exit 1; }
[ -S /run/aipc-vision/visiond.sock ] || say "เตือน: visiond ไม่ทำงาน · จอล็อกจะใช้รหัสผ่านอย่างเดียวจนกว่า visiond จะพร้อม"

install_text() {  # install_text <ไฟล์ปลายทาง> <โหมด> <เนื้อหา>
  if [ "$MODE" != "apply" ]; then say "[จะเขียน] $1 ($2)"; printf '%s\n' "$3" | sed 's/^/   /'; return; fi
  install -d -m 0755 "$(dirname "$1")"
  local tmp; tmp="$(mktemp)"
  printf '%s\n' "$3" > "$tmp"
  install -o root -g root -m "$2" "$tmp" "$1"
  rm -f "$tmp"
  say "+ เขียน $1"
}

say ""; say "1) ตัวตรวจใบหน้า $WRAPPER"
install_text "$WRAPPER" 0755 "$WRAPPER_TEXT"

say ""; say "2) PAM $PAMFILE (เดิม: $(tr '\n' ' ' < "$PAMFILE" 2>/dev/null || echo ไม่มี))"
if [ "$MODE" = "apply" ] && [ ! -f "$BACKUP" ] && [ -f "$PAMFILE" ]; then
  install -d -o root -g root -m 0700 "$(dirname "$BACKUP")"
  cp -p "$PAMFILE" "$BACKUP" && say "+ สำรอง $PAMFILE → $BACKUP"
fi
install_text "$PAMFILE" 0644 "$PAM_TEXT"

say ""
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ลองที่จอ: ล็อก → มองกล้อง → กด Enter ช่องว่าง · ย้อน: sudo $0 --rollback"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-lockscreen.sh --apply"
fi
