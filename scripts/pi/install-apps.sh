#!/usr/bin/env bash
# ตัวติดตั้งแอปจากรายการที่อนุญาต (การ์ด 0054) · ผู้ใช้สั่ง "เปิด X" แล้วไม่มี X → ผู้ดูแลใส่รหัสแล้วติดตั้งให้
# ใช้หลัง install-accounts.sh (ต้องมีแอปที่ /opt/aipc-v2 แล้ว)
#
#   ./scripts/pi/install-apps.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-apps.sh --apply     ทำจริง
#   sudo ./scripts/pi/install-apps.sh --rollback  ลบตัวติดตั้ง กฎ sudo และไฟล์ PAM (แอปที่ติดตั้งไปแล้วยังอยู่)
#
# ทำอะไร:
#   1. /usr/local/sbin/aipc-apps (root 0755) = เรียก python -I -m aipc.accounts.apphelper จาก /opt/aipc-v2
#   2. (รุ่นแรกเคยเขียน /etc/pam.d/aipc-apps ไว้ตรวจรหัสผู้ดูแล · เลิกถามรหัสแล้ว 2026-10-23 → ลบทิ้งถ้ามี)
#   3. /etc/sudoers.d/aipc-apps = ทุกบัญชีเรียกตัวติดตั้งได้คำสั่งเดียว ห้ามใส่อาร์กิวเมนต์
#      ตัวติดตั้งตรวจเอง: ชื่อแอปต้องอยู่ในรายการ · เรียกจากเซสชันของผู้ใช้ · ดิสก์ว่าง ≥ 2 GB (ไม่ถามรหัส · Pakon 2026-10-23)
#      **ตรวจด้วย visudo -c ก่อนติดตั้งเสมอ** (ไฟล์ sudoers ผิด = sudo ใช้ไม่ได้ทั้งเครื่อง)
# ไม่แตะ: รายการแอป (/etc/aipc/apps-allowed.json ผู้ดูแลเขียนเองถ้าจะเปลี่ยน) · greetd · ไฟล์บูต · ไม่รีบูต
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

DEST=/opt/aipc-v2
WRAPPER=/usr/local/sbin/aipc-apps
PAMFILE=/etc/pam.d/aipc-apps  # รุ่นแรกเท่านั้น · ลบทิ้ง
SUDOERS=/etc/sudoers.d/aipc-apps

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

WRAPPER_TEXT='#!/bin/sh
# ตัวติดตั้งแอปจากรายการที่อนุญาต (การ์ด 0054) · เรียกผ่าน sudo เท่านั้น · คำขอเป็น JSON ทาง stdin
# -I = ไม่อ่าน PYTHONPATH และ site ของผู้ใช้ → โหลดโค้ดจาก /opt/aipc-v2 ที่ root เป็นเจ้าของเท่านั้น
exec /opt/aipc-v2/.venv/bin/python -I -m aipc.accounts.apphelper'
SUDOERS_TEXT='# บัญชีบนเครื่องเรียกตัวติดตั้งแอปของ aipc ได้คำสั่งเดียว ห้ามใส่อาร์กิวเมนต์ (การ์ด 0054)
# ตัวติดตั้งตรวจเอง: แอปในรายการเท่านั้น · เรียกจากเซสชันของผู้ใช้ · ดิสก์ว่างพอ
ALL ALL=(root) NOPASSWD: /usr/local/sbin/aipc-apps ""'

if [ "$MODE" = "rollback" ]; then
  need_root
  rm -f "$SUDOERS" && say "+ ลบ $SUDOERS"
  rm -f "$WRAPPER" "$PAMFILE" && say "+ ลบ $WRAPPER และ $PAMFILE"
  say "เสร็จ · แอปที่ติดตั้งไปแล้วยังอยู่ (ถอนเองด้วย apt ถ้าไม่ใช้)"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
[ -x "$DEST/.venv/bin/python" ] || { say "หยุด: ไม่มี $DEST/.venv · รัน install-greeter.sh ก่อน"; exit 1; }
"$DEST/.venv/bin/python" -I -c "import aipc.accounts.apphelper" \
  || { say "หยุด: แอปใน $DEST ยังไม่มีตัวติดตั้ง (อัปเดตแอปก่อน)"; exit 1; }

install_text() {  # install_text <ไฟล์ปลายทาง> <โหมด> <เนื้อหา>
  if [ "$MODE" != "apply" ]; then say "[จะเขียน] $1 ($2)"; printf '%s\n' "$3" | sed 's/^/   /'; return; fi
  install -d -m 0755 "$(dirname "$1")"
  local tmp; tmp="$(mktemp)"
  printf '%s\n' "$3" > "$tmp"
  install -o root -g root -m "$2" "$tmp" "$1"
  rm -f "$tmp"
  say "+ เขียน $1"
}

say ""; say "1) ตัวติดตั้ง $WRAPPER"
install_text "$WRAPPER" 0755 "$WRAPPER_TEXT"
say ""; say "2) ไฟล์ PAM ของรุ่นแรก $PAMFILE"
if [ -f "$PAMFILE" ]; then
  if [ "$MODE" = "apply" ]; then rm -f "$PAMFILE" && say "+ ลบ $PAMFILE"; else say "[จะลบ] $PAMFILE"; fi
else
  say "   ไม่มี · ไม่ต้องทำอะไร"
fi

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

say ""
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ตรวจ: sudo -l -U <ผู้ใช้ทั่วไป> ต้องเห็น $WRAPPER"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-apps.sh --apply"
fi
