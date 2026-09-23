#!/usr/bin/env bash
# เอาระบบเก่า ai-pc-2 ออกจาก Pi (ผู้ใช้สั่ง 2026-09-23: "ลบออกไปเลย เราไม่ใช้")
#
#   ./scripts/pi/remove-ai-pc-2.sh               ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/remove-ai-pc-2.sh --apply  ทำจริง
#
# ai-pc-2 ไม่ได้ตั้งให้เปิดเองตอนบูต (ไม่ได้แตะ greetd/lightdm/PAM) · ที่ต้องเอาออกมี:
#   1. บัญชีทดสอบที่ home อยู่ใน /srv/aipc/home (usera, userb)
#   2. ระบบไฟล์ /var/lib/aipc/homes.img ที่ต่อไว้ที่ /srv/aipc/home + บรรทัดใน /etc/fstab
#   3. /etc/fscrypt.conf (สร้างโดย fscrypt setup)
#   4. โค้ดที่ ~/ai-pc-2
#
# ปลอดภัยกว่า teardown เดิมของ ai-pc-2 ตรงที่:
#   - /etc/fstab: สำรองก่อน · ลบเฉพาะบรรทัดเดียวที่ตรงเป๊ะ · ตรวจว่าต่างจากเดิมแค่บรรทัดนั้นจริงก่อนเขียนทับ
#   - ถอด mount ไม่ได้ (มีโปรแกรมใช้อยู่) → หยุด ไม่ฝืน
#   - โค้ด ~/ai-pc-2 ถูกบีบอัดเก็บไว้ใน home ก่อนลบ (เผื่อมีผลวัดบน Pi ที่ยังไม่ได้ส่งกลับ) · ไม่รวม .venv
# ไม่แตะ: ไฟล์บูต, พาร์ทิชัน, greetd, lightdm, PAM, ระบบเก่า "ai computer" (/opt/ai-pc) · อันนั้นแยกขั้นตอน
set -euo pipefail

IMAGE=/var/lib/aipc/homes.img
MOUNT=/srv/aipc/home
# AIPC_TEST_*: ใช้แค่ในเทสต์ เพื่อชี้ไปที่ไฟล์จำลอง
FSTAB="${AIPC_TEST_FSTAB:-/etc/fstab}"
PASSWD="${AIPC_TEST_PASSWD:-/etc/passwd}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/root/aipc-old-backup-$STAMP"

APPLY=0
case "${1:-}" in
  "") ;;
  --apply) APPLY=1 ;;
  *) echo "ไม่รู้จัก: $1 (ใช้ --apply)" >&2; exit 2 ;;
esac
if [ "$APPLY" = 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "--apply ต้องรันด้วย sudo" >&2; exit 1
fi

OWNER="${SUDO_USER:-$(id -un)}"
OWNER_HOME="${AIPC_TEST_HOME:-$(getent passwd "$OWNER" | cut -d: -f6)}"
CHECKOUT="$OWNER_HOME/ai-pc-2"

say() { printf '%s\n' "$*"; }
do_() { if [ "$APPLY" = 1 ]; then say "+ $*"; "$@"; else say "[จะทำ] $*"; fi; }
[ "$APPLY" = 1 ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="

# ---------- 1. บัญชีทดสอบ ----------
say ""; say "1) บัญชีที่ home อยู่ใน $MOUNT"
USERS=()
while IFS=: read -r name _ _ _ _ home _; do
  case "$home" in "$MOUNT"/*) USERS+=("$name") ;; esac
done < "$PASSWD"
if [ "${#USERS[@]}" = 0 ]; then say "   ไม่มี"; fi
for u in "${USERS[@]}"; do
  if [ -n "$(pgrep -u "$u" 2>/dev/null)" ]; then
    say "หยุด: บัญชี $u ยังมีโปรแกรมทำงานอยู่ (ออกจากระบบบัญชีนั้นก่อน)"; exit 1
  fi
  do_ userdel "$u"
done

# ---------- 2. ระบบไฟล์ + /etc/fstab ----------
say ""; say "2) $MOUNT และ $IMAGE"
if mountpoint -q "$MOUNT" 2>/dev/null; then
  if [ "$APPLY" = 1 ] && ! umount "$MOUNT"; then
    say "หยุด: ถอด $MOUNT ไม่ได้ · ดูว่าใครใช้อยู่ด้วย: sudo fuser -vm $MOUNT"; exit 1
  fi
  [ "$APPLY" = 1 ] && say "+ umount $MOUNT" || say "[จะทำ] umount $MOUNT"
else
  say "   ไม่ได้ต่ออยู่"
fi

PATTERN="^${IMAGE//./\\.}[[:space:]]+${MOUNT}[[:space:]]"
COUNT="$(grep -cE "$PATTERN" "$FSTAB" || true)"
case "$COUNT" in
  0) say "   $FSTAB ไม่มีบรรทัดของ ai-pc-2" ;;
  1)
    say "   บรรทัดที่จะเอาออกจาก $FSTAB:"; grep -nE "$PATTERN" "$FSTAB" | sed 's/^/     /'
    TMP="$(mktemp)"
    grep -vE "$PATTERN" "$FSTAB" > "$TMP" || true
    # ต้องต่างจากเดิมแค่บรรทัดเดียวนั้นเท่านั้น ไม่งั้นไม่เขียน
    if [ "$(diff "$FSTAB" "$TMP" | grep -c '^[<>]')" != 1 ]; then
      say "หยุด: ผลลัพธ์ต่างจาก $FSTAB เดิมมากกว่าหนึ่งบรรทัด ไม่เขียนทับ"; rm -f "$TMP"; exit 1
    fi
    if [ "$APPLY" = 1 ]; then
      cp -a "$FSTAB" "$FSTAB.before-remove-ai-pc-2-$STAMP"
      say "+ สำรองไว้ที่ $FSTAB.before-remove-ai-pc-2-$STAMP"
      cat "$TMP" > "$FSTAB"   # เขียนทับเนื้อหา คงเจ้าของและสิทธิ์ไฟล์เดิม
      say "+ เอาบรรทัดออกแล้ว"
      systemctl daemon-reload
    else
      say "[จะทำ] สำรอง $FSTAB แล้วเอาบรรทัดนั้นออก"
    fi
    rm -f "$TMP"
    ;;
  *) say "หยุด: เจอบรรทัดของ ai-pc-2 ใน $FSTAB มากกว่าหนึ่งบรรทัด ($COUNT) · ส่งไฟล์นี้มาให้ดูก่อน"; exit 1 ;;
esac

if [ -f "$IMAGE" ]; then do_ rm -f "$IMAGE"; else say "   ไม่มี $IMAGE"; fi
for d in "$MOUNT" /srv/aipc /var/lib/aipc; do
  [ -d "$d" ] && do_ rmdir --ignore-fail-on-non-empty "$d"
done

# ---------- 3. /etc/fscrypt.conf ----------
say ""; say "3) /etc/fscrypt.conf"
if [ -f /etc/fscrypt.conf ]; then
  do_ mkdir -p "$BACKUP"
  do_ mv /etc/fscrypt.conf "$BACKUP/"
else
  say "   ไม่มี"
fi

# ---------- 4. โค้ด ~/ai-pc-2 ----------
say ""; say "4) $CHECKOUT"
if [ -d "$CHECKOUT/.git" ] && [ -f "$CHECKOUT/scripts/aipc-homes.sh" ]; then
  ARCHIVE="$OWNER_HOME/ai-pc-2-archive-$STAMP.tar.gz"
  say "   เก็บสำเนาไว้ที่ $ARCHIVE ก่อนลบ (ไม่รวม .venv) · ลบไฟล์นี้เองได้เมื่อแน่ใจ"
  do_ tar --exclude=.venv -czf "$ARCHIVE" -C "$OWNER_HOME" ai-pc-2
  [ "$APPLY" = 1 ] && chown "$OWNER": "$ARCHIVE"
  do_ rm -rf "$CHECKOUT"
elif [ -e "$CHECKOUT" ]; then
  say "หยุด: $CHECKOUT มีอยู่แต่ไม่เหมือน repo ai-pc-2 · ไม่ลบ ตรวจด้วยตาก่อน"; exit 1
else
  say "   ไม่มี"
fi

say ""
if [ "$APPLY" = 1 ]; then
  say "เสร็จ · ของที่สำรองไว้: $FSTAB.before-remove-ai-pc-2-$STAMP, $BACKUP/, ~/ai-pc-2-archive-*.tar.gz"
  say "ตรวจซ้ำได้ด้วย ./scripts/pi/check-old-system.sh"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/remove-ai-pc-2.sh --apply"
fi
