#!/usr/bin/env bash
# ตัวช่วยสร้างบัญชี/กู้คืนรหัสผ่านที่หน้า Login (การ์ด 0012) + ปิด autologin ที่ tty1
# ใช้หลัง install-greeter.sh (ต้องมีแอปที่ /opt/aipc-v2 แล้ว)
#
#   ./scripts/pi/install-accounts.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-accounts.sh --apply     ทำจริง
#   sudo ./scripts/pi/install-accounts.sh --rollback  ลบตัวช่วย กฎ sudo และไฟล์ PAM · คืน autologin ถ้าเคยปิด
#
# ทำอะไร:
#   1. /usr/local/sbin/aipc-accounts (root 0755) = เรียก python -I -m aipc.accounts.helper จาก /opt/aipc-v2
#   2. /etc/pam.d/aipc-accounts = ตรวจรหัสผ่านผู้ดูแลด้วย pam_unix (ชุดเดียวกับ login ปกติ)
#   3. /etc/sudoers.d/aipc-accounts = ผู้ใช้ _greetd เรียกตัวช่วยได้คำสั่งเดียว ห้ามใส่อาร์กิวเมนต์
#      **ตรวจด้วย visudo -c ก่อนติดตั้งเสมอ** (ไฟล์ sudoers ผิด = sudo ใช้ไม่ได้ทั้งเครื่อง)
#   4. /var/lib/aipc (root 0700) = ที่เก็บ hash รหัสกู้คืน และงานสมัครค้าง
#   5. ปิด autologin ที่ tty1 (ย้ายไฟล์ไปเก็บ ไม่ลบ) · ไม่งั้นกด Ctrl+Alt+F1 = ได้ shell โดยไม่ใส่รหัส
# ไม่แตะ: greetd config, PAM ชุด login ของ OS, ไฟล์บูต, พาร์ทิชัน · ไม่รีบูต
# ทางเข้าสำรอง: SSH และ tty2 (Ctrl+Alt+F2) ใช้ได้ตามเดิม
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

DEST=/opt/aipc-v2
WRAPPER=/usr/local/sbin/aipc-accounts
PAMFILE=/etc/pam.d/aipc-accounts
SUDOERS=/etc/sudoers.d/aipc-accounts
STATE=/var/lib/aipc
AUTOLOGIN=/etc/systemd/system/getty@tty1.service.d/autologin.conf
PARKED=/var/lib/aipc/autologin.conf.parked

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

WRAPPER_TEXT='#!/bin/sh
# ตัวช่วยสร้างบัญชี/กู้คืน (การ์ด 0012) · เรียกได้จากหน้า Login ผ่าน sudo เท่านั้น · คำขอเป็น JSON ทาง stdin
# -I = ไม่อ่าน PYTHONPATH และ site ของผู้ใช้ → โหลดโค้ดจาก /opt/aipc-v2 ที่ root เป็นเจ้าของเท่านั้น
exec /opt/aipc-v2/.venv/bin/python -I -m aipc.accounts.helper'
PAM_TEXT='# ตรวจรหัสผ่านผู้ดูแลตอนอนุมัติบัญชีใหม่ (aipc การ์ด 0012)
auth    required pam_unix.so
account required pam_unix.so'
SUDOERS_TEXT='# หน้า Login ของ aipc (ผู้ใช้ _greetd) เรียกตัวช่วยสร้างบัญชีได้คำสั่งเดียว ห้ามใส่อาร์กิวเมนต์ (การ์ด 0012)
_greetd ALL=(root) NOPASSWD: /usr/local/sbin/aipc-accounts ""'

if [ "$MODE" = "rollback" ]; then
  need_root
  rm -f "$SUDOERS" && say "+ ลบ $SUDOERS"
  rm -f "$WRAPPER" "$PAMFILE" && say "+ ลบ $WRAPPER และ $PAMFILE"
  if [ -f "$PARKED" ]; then
    mkdir -p "$(dirname "$AUTOLOGIN")"
    mv "$PARKED" "$AUTOLOGIN" && systemctl daemon-reload && say "+ คืน autologin ที่ tty1"
  fi
  say "เสร็จ · $STATE ยังอยู่ (มี hash รหัสกู้คืน · ลบเองได้ถ้าไม่ใช้แล้ว) · บัญชีที่สร้างไปแล้วยังอยู่"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
[ -x "$DEST/.venv/bin/python" ] || { say "หยุด: ไม่มี $DEST/.venv · รัน install-greeter.sh ก่อน"; exit 1; }
getent passwd _greetd >/dev/null || { say "หยุด: ไม่มีผู้ใช้ _greetd (ติดตั้ง greetd ก่อน)"; exit 1; }
"$DEST/.venv/bin/python" -I -c "import aipc.accounts.helper" \
  || { say "หยุด: แอปใน $DEST ยังไม่มีตัวช่วย (อัปเดตแอปก่อน)"; exit 1; }

install_text() {  # install_text <ไฟล์ปลายทาง> <โหมด> <เนื้อหา>
  if [ "$MODE" != "apply" ]; then say "[จะเขียน] $1 ($2)"; printf '%s\n' "$3" | sed 's/^/   /'; return; fi
  local tmp; tmp="$(mktemp)"
  printf '%s\n' "$3" > "$tmp"
  install -o root -g root -m "$2" "$tmp" "$1"
  rm -f "$tmp"
  say "+ เขียน $1"
}

say ""; say "1) ตัวช่วย $WRAPPER"
install_text "$WRAPPER" 0755 "$WRAPPER_TEXT"
say ""; say "2) PAM $PAMFILE"
install_text "$PAMFILE" 0644 "$PAM_TEXT"

say ""; say "3) กฎ sudo $SUDOERS (ตรวจด้วย visudo ก่อน)"
if [ "$MODE" = "apply" ]; then
  TMP="$(mktemp)"
  printf '%s\n' "$SUDOERS_TEXT" > "$TMP"
  if ! visudo -cf "$TMP" >/dev/null; then
    rm -f "$TMP"; say "หยุด: กฎ sudo ไม่ผ่าน visudo · ไม่ได้ติดตั้ง (sudo ของเครื่องยังเหมือนเดิม)"; exit 1
  fi
  install -o root -g root -m 0440 "$TMP" "$SUDOERS"
  rm -f "$TMP"
  visudo -c >/dev/null || { rm -f "$SUDOERS"; say "หยุด: sudoers ทั้งเครื่องไม่ผ่านหลังเพิ่ม → เอาออกแล้ว"; exit 1; }
  say "+ เขียน $SUDOERS"
else
  say "[จะเขียน] $SUDOERS (0440)"; printf '%s\n' "$SUDOERS_TEXT" | sed 's/^/   /'
fi

say ""; say "4) ที่เก็บ $STATE (root 0700)"
if [ "$MODE" = "apply" ]; then
  install -d -o root -g root -m 0700 "$STATE" "$STATE/recovery" "$STATE/pending"
  say "+ สร้าง $STATE"
else
  say "[จะสร้าง] $STATE $STATE/recovery $STATE/pending"
fi

say ""; say "5) autologin ที่ tty1"
if [ -f "$AUTOLOGIN" ]; then
  if [ "$MODE" = "apply" ]; then
    mv "$AUTOLOGIN" "$PARKED" && systemctl daemon-reload && say "+ ย้าย $AUTOLOGIN ไปเก็บที่ $PARKED (คืนได้ด้วย --rollback)"
  else
    say "[จะย้าย] $AUTOLOGIN → $PARKED"
  fi
else
  say "   ไม่มี autologin ที่ tty1 · ไม่ต้องทำอะไร"
fi

say ""
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ตรวจ: sudo -l -U _greetd ต้องเห็นแค่ $WRAPPER"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-accounts.sh --apply"
fi
