#!/usr/bin/env bash
# ให้ทุกบัญชีผู้ใช้เลือก Wi-Fi ของเครื่องได้จากแถบบน (การ์ด 0063 ทาง ก · Pakon "ทุกบัญชี" 2026-10-24)
#
#   ./scripts/pi/install-wifi-access.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-wifi-access.sh --apply     ทำจริง
#   sudo ./scripts/pi/install-wifi-access.sh --rollback  เอาออกจาก netdev เฉพาะบัญชีที่สคริปต์นี้ใส่ไว้
#
# ทำไมเป็นกลุ่ม netdev: Raspberry Pi OS มีกฎ polkit อยู่แล้วว่าคนในกลุ่ม netdev (หรือ sudo)
#   แก้การตั้งค่าเครือข่ายของทั้งเครื่องได้ (settings.modify.system) · เราจึงไม่ต้องเขียนกฎ polkit เอง
# ทำอะไร: usermod -aG netdev <บัญชี> ให้บัญชีคน (uid 1000–59999 · shell ไม่ใช่ nologin) ที่ยังไม่อยู่
#   จดรายชื่อที่ใส่ไว้ใน /var/lib/aipc/netdev-added (ใช้ตอนย้อนกลับ ไม่ไปเอาคนที่อยู่มาก่อนออก)
# มีผลเมื่อบัญชีนั้นออกจากระบบแล้วเข้าใหม่ · บัญชีใหม่ที่สมัครที่หน้า Login ได้ netdev เอง (accounts/helper.py)
# ไม่แตะ: กฎ polkit, NetworkManager, sudo, ไฟล์บูต · ไม่รีบูต
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

GROUP=netdev
RECORD=/var/lib/aipc/netdev-added

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }
in_group() { id -nG "$1" | tr ' ' '\n' | grep -qx "$GROUP"; }

getent group "$GROUP" >/dev/null || { say "หยุด: เครื่องนี้ไม่มีกลุ่ม $GROUP"; exit 1; }

if [ "$MODE" = "rollback" ]; then
  need_root
  [ -f "$RECORD" ] || { say "ไม่มี $RECORD · ไม่มีอะไรต้องย้อน"; exit 0; }
  while read -r u; do
    [ -n "$u" ] || continue
    if getent passwd "$u" >/dev/null && in_group "$u"; then
      gpasswd -d "$u" "$GROUP" >/dev/null && say "+ เอา $u ออกจาก $GROUP"
    fi
  done < "$RECORD"
  rm -f "$RECORD"
  say "เสร็จ · มีผลเมื่อออกจากระบบแล้วเข้าใหม่"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="

added=0
while IFS=: read -r name _ uid _ _ _ shell; do
  [ "$uid" -ge 1000 ] && [ "$uid" -lt 60000 ] || continue
  case "$shell" in */nologin|*/false) continue ;; esac
  if in_group "$name"; then
    say "  $name อยู่ใน $GROUP แล้ว"
  elif [ "$MODE" = "apply" ]; then
    usermod -aG "$GROUP" "$name"
    install -d -m 0700 "$(dirname "$RECORD")"
    printf '%s\n' "$name" >> "$RECORD"
    chmod 0600 "$RECORD"
    say "+ ใส่ $name เข้า $GROUP"
    added=$((added + 1))
  else
    say "[จะทำ] usermod -aG $GROUP $name"
    added=$((added + 1))
  fi
done < <(getent passwd)

if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ใส่ $added บัญชี · มีผลเมื่อออกจากระบบแล้วเข้าใหม่ · ย้อน = --rollback"
else
  say "จะใส่ $added บัญชี · ทำจริง: sudo $0 --apply"
fi
