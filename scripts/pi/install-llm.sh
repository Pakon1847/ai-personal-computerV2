#!/usr/bin/env bash
# ติดตั้ง AI ในเครื่อง (การ์ด 0013): llama-server + ไฟล์โมเดล + user service ให้ทุกบัญชีใช้ร่วมกัน
#
#   ./scripts/pi/install-llm.sh --model <ไฟล์.gguf> [--threads 4] [--llama ~/llama.cpp]   ดูว่าจะทำอะไร
#   sudo ./scripts/pi/install-llm.sh --apply --model <ไฟล์.gguf> [...]                      ทำจริง
#   sudo ./scripts/pi/install-llm.sh --rollback                                                 ถอด (ไม่ลบโมเดล)
#
# ทำอะไร:
#   1. คัด llama-server ที่ build บนเครื่องนี้ (ไฟล์โปรแกรม + .so) ไป /opt/aipc-llm (root · อ่านได้ทุกคน)
#   2. คัดไฟล์โมเดลไป /opt/aipc-models (root 0644) · แสดง sha256 ให้จดลงผลวัด
#   3. /etc/aipc/llm.conf (MODEL THREADS CTX) · /etc/systemd/user/aipc-llm.service
#   (KillUserProcesses=yes อยู่ใน install-accounts.sh · เป็นเรื่องแยกบัญชี ไม่ได้ผูกกับ AI)
# ไม่แตะ: greetd, PAM, logind, ไฟล์บูต, พาร์ทิชัน · ไม่รีบูต
# เปลี่ยนโมเดล = รันใหม่ด้วย --model อื่น แล้วออกจากระบบ-เข้าใหม่
set -euo pipefail

MODE="dry-run"; MODEL=""; THREADS=4; LLAMA="${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}/llama.cpp"
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) MODE="apply" ;;
    --rollback) MODE="rollback" ;;
    --model) MODEL="${2:?}"; shift ;;
    --threads) THREADS="${2:?}"; shift ;;
    --llama) LLAMA="${2:?}"; shift ;;
    *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
  esac
  shift
done
[ "$LLAMA" = "/llama.cpp" ] && LLAMA="$HOME/llama.cpp"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPT=/opt/aipc-llm
MODELS=/opt/aipc-models
CONF=/etc/aipc/llm.conf
UNIT=/etc/systemd/user/aipc-llm.service
say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

if [ "$MODE" = "rollback" ]; then
  need_root
  rm -f "$UNIT" "$CONF"
  rm -rf "$OPT"
  say "เสร็จ · ถอด llama-server, ค่าตั้ง และ user service แล้ว · โมเดลใน $MODELS ยังอยู่ (ลบเองได้)"
  exit 0
fi

[ -n "$MODEL" ] || { say "หยุด: ต้องบอก --model <ไฟล์.gguf>" >&2; exit 2; }
[ -f "$MODEL" ] || { say "หยุด: ไม่มีไฟล์ $MODEL" >&2; exit 1; }
BIN="$LLAMA/build/bin"
[ -x "$BIN/llama-server" ] || { say "หยุด: ไม่มี $BIN/llama-server (build llama.cpp ก่อน · runbook ตั้ง Pi 5 ขั้น 5)" >&2; exit 1; }
"$BIN/llama-server" --help 2>/dev/null | grep -q "\.sock" \
  || { say "หยุด: llama-server รุ่นนี้ไม่รองรับ Unix socket (ADR-008)" >&2; exit 1; }
NAME="$(basename "$MODEL")"
say "llama.cpp: $(git -C "$LLAMA" rev-parse --short HEAD 2>/dev/null || echo ไม่รู้ commit) · โมเดล: $NAME · threads $THREADS"
[ "$MODE" = "apply" ] || { say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="; }
[ "$MODE" = "apply" ] && need_root

run() { if [ "$MODE" = "apply" ]; then say "+ $*"; "$@"; else say "[จะทำ] $*"; fi; }

say ""; say "1) llama-server → $OPT"
run install -d -o root -g root -m 0755 "$OPT/bin" "$OPT/lib"
run install -o root -g root -m 0755 "$BIN/llama-server" "$OPT/bin/llama-server"
for so in "$BIN"/*.so*; do
  [ -e "$so" ] || continue
  run cp -a "$so" "$OPT/lib/"
done
run chown -R root:root "$OPT"

say ""; say "2) โมเดล → $MODELS/$NAME"
run install -d -o root -g root -m 0755 "$MODELS"
run install -o root -g root -m 0644 "$MODEL" "$MODELS/$NAME"
say "   sha256: $(sha256sum "$MODEL" | cut -d' ' -f1)"

say ""; say "3) $CONF และ $UNIT"
CONF_TEXT="# ค่าตั้ง AI ในเครื่อง (การ์ด 0013) · แก้แล้วให้ผู้ใช้ออกจากระบบ-เข้าใหม่
MODEL=$MODELS/$NAME
THREADS=$THREADS
CTX=4096"
if [ "$MODE" = "apply" ]; then
  install -d -m 0755 "$(dirname "$CONF")" "$(dirname "$UNIT")"
  printf '%s\n' "$CONF_TEXT" > "$CONF" && chmod 0644 "$CONF" && say "+ เขียน $CONF"
  install -o root -g root -m 0644 "$SRC/scripts/pi/session/aipc-llm.service" "$UNIT" && say "+ เขียน $UNIT"
else
  printf '%s\n' "$CONF_TEXT" | sed 's/^/   /'
  say "[จะคัด] $SRC/scripts/pi/session/aipc-llm.service → $UNIT"
fi

say ""
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ออกจากระบบแล้วเข้าใหม่ AI จะเริ่มเอง · ตรวจ: systemctl --user status aipc-llm"
  say "ต้องอัปเดตแอปด้วย update-app.sh ให้มี scripts/pi/session/aipc-llm-start ก่อน"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-llm.sh --apply --model $MODEL"
fi
