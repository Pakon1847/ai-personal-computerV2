#!/usr/bin/env bash
# อัปเดตแอป V2 แบบโฟลเดอร์ต่อรุ่น + ลองเปิดหน้า Login ก่อนสลับ (ADR-009) · ใช้หลังติดตั้งด้วย install-greeter.sh
#
#   ./scripts/pi/update-app.sh                  ดูว่าจะทำอะไร + รุ่นที่ใช้อยู่ (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/update-app.sh --apply     สร้างรุ่นใหม่จาก commit ปัจจุบัน ทดสอบ แล้วจึงสลับ
#   sudo ./scripts/pi/update-app.sh --rollback  สลับกลับไปรุ่นก่อนหน้า (ไม่ต้องใช้เน็ต · ไม่ติดตั้งอะไรใหม่)
#
# โครงสร้าง: /opt/aipc-v2 เป็น symlink → /opt/aipc-releases/<commit>/ (แต่ละรุ่นมี .venv ของตัวเอง)
#   ครั้งแรก: ย้ายโฟลเดอร์ /opt/aipc-v2 เดิมไปเป็นรุ่นหนึ่งใน /opt/aipc-releases แล้วแทนด้วย symlink
#   (greetd config, สคริปต์เซสชัน และตัวช่วยสร้างบัญชียังใช้ path /opt/aipc-v2 เหมือนเดิม)
# ทำไม (เดิม): แตกไฟล์ทับของเดิม ทดสอบไม่ได้ก่อนใช้จริง · rollback ต้องใช้เน็ตและเลือกไฟล์สำรองผิดได้
#   หน้า Login คือส่วนที่ห้ามพังที่สุด อัปเดตพลาดครั้งเดียว = เหลือทางเข้าแค่ SSH/tty2 (ตรวจ 2026-09-28)
# ขั้นตอน --apply: สร้างรุ่นใหม่ในโฟลเดอร์ชั่วคราว → venv + ไลบรารีตาม constraints.txt (เก็บ wheel ไว้ใช้ออฟไลน์)
#   → **ลองเปิดหน้า Login ด้วยผู้ใช้ _greetd และหน้าจอเซสชันแบบไม่มีจอ** → ผ่านจึงสลับ symlink ทีเดียว
#   → เก็บรุ่นก่อนหน้าไว้ 1 รุ่นสำหรับ --rollback · ลบรุ่นที่เก่ากว่านั้น
# ไม่แตะ: greetd config, บริการ, PAM, ไฟล์บูต, พาร์ทิชัน · ไม่รีบูต
# มีผลเมื่อ: หน้าจอเปิดใหม่ (ออกจากระบบแล้วเข้าใหม่)
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  "") ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINK=/opt/aipc-v2
RELEASES=/opt/aipc-releases
WHEELS="$RELEASES/wheels"
PREVIOUS="$RELEASES/previous"   # ไฟล์บอกชื่อรุ่นก่อนหน้า
STAMP="$(date +%Y%m%d-%H%M%S)"
say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }
current() { [ -L "$LINK" ] && basename "$(readlink -f "$LINK")" || echo ""; }
switch_to() {  # สลับ symlink ทีเดียว (mv -T ของ symlink ใหม่ทับตัวเดิม = ไม่มีช่วงที่ไม่มี /opt/aipc-v2)
  ln -sfn "$RELEASES/$1" "$LINK.new"
  mv -T "$LINK.new" "$LINK"
}

say "รุ่นที่ใช้อยู่: $(current || true)$([ -L "$LINK" ] || printf ' (ยังเป็นโฟลเดอร์ธรรมดา · --apply ครั้งแรกจะย้ายเข้า %s)' "$RELEASES")"
[ -f "$PREVIOUS" ] && say "รุ่นก่อนหน้า (--rollback): $(cat "$PREVIOUS")"

# ---------- ย้อนกลับ: สลับ symlink อย่างเดียว ----------
if [ "$MODE" = "rollback" ]; then
  need_root
  [ -f "$PREVIOUS" ] || { say "หยุด: ไม่มีรุ่นก่อนหน้าให้ย้อน" >&2; exit 1; }
  BACK="$(cat "$PREVIOUS")"
  [ -x "$RELEASES/$BACK/.venv/bin/python" ] || { say "หยุด: รุ่น $BACK ไม่ครบ" >&2; exit 1; }
  NOW="$(current)"
  switch_to "$BACK"
  printf '%s\n' "$NOW" > "$PREVIOUS"
  say "เสร็จ · ใช้รุ่น $BACK แล้ว (รุ่นก่อนหน้าตอนนี้คือ $NOW) · ออกจากระบบแล้วเข้าใหม่เพื่อใช้รุ่นนี้"
  exit 0
fi

[ -d "$SRC/.git" ] || { say "หยุด: $SRC ไม่ใช่ git repo" >&2; exit 1; }
if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
  say "หยุด: $SRC มีไฟล์ที่ยังไม่ commit · ติดตั้งได้เฉพาะของที่ commit แล้ว (ผูกกับผลทดสอบได้)" >&2
  exit 1
fi
NEWID="$(git -C "$SRC" rev-parse --short=8 HEAD)"
say "จะสร้างรุ่น: $NEWID"
if [ "$MODE" != "apply" ]; then
  say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
  say "[จะทำ] สร้าง $RELEASES/$NEWID → ติดตั้ง venv ตาม constraints.txt → ลองเปิดหน้า Login (_greetd) และหน้าจอเซสชัน → สลับ $LINK"
  say "ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/update-app.sh --apply"
  exit 0
fi
need_root
[ "$(current)" = "$NEWID" ] && { say "ใช้รุ่น $NEWID อยู่แล้ว · ไม่ต้องทำอะไร"; exit 0; }
getent passwd _greetd >/dev/null || { say "หยุด: ไม่มีผู้ใช้ _greetd" >&2; exit 1; }
mkdir -p "$RELEASES" "$WHEELS"

# ---------- ครั้งแรก: ย้ายโฟลเดอร์เดิมเป็นรุ่นหนึ่ง แล้วแทนด้วย symlink ----------
if [ -d "$LINK" ] && [ ! -L "$LINK" ]; then
  OLDID="$(cat "$LINK/.installed-commit" 2>/dev/null || echo "legacy-$STAMP")"
  say "+ ย้าย $LINK เดิม → $RELEASES/$OLDID แล้วแทนด้วย symlink"
  mv "$LINK" "$RELEASES/$OLDID"
  ln -sfn "$RELEASES/$OLDID" "$LINK"
fi
OLD="$(current)"

# ---------- สร้างรุ่นใหม่ในโฟลเดอร์ชั่วคราว ----------
TMP="$RELEASES/.building-$NEWID"
rm -rf "$TMP"
trap 'rm -rf "$TMP"' EXIT   # ล้มตรงไหน = ลบของครึ่ง ๆ ทิ้ง รุ่นที่ใช้อยู่ไม่ถูกแตะ
mkdir -p "$TMP"
say "+ git archive $NEWID → $TMP"
git -C "$SRC" archive HEAD | tar -x -C "$TMP"
printf '%s\n' "$NEWID" > "$TMP/.installed-commit"
python3 -m venv "$TMP/.venv"
PIP="$TMP/.venv/bin/pip"
# เก็บ wheel ไว้ในเครื่อง: ครั้งหน้าติดตั้งได้แม้ไม่มีเน็ต · ออฟไลน์ตอนนี้ = ใช้ wheel ที่เคยเก็บไว้
"$PIP" download -q -d "$WHEELS" -c "$TMP/constraints.txt" "setuptools>=68" \
  PySide6-Essentials opencv-python-headless numpy icalendar recurring-ical-events \
  || say "   ดาวน์โหลดไม่ได้ (ออฟไลน์?) · ใช้ wheel ที่เก็บไว้ใน $WHEELS"
"$PIP" install -q --no-index --find-links "$WHEELS" "setuptools>=68"
"$PIP" install -q --no-index --find-links "$WHEELS" --no-build-isolation \
  -c "$TMP/constraints.txt" "$TMP[ui,vision]"
if [ -n "$OLD" ] && [ -d "$RELEASES/$OLD/models" ]; then
  cp -a "$RELEASES/$OLD/models" "$TMP/models"   # โมเดลใบหน้า (ตรวจ sha256 ทุกครั้งที่โหลดอยู่แล้ว)
fi
chown -R root:root "$TMP"
chmod -R go-w,a+rX "$TMP"

# ---------- ลองเปิดก่อนสลับ ----------
# ตัวเปิดหน้า Login (greetd เรียก aipc-greeter ของรุ่นที่ใช้อยู่) ต้องมี รันได้ และมีไฟล์ผังแป้นครบ · ไม่งั้นรีบูตแล้วหน้า Login หาย
G="$TMP/scripts/pi/session"
if ! { [ -x "$G/aipc-greeter" ] && sh -n "$G/aipc-greeter" && [ -f "$G/labwc/environment" ] \
       && [ -f "$G/xkb/rules/evdev" ] && [ -f "$G/xkb/symbols/aipc" ]; }; then
  say "หยุด: รุ่น $NEWID ไม่มีตัวเปิดหน้า Login (aipc-greeter + ผังแป้น) ที่ใช้ได้ · ไม่ได้สลับ (ยังใช้รุ่น $OLD)"
  exit 1
fi
say "+ ลองเปิดหน้า Login ด้วยผู้ใช้ _greetd (ไม่มีจอ)"
SHOT="$(mktemp -d)"
chmod 0777 "$SHOT"
smoke() {  # smoke <ผู้ใช้> <ชื่อไฟล์ภาพ> <อาร์กิวเมนต์ของ aipc.ui...>
  local who="$1" png="$SHOT/$2"; shift 2
  runuser -u "$who" -- env QT_QPA_PLATFORM=offscreen HOME="$SHOT" XDG_RUNTIME_DIR="$SHOT" \
    XDG_CONFIG_HOME="$SHOT/cfg-$who" XDG_DATA_HOME="$SHOT/data-$who" XDG_STATE_HOME="$SHOT/state-$who" \
    timeout 90 "$TMP/.venv/bin/python" -m aipc.ui "$@" --software --screenshot "$png" >"$SHOT/$who.log" 2>&1 \
    && [ -s "$png" ]
}
if ! smoke _greetd greeter.png --greeter labwc; then
  say "หยุด: รุ่น $NEWID เปิดหน้า Login ไม่ขึ้น · ไม่ได้สลับ (ยังใช้รุ่น $OLD)"
  tail -20 "$SHOT/_greetd.log" || true
  exit 1
fi
WHO="${SUDO_USER:-}"
if [ -n "$WHO" ] && [ "$WHO" != root ]; then
  say "+ ลองเปิดหน้าจอเซสชันด้วยผู้ใช้ $WHO (ไม่มีจอ)"
  smoke "$WHO" session.png --session || { say "หยุด: หน้าจอเซสชันเปิดไม่ขึ้น · ไม่ได้สลับ"; tail -20 "$SHOT/$WHO.log" || true; exit 1; }
fi
rm -rf "$SHOT"

# ---------- สลับ ----------
rm -rf "${RELEASES:?}/$NEWID"
mv "$TMP" "$RELEASES/$NEWID"
trap - EXIT
switch_to "$NEWID"
[ -n "$OLD" ] && printf '%s\n' "$OLD" > "$PREVIOUS"
say "+ สลับ $LINK → $RELEASES/$NEWID"

# เก็บแค่รุ่นปัจจุบัน + รุ่นก่อนหน้า
for d in "$RELEASES"/*/; do
  id="$(basename "$d")"
  case "$id" in "$NEWID"|"$OLD"|wheels) continue ;; esac
  # ยังมีโปรเซสใช้รุ่นนี้อยู่ (เซสชันที่ login ไว้ก่อนอัปเดต) = เก็บไว้ ลบรอบหน้า
  # พบบน Pi 5 2026-10-01: ลบรุ่นที่เซสชันใช้อยู่ → หน้าจอล่มครั้งเดียวก็เปิดใหม่ไม่ได้ เด้งกลับหน้า Login
  if pgrep -f "$RELEASES/$id/" >/dev/null 2>&1; then
    say "+ เก็บรุ่น $id ไว้ (ยังมีคนใช้อยู่)"
    continue
  fi
  rm -rf "${RELEASES:?}/$id" && say "+ ลบรุ่นเก่า $id"
done

say "เสร็จ · ใช้รุ่น $NEWID · ออกจากระบบแล้วเข้าใหม่เพื่อใช้รุ่นนี้ · ย้อนกลับ: sudo $SRC/scripts/pi/update-app.sh --rollback"
say "   หน้า Login ที่เปิดค้างอยู่ยังเป็นรุ่นเดิม · เปิดใหม่: sudo systemctl restart greetd (เฉพาะตอนไม่มีใครใช้ที่จอ) หรือรีบูต"
# เครื่องที่ติดตั้งก่อน 2026-09-29: greetd ยังเรียก cage ตรง ๆ = หน้า Login ไม่มีแป้นไทย
if [ -f /etc/greetd/config.toml ] && ! grep -q aipc-greeter /etc/greetd/config.toml; then
  say "   หมายเหตุ: หน้า Login ยังใช้คำสั่งแบบเก่า (พิมพ์ไทยไม่ได้) → sudo $SRC/scripts/pi/install-greeter.sh --config-only --apply"
fi
