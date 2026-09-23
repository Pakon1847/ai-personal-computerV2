#!/usr/bin/env bash
# ติดตั้งหน้าจอ V2 ให้เปิดเต็มจอเองหลังเข้าเดสก์ท็อปของ Raspberry Pi OS (แบบปลอดภัย · ย้อนกลับได้)
#
#   ./scripts/pi/install-ui.sh              ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   ./scripts/pi/install-ui.sh --apply      ทำจริง
#   ./scripts/pi/install-ui.sh --uninstall  เอาการเปิดเองออก (ลบไฟล์เดียวที่สร้าง)
#
# ขอบเขต: ไม่ใช้ sudo · ไม่แตะ /etc, ไฟล์บูต, พาร์ทิชัน, หน้า login ของ Raspberry Pi OS
# สิ่งที่สร้าง: .venv ใน repo นี้ และไฟล์ ~/.config/autostart/aipc-ui.desktop เท่านั้น
# ออกจากแอปเต็มจอ: Ctrl+Alt+Q (ใช้ได้ทุกหน้า)
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --uninstall) MODE="uninstall" ;;
  *) echo "ไม่รู้จัก: $1 (ใช้ --apply หรือ --uninstall)" >&2; exit 2 ;;
esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AUTOSTART="$HOME/.config/autostart/aipc-ui.desktop"
PY="$REPO/.venv/bin/python"
# --dev: หน้า Login ของ V2 ยังไม่ตรวจรหัสผ่านจริง นอกโหมดพัฒนาจึงเข้าไม่ได้ · มีแถบส้มบอกตลอด (H5)
EXEC="$PY -m aipc.ui --dev --fullscreen"

say() { printf '%s\n' "$*"; }
run() {
  if [ "$MODE" = "apply" ]; then say "+ $*"; "$@"; else say "[จะทำ] $*"; fi
}

if [ "$MODE" = "uninstall" ]; then
  if [ -f "$AUTOSTART" ]; then rm -v "$AUTOSTART"; else say "ไม่มี $AUTOSTART อยู่แล้ว"; fi
  say "เสร็จ · .venv ใน $REPO ยังอยู่ (ลบเองได้ถ้าไม่ใช้แล้ว)"
  exit 0
fi

# ---------- ตรวจก่อน ทำอะไรไม่ได้ก็หยุด ----------
ARCH="$(uname -m)"
GLIBC="$(python3 -c 'import os; f = getattr(os, "confstr", None); print(f("CS_GNU_LIBC_VERSION").split()[1] if f else "unknown")')"
say "เครื่อง: $ARCH · glibc $GLIBC · Python $(python3 -c 'import sys; print(sys.version.split()[0])')"
say "เซสชัน: ${XDG_SESSION_TYPE:-ไม่รู้} (${XDG_CURRENT_DESKTOP:-ไม่รู้})"

# PySide6 จาก pip บน aarch64 ต้องใช้ glibc >= 2.39 (pyproject.toml, BRIEF หัวข้อ 2)
if [ "$ARCH" = "aarch64" ] && [ "$GLIBC" = "unknown" ]; then
  say "หยุด: อ่านรุ่น glibc ไม่ได้ · ส่งผลของ ldd --version มาก่อน"
  exit 1
fi
if [ "$ARCH" = "aarch64" ] && ! python3 - "$GLIBC" <<'EOF'
import sys
major, minor = (int(x) for x in sys.argv[1].split(".")[:2])
sys.exit(0 if (major, minor) >= (2, 39) else 1)
EOF
then
  say "หยุด: glibc $GLIBC ต่ำกว่า 2.39 → ติดตั้ง PySide6 จาก pip ไม่ได้"
  say "ทางแก้คือใช้ Raspberry Pi OS รุ่นใหม่ (Debian 13 trixie) · สคริปต์นี้ไม่เปลี่ยน OS ให้ ส่งผลนี้กลับมาก่อน"
  exit 1
fi

# ---------- ทำ ----------
if [ ! -x "$PY" ]; then
  run python3 -m venv "$REPO/.venv"
fi
run "$PY" -m pip install -e "$REPO[ui]"

say ""
say "ไฟล์เปิดเอง: $AUTOSTART"
DESKTOP="[Desktop Entry]
Type=Application
Name=AI PC (V2)
Comment=หน้าจอ AI PC V2 · ออกด้วย Ctrl+Alt+Q · เอาออกด้วย scripts/pi/install-ui.sh --uninstall
Exec=$EXEC
X-GNOME-Autostart-enabled=true"
if [ "$MODE" = "apply" ]; then
  mkdir -p "$(dirname "$AUTOSTART")"
  printf '%s\n' "$DESKTOP" > "$AUTOSTART"
  say "+ เขียนแล้ว"
else
  printf '%s\n' "$DESKTOP" | sed 's/^/[จะเขียน] /'
fi

say ""
if [ "$MODE" = "apply" ]; then
  say "ลองเปิดเองก่อนรีบูต:  $EXEC"
  say "ถ้าเปิดได้ รีบูตแล้วแอปควรขึ้นเองหลังเข้าเดสก์ท็อป · ถ้าไม่ขึ้น ส่งผลของ echo \$XDG_CURRENT_DESKTOP มา"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง รันอีกครั้งด้วย --apply"
fi
