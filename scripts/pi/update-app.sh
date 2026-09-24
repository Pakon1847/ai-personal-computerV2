#!/usr/bin/env bash
# อัปเดตแอป V2 ที่ /opt/aipc-v2 เป็น commit ปัจจุบันของ repo นี้ (ใช้หลังติดตั้งด้วย install-greeter.sh แล้ว)
#
#   ./scripts/pi/update-app.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/update-app.sh --apply     ทำจริง
#   sudo ./scripts/pi/update-app.sh --rollback  คืนแอปเป็นรุ่นก่อนอัปเดตครั้งล่าสุด
#
# ทำอะไร: เก็บสำรองไฟล์แอปเดิม (ไม่รวม .venv และโมเดล) เป็น tar · แตกไฟล์ commit ใหม่ทับ
#         · ติดตั้งแพ็กเกจ aipc รุ่นใหม่ลง venv เดิม (--no-deps: ไม่แตะ PySide6/OpenCV ที่มีอยู่)
# ไม่แตะ: greetd config, บริการ, PAM, ไฟล์บูต, พาร์ทิชัน · ไม่รีบูต · ไม่ลบ venv หรือโมเดล
# มีผลเมื่อ: หน้าจอ V2 เปิดใหม่ (ออกจากระบบแล้วเข้าใหม่) · หน้า Login ใช้รุ่นใหม่หลังออกจากระบบครั้งถัดไป
# ต้องมีเน็ต: pip ต้องดาวน์โหลดเครื่องมือ build (setuptools) · ถ้า build ไม่ผ่าน แพ็กเกจเดิมยังอยู่
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  "") ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST=/opt/aipc-v2
PY="$DEST/.venv/bin/python"
STAMP="$(date +%Y%m%d-%H%M%S)"
say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }
do_() { if [ "$MODE" = "apply" ] || [ "$MODE" = "rollback" ]; then say "+ $*"; "$@"; else say "[จะทำ] $*"; fi; }

[ -x "$PY" ] || { say "หยุด: ไม่พบ $PY · ติดตั้งครั้งแรกใช้ install-greeter.sh" >&2; exit 1; }
[ "$MODE" = "dry-run" ] || need_root

if [ "$MODE" = "rollback" ]; then
  LAST="$(ls -1t /opt/aipc-v2.backup-*.tar 2>/dev/null | head -1 || true)"
  [ -n "$LAST" ] || { say "หยุด: ไม่มีไฟล์สำรอง /opt/aipc-v2.backup-*.tar" >&2; exit 1; }
  say "คืนจาก $LAST"
  do_ tar -xf "$LAST" -C "$DEST"
  do_ "$DEST/.venv/bin/pip" install --no-deps --no-cache-dir --force-reinstall "$DEST"
  do_ chown -R root:root "$DEST"
  do_ chmod -R go-w,a+rX "$DEST"
  say "เสร็จ · ออกจากระบบแล้วเข้าใหม่เพื่อใช้รุ่นที่คืน ($(cat "$DEST/.installed-commit" 2>/dev/null || echo ไม่รู้ commit))"
  exit 0
fi

[ -d "$SRC/.git" ] || { say "หยุด: $SRC ไม่ใช่ git repo" >&2; exit 1; }
if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
  say "หยุด: $SRC มีไฟล์ที่ยังไม่ commit · ติดตั้งได้เฉพาะของที่ commit แล้ว (ผูกกับผลทดสอบได้)" >&2
  exit 1
fi
NEW="$(git -C "$SRC" rev-parse --short HEAD)"
OLD="$(cat "$DEST/.installed-commit" 2>/dev/null || echo ไม่รู้)"
say "อัปเดต $DEST: $OLD → $NEW"
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="

say "1) สำรองไฟล์แอปเดิม (ไม่รวม .venv และ models)"
do_ tar --exclude=./.venv --exclude=./models -cf "/opt/aipc-v2.backup-$STAMP.tar" -C "$DEST" .
say "2) แตกไฟล์ commit $NEW ทับ"
if [ "$MODE" = "apply" ]; then
  say "+ git archive HEAD | tar -x -C $DEST"
  git -C "$SRC" archive HEAD | tar -x -C "$DEST"
  printf '%s\n' "$NEW" > "$DEST/.installed-commit"
else
  say "[จะทำ] git archive HEAD | tar -x -C $DEST · เขียน $NEW ลง .installed-commit"
fi
say "3) ติดตั้งแพ็กเกจ aipc รุ่นใหม่ลง venv เดิม"
do_ "$DEST/.venv/bin/pip" install --no-deps --no-cache-dir --force-reinstall "$DEST"
do_ chown -R root:root "$DEST"
do_ chmod -R go-w,a+rX "$DEST"
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ออกจากระบบแล้วเข้าใหม่เพื่อใช้รุ่น $NEW · ย้อนกลับ: sudo $SRC/scripts/pi/update-app.sh --rollback"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/update-app.sh --apply"
fi
