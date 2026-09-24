#!/usr/bin/env bash
# ให้หน้า Login ของ V2 เป็นหน้า login จริงของเครื่อง (การ์ดออกแบบ 0003) · ใช้กับ Raspberry Pi OS ที่ลงใหม่
#
#   ./scripts/pi/install-greeter.sh                   ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-greeter.sh --apply      ทำจริง (ถามยืนยันเรื่องทางเข้าสำรองก่อน)
#   sudo ./scripts/pi/install-greeter.sh --rollback   กลับไปใช้หน้า login เดิมของ Raspberry Pi OS (lightdm)
#   ตัวเลือก: --session "คำสั่ง"  เซสชันที่จะเริ่มหลังเข้าได้ (ค่าเริ่มต้น: อ่านจาก lightdm.conf = เดสก์ท็อป Pi)
#             --session v2       หน้าจอ V2 เป็นทั้งเซสชัน ไม่มีเดสก์ท็อป Pi (การ์ด 0004)
#
# ทำอะไร: ติดตั้ง greetd + cage (apt) · คัดลอกแอปไปที่ /opt/aipc-v2 ให้ผู้ใช้ _greetd อ่านได้
#         · เขียน /etc/greetd/config.toml (สำรองของเดิมก่อน) · ปิด lightdm เปิด greetd · **ไม่รีบูตให้**
# ไม่แตะ: PAM (ใช้ชุด login ปกติของ OS), ไฟล์บูต, พาร์ทิชัน, /etc/fstab · ไม่ถอน lightdm (ย้อนกลับได้เสมอ)
# ทางเข้าสำรอง: cage รันด้วย -s จึงกด Ctrl+Alt+F2 ไปหน้าจอตัวหนังสือได้ แล้วรัน --rollback
set -euo pipefail

MODE="dry-run"
SESSION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) MODE="apply" ;;
    --rollback) MODE="rollback" ;;
    --session) SESSION="${2:?--session ต้องตามด้วยคำสั่ง}"; shift ;;
    *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
  esac
  shift
done

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST=/opt/aipc-v2
CONF=/etc/greetd/config.toml
STAMP="$(date +%Y%m%d-%H%M%S)"
# การ์ด 0004: เซสชันของ V2 เอง (labwc + ค่าตั้งของเรา + หน้าจอ V2) · ไฟล์อยู่ในแอปที่คัดลอกไป $DEST
if [ "$SESSION" = "v2" ]; then
  SESSION="$DEST/scripts/pi/session/aipc-session"
  [ -x "$SRC/scripts/pi/session/aipc-session" ] || { echo "หยุด: ไม่มี scripts/pi/session/aipc-session ใน $SRC" >&2; exit 1; }
fi

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

# ---------- ย้อนกลับ ----------
if [ "$MODE" = "rollback" ]; then
  need_root
  systemctl disable greetd || true
  systemctl enable lightdm
  LAST="$(ls -1t "$CONF".before-aipc-* 2>/dev/null | head -1 || true)"
  if [ -n "$LAST" ]; then cp -a "$LAST" "$CONF"; say "+ คืน $CONF จาก $LAST"; fi
  say "เสร็จ · รีบูตแล้วจะกลับมาเป็นหน้า login ของ Raspberry Pi OS · $DEST ยังอยู่ (ลบเองได้)"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
do_() { if [ "$MODE" = "apply" ]; then say "+ $*"; "$@"; else say "[จะทำ] $*"; fi; }

# ---------- ตรวจ ----------
ARCH="$(uname -m)"
GLIBC="$(python3 -c 'import os; f = getattr(os, "confstr", None); print(f("CS_GNU_LIBC_VERSION").split()[1] if f else "unknown")')"
say "เครื่อง: $ARCH · glibc $GLIBC"
if [ "$ARCH" = "aarch64" ] && ! python3 -c "import sys; v = tuple(int(x) for x in '$GLIBC'.split('.')[:2]); sys.exit(v < (2, 39))" 2>/dev/null; then
  say "หยุด: glibc $GLIBC ต่ำกว่า 2.39 → PySide6 จาก pip ใช้ไม่ได้ · ต้องใช้ Raspberry Pi OS รุ่น trixie"; exit 1
fi
[ -d "$SRC/.git" ] || { say "หยุด: $SRC ไม่ใช่ git repo (ต้อง clone จาก aipc.bundle)"; exit 1; }
if [ -n "$(git -C "$SRC" status --porcelain 2>/dev/null)" ]; then
  say "หยุด: $SRC มีไฟล์ที่แก้แต่ยังไม่ commit · ติดตั้งเฉพาะของที่ commit แล้วเท่านั้น"; exit 1
fi

# เซสชันหลังเข้าได้: ใช้ตัวเดียวกับที่ lightdm ใช้อยู่ ถ้าไม่ได้บอกมา
if [ -z "$SESSION" ]; then
  # ภาพ OS ที่เพิ่งลงอาจไม่มีบรรทัดนี้ (lightdm.conf มีแค่ #user-session=default) → ใช้ชื่อมาตรฐานของ Pi OS
  # trixie = rpd-labwc · bookworm = LXDE-pi-labwc (ยืนยันจาก raspi-config do_wayland และแพ็กเกจ rpd-wayland-core)
  NAME="$(grep -E '^\s*user-session\s*=' /etc/lightdm/lightdm.conf 2>/dev/null | tail -1 | cut -d= -f2 | tr -d ' ' || true)"
  for n in "$NAME" rpd-labwc LXDE-pi-labwc; do
    FILE="/usr/share/wayland-sessions/$n.desktop"
    if [ -n "$n" ] && [ -f "$FILE" ]; then
      SESSION="$(grep -E '^Exec=' "$FILE" | head -1 | cut -d= -f2-)"
      say "ใช้เซสชันจาก $FILE"
      break
    fi
  done
fi
if [ -z "$SESSION" ]; then
  say "หยุด: หาเซสชันเดสก์ท็อปไม่เจอ · เลือกจากรายการนี้แล้วรันใหม่ด้วย --session \"Exec ของตัวที่เลือก\":"
  grep -H '^Exec=' /usr/share/wayland-sessions/*.desktop 2>/dev/null || say "  (ไม่มีไฟล์ใน /usr/share/wayland-sessions)"
  exit 1
fi
case "$SESSION" in *\"*|*\'*) say "หยุด: คำสั่งเซสชันมีเครื่องหมายคำพูด ใส่ใน config ไม่ได้อย่างปลอดภัย"; exit 1 ;; esac
say "เซสชันหลังเข้าได้: $SESSION"

# ---------- ยืนยันทางเข้าสำรองก่อนเริ่มทำอะไร ----------
if [ "$MODE" = "apply" ]; then
  say ""
  say "ก่อนเปลี่ยนหน้า login: เคยลองกด Ctrl+Alt+F2 แล้ว login ในหน้าจอตัวหนังสือได้ใช่ไหม"
  say "(ถ้าหน้า Login ใหม่มีปัญหา จะใช้ทางนี้เข้าไปรัน --rollback)"
  read -r -p "พิมพ์ YES ถ้าใช่: " ANSWER
  [ "$ANSWER" = "YES" ] || { say "ยกเลิก · ยังไม่ได้เปลี่ยนอะไร"; exit 1; }
fi

# ---------- 1. แพ็กเกจ ----------
say ""; say "1) greetd + cage"
MISSING=()
command -v greetd >/dev/null || MISSING+=(greetd)
command -v cage >/dev/null || MISSING+=(cage)
if [ "${#MISSING[@]}" -gt 0 ]; then do_ apt-get install -y "${MISSING[@]}"; else say "   มีครบแล้ว"; fi
# แพ็กเกจ greetd อาจเปิดตัวเองตอนติดตั้ง → คืนให้ lightdm เป็นหน้า login ไว้ก่อนจนถึงขั้นที่ 4
# (ถ้าขั้น 2–3 พังกลางทาง เครื่องยังบูตเข้าหน้า login เดิมได้ ไม่ใช่ greetd ที่ยังไม่ได้ตั้งค่า)
if [ "$MODE" = "apply" ]; then
  systemctl disable greetd 2>/dev/null || true
  systemctl enable lightdm
fi

# ---------- 2. แอปที่ /opt/aipc-v2 ----------
say ""; say "2) คัดลอกแอป (เฉพาะไฟล์ที่ commit แล้ว: $(git -C "$SRC" rev-parse --short HEAD)) ไปที่ $DEST"
if [ -e "$DEST" ]; then do_ mv "$DEST" "$DEST.prev-$STAMP"; fi
do_ mkdir -p "$DEST"
if [ "$MODE" = "apply" ]; then
  say "+ git archive HEAD | tar -x -C $DEST"
  git -C "$SRC" archive HEAD | tar -x -C "$DEST"
else
  say "[จะทำ] git archive HEAD | tar -x -C $DEST"
fi
do_ python3 -m venv "$DEST/.venv"
do_ "$DEST/.venv/bin/pip" install --no-cache-dir "$DEST[ui,vision]"
# โมเดลใบหน้า SFace (37 MB · การ์ด 0006) เก็บกลางที่ $DEST/models ให้ทุกบัญชีใช้ร่วม · ตรวจ sha256 ก่อนใช้
do_ env AIPC_MODEL_DIR="$DEST/models" "$DEST/.venv/bin/python" -m aipc.vision.models fetch
do_ chown -R root:root "$DEST"
do_ chmod -R go-w,a+rX "$DEST"

# ---------- 3. config ของ greetd ----------
CMD="cage -s -- $DEST/.venv/bin/python -m aipc.ui --fullscreen --greeter '$SESSION'"
NEW="[terminal]
vt = 7

[default_session]
command = \"$CMD\"
user = \"_greetd\""
say ""; say "3) $CONF"
printf '%s\n' "$NEW" | sed 's/^/   /'

# ---------- ยืนยันทางเข้าสำรองก่อนเปลี่ยนหน้า login ----------
if [ "$MODE" = "apply" ]; then
  getent passwd _greetd >/dev/null || { say "หยุด: ไม่มีผู้ใช้ _greetd (แพ็กเกจ greetd ควรสร้างให้)"; exit 1; }
  [ -f "$CONF" ] && cp -a "$CONF" "$CONF.before-aipc-$STAMP" && say "+ สำรอง $CONF.before-aipc-$STAMP"
  mkdir -p "$(dirname "$CONF")"
  printf '%s\n' "$NEW" > "$CONF"
  say "+ เขียน $CONF"
fi

# ---------- 4. สลับตัวจัดการหน้า login ----------
say ""; say "4) ปิด lightdm เปิด greetd (มีผลหลังรีบูต)"
if [ "$MODE" = "apply" ]; then
  systemctl disable lightdm || true
  if ! systemctl enable greetd; then
    say "เปิด greetd ไม่ได้ → เปิด lightdm คืนให้ทันที"
    systemctl enable lightdm
    exit 1
  fi
  say ""
  say "เสร็จ · รีบูตด้วย: sudo reboot"
  say "ถ้าหน้า Login ใหม่ไม่ขึ้น: Ctrl+Alt+F2 → login → sudo $SRC/scripts/pi/install-greeter.sh --rollback → sudo reboot"
else
  say "[จะทำ] systemctl disable lightdm && systemctl enable greetd"
  say ""
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-greeter.sh --apply"
fi
