#!/usr/bin/env bash
# Chromium ไม่ใช้ keyring ของระบบ (Pakon เลือกทาง ข 2026-10-06)
#
#   ./scripts/pi/install-browser.sh             ดูว่าจะทำอะไร
#   sudo ./scripts/pi/install-browser.sh --apply
#   sudo ./scripts/pi/install-browser.sh --rollback
#
# ทำไม: เข้าเครื่องด้วยใบหน้าไม่ได้ใส่รหัสผ่าน → gnome-keyring ไม่ถูกปลด (journal: "gkr-pam: couldn't unlock the login keyring") →
#   เปิด Chromium แล้วมีหน้าต่างถามรหัส keyring ซึ่งไปอยู่ด้านหลังจอ · Chromium โหลดเว็บไม่ได้จนกว่าจะใส่รหัส (ทดสอบ Pi 5 2026-10-06)
# ทำอะไร: /etc/chromium.d/aipc-password-store (ตัวเปิด /usr/bin/chromium อ่านทุกไฟล์ในโฟลเดอร์นี้) → --password-store=basic
# ผลที่ยอมรับ (THREAT_MODEL): คุกกี้/รหัสผ่านเว็บไม่ได้เข้ารหัสด้วยรหัสผ่านเข้าเครื่อง → ถอด microSD ไปอ่านได้ (เหมือนแชทและไฟล์ · T4) ·
#   หลังเปลี่ยน คุกกี้ที่เข้ารหัสด้วย keyring เดิมอ่านไม่ได้ → ทุกคน login เว็บใหม่ 1 ครั้ง · home ยัง 0700 (บัญชีอื่นอ่านไม่ได้)
# ไม่แตะ greetd, PAM, ไฟล์บูต · ไม่รีบูต · มีผลเมื่อเปิด Chromium ครั้งถัดไป
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  "") ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac
DIR="${AIPC_CHROMIUM_D:-/etc/chromium.d}"   # เทสต์ใช้โฟลเดอร์ชั่วคราว
FILE="$DIR/aipc-password-store"
say() { printf '%s\n' "$*"; }
need_root() { [ -n "${AIPC_CHROMIUM_D:-}" ] || [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

if [ "$MODE" = "rollback" ]; then
  need_root
  rm -f "$FILE"
  say "เสร็จ · ลบ $FILE แล้ว · Chromium กลับไปใช้ keyring ตามเดิม (เปิดใหม่แล้วมีผล)"
  exit 0
fi

[ -d "$DIR" ] || { say "หยุด: ไม่มี $DIR (Chromium ของเครื่องนี้ไม่อ่านโฟลเดอร์นี้?)" >&2; exit 1; }
if [ -f "$FILE" ]; then say "มี $FILE อยู่แล้ว"; else say "[จะทำ] สร้าง $FILE → Chromium ใช้ --password-store=basic (ไม่ถามรหัส keyring)"; fi
[ "$MODE" = "apply" ] || { say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร · ใส่ --apply เพื่อทำจริง =="; exit 0; }
need_root
umask 022
cat > "$FILE.tmp" <<'EOF'
# AI PC V2 (scripts/pi/install-browser.sh · Pakon เลือก 2026-10-06): ไม่ใช้ keyring ของระบบ
# เข้าด้วยใบหน้าแล้ว keyring ไม่ถูกปลด → Chromium ถามรหัสในหน้าต่างที่ไปอยู่ด้านหลัง · ลบไฟล์นี้ = กลับไปใช้ keyring
export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --password-store=basic"
EOF
mv "$FILE.tmp" "$FILE"
say "เสร็จ · $FILE · เปิด Chromium ใหม่แล้วมีผล (เว็บที่เคย login ต้อง login ใหม่ 1 ครั้ง)"
