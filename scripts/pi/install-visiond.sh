#!/usr/bin/env bash
# สแกนหน้าที่หน้า Login แล้วเข้าระบบได้เลย (การ์ด 0015 หัวข้อ 12 · Pakon ตัดสิน 2026-09-30)
# ใช้หลัง install-greeter.sh + update-app.sh + install-accounts.sh (ต้องมีแอปที่ /opt/aipc-v2 และตัวช่วย aipc-accounts)
#
#   ./scripts/pi/install-visiond.sh                  ดูว่าจะทำอะไร (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-visiond.sh --apply     ทำจริง
#   sudo ./scripts/pi/install-visiond.sh --rollback  เอาออกทั้งหมด · คืน /etc/pam.d/greetd เดิม
#
# ทำอะไร:
#   1. ผู้ใช้ระบบ _aipcvision (ไม่มี shell · กลุ่ม video = ใช้กล้องได้)
#   2. /etc/systemd/system/aipc-visiond.service · แม่แบบอยู่ /var/lib/aipc-vision (0700 ของ _aipcvision)
#      socket อยู่ /run/aipc-vision (systemd สร้างให้)
#   3. /usr/local/sbin/aipc-face-pass (root 0755) = ตัวที่ PAM เรียก ขอใช้ตั๋วจาก visiond
#   4. /etc/pam.d/aipc-face-check = pam_unix สำหรับตัวช่วย root ตรวจรหัสผ่านตอนเปิด/ปิดใบหน้า
#   5. /etc/sudoers.d/aipc-visiond = _aipcvision เรียก aipc-accounts ได้คำสั่งเดียว (ตัวช่วยยอมให้แค่ check-password)
#      **ตรวจด้วย visudo -c ก่อนติดตั้งเสมอ**
#   6. /etc/pam.d/greetd: เพิ่ม 2 บรรทัด (สำรองไฟล์เดิมก่อน):
#        auth    [success=done default=ignore] pam_exec.so quiet /usr/local/sbin/aipc-face-pass   (บรรทัดแรก)
#        session optional                      pam_exec.so quiet /usr/local/sbin/aipc-face-pass   (บรรทัดท้าย)
#      มีตั๋ว = เข้าได้เลย · ไม่มี/visiond ล่ม = ถามรหัสผ่านตามเดิม
# ไม่แตะ: PAM ของ sudo, sshd, login ของ OS (ใบหน้าใช้ได้ที่หน้า Login ของ greetd เท่านั้น) · ไม่รีบูต
# ทางเข้าสำรอง: SSH และ tty2 (Ctrl+Alt+F2) ใช้ได้ตามเดิม · ถ้าหน้า Login เข้าไม่ได้: --rollback
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  --rollback) MODE="rollback" ;;
  *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
esac

DEST=/opt/aipc-v2
USER_=_aipcvision
UNIT=/etc/systemd/system/aipc-visiond.service
PASS=/usr/local/sbin/aipc-face-pass
PAMCHECK=/etc/pam.d/aipc-face-check
SUDOERS=/etc/sudoers.d/aipc-visiond
PAMGREETD=/etc/pam.d/greetd
BACKUP=/var/lib/aipc/greetd.pam.before-visiond
MARK="aipc-face-pass"
AUTH_LINE="auth    [success=done default=ignore] pam_exec.so quiet $PASS"
SESSION_LINE="session optional                      pam_exec.so quiet $PASS"

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

UNIT_TEXT="# visiond: สแกนหน้าที่หน้า Login (aipc การ์ด 0015) · ติดตั้งโดย install-visiond.sh
[Unit]
Description=aipc visiond (สแกนหน้าเข้าเครื่อง)
After=systemd-udevd.service

[Service]
User=$USER_
Group=$USER_
SupplementaryGroups=video
Environment=AIPC_MODEL_DIR=$DEST/models
ExecStart=$DEST/.venv/bin/python -I -m aipc.vision.daemon
RuntimeDirectory=aipc-vision
RuntimeDirectoryMode=0755
StateDirectory=aipc-vision
StateDirectoryMode=0700
Restart=on-failure
RestartSec=3
# ปิดสิทธิ์ที่ไม่ต้องใช้ · ไม่ใส่ NoNewPrivileges เพราะต้องเรียก sudo ไปหาตัวช่วยตรวจรหัสผ่าน
# full (ไม่ใช่ strict): ตัวช่วย root ที่เรียกผ่าน sudo อยู่ใน namespace เดียวกัน และต้องเขียน /var/lib/aipc
ProtectSystem=full
ProtectHome=yes
PrivateTmp=yes
MemoryMax=600M

[Install]
WantedBy=multi-user.target"

PASS_TEXT="#!/bin/sh
# PAM ของหน้า Login เรียก (pam_exec) · ขอใช้ตั๋วใบหน้าจาก visiond (การ์ด 0015) · -I = โหลดโค้ดจาก $DEST เท่านั้น
exec $DEST/.venv/bin/python -I -m aipc.vision.face_pass"
PAMCHECK_TEXT="# ตัวช่วย root ตรวจรหัสผ่านก่อนเปิด/ปิดเข้าเครื่องด้วยใบหน้า (aipc การ์ด 0015)
auth    required pam_unix.so
account required pam_unix.so"
SUDOERS_TEXT="# visiond (ผู้ใช้ $USER_) ขอให้ตัวช่วย root ตรวจรหัสผ่าน · คำสั่งเดียว ห้ามใส่อาร์กิวเมนต์ (การ์ด 0015)
$USER_ ALL=(root) NOPASSWD: /usr/local/sbin/aipc-accounts \"\""

install_text() {  # install_text <ไฟล์ปลายทาง> <โหมด> <เนื้อหา>
  if [ "$MODE" != "apply" ]; then say "[จะเขียน] $1 ($2)"; printf '%s\n' "$3" | sed 's/^/   /'; return; fi
  install -d -m 0755 "$(dirname "$1")"
  local tmp; tmp="$(mktemp)"
  printf '%s\n' "$3" > "$tmp"
  install -o root -g root -m "$2" "$tmp" "$1"
  rm -f "$tmp"
  say "+ เขียน $1"
}

if [ "$MODE" = "rollback" ]; then
  need_root
  if [ -f "$BACKUP" ]; then
    install -o root -g root -m 0644 "$BACKUP" "$PAMGREETD" && say "+ คืน $PAMGREETD จาก $BACKUP"
  else
    sed -i "/$MARK/d" "$PAMGREETD" && say "+ เอาบรรทัด $MARK ออกจาก $PAMGREETD"
  fi
  systemctl disable --now aipc-visiond.service 2>/dev/null || true
  rm -f "$UNIT" "$PASS" "$PAMCHECK" "$SUDOERS"
  systemctl daemon-reload
  say "+ ลบ $UNIT $PASS $PAMCHECK $SUDOERS"
  say "เสร็จ · หน้า Login ใช้รหัสผ่านอย่างเดียว · ข้อมูลใบหน้าใน /var/lib/aipc-vision ยังอยู่ (ลบเอง: sudo rm -r /var/lib/aipc-vision)"
  exit 0
fi

[ "$MODE" = "apply" ] && need_root
[ "$MODE" = "apply" ] || say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร =="
[ -x "$DEST/.venv/bin/python" ] || { say "หยุด: ไม่มี $DEST/.venv · รัน install-greeter.sh ก่อน"; exit 1; }
[ -x /usr/local/sbin/aipc-accounts ] || { say "หยุด: ไม่มี aipc-accounts · รัน install-accounts.sh ก่อน"; exit 1; }
[ -f "$PAMGREETD" ] || { say "หยุด: ไม่มี $PAMGREETD (ติดตั้ง greetd ก่อน)"; exit 1; }
"$DEST/.venv/bin/python" -I -c "import aipc.vision.daemon, aipc.vision.face_pass" \
  || { say "หยุด: แอปใน $DEST ยังไม่มี visiond (update-app.sh --apply ก่อน)"; exit 1; }
[ -f "$DEST/models/face_recognition_sface_2021dec.onnx" ] \
  || { say "หยุด: ไม่มีโมเดลใบหน้าใน $DEST/models (update-app.sh โหลดให้)"; exit 1; }

say ""; say "1) ผู้ใช้ระบบ $USER_ (กลุ่ม video)"
if getent passwd "$USER_" >/dev/null; then
  say "   มีแล้ว"
elif [ "$MODE" = "apply" ]; then
  useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin --groups video "$USER_"
  say "+ สร้าง $USER_"
else
  say "[จะสร้าง] useradd --system --shell /usr/sbin/nologin --groups video $USER_"
fi

say ""; say "2) service $UNIT"
install_text "$UNIT" 0644 "$UNIT_TEXT"

say ""; say "3) $PASS"
install_text "$PASS" 0755 "$PASS_TEXT"

say ""; say "4) PAM ตรวจรหัสผ่าน $PAMCHECK"
install_text "$PAMCHECK" 0644 "$PAMCHECK_TEXT"

say ""; say "5) กฎ sudo $SUDOERS (ตรวจด้วย visudo ก่อน)"
if [ "$MODE" = "apply" ]; then
  TMP="$(mktemp)"
  printf '%s\n' "$SUDOERS_TEXT" > "$TMP"
  if ! visudo -cf "$TMP" >/dev/null; then
    rm -f "$TMP"; say "หยุด: กฎ sudo ไม่ผ่าน visudo · ไม่ได้ติดตั้ง"; exit 1
  fi
  install -o root -g root -m 0440 "$TMP" "$SUDOERS"
  rm -f "$TMP"
  visudo -c >/dev/null || { rm -f "$SUDOERS"; say "หยุด: sudoers ทั้งเครื่องไม่ผ่านหลังเพิ่ม → เอาออกแล้ว"; exit 1; }
  say "+ เขียน $SUDOERS"
else
  say "[จะเขียน] $SUDOERS (0440)"; printf '%s\n' "$SUDOERS_TEXT" | sed 's/^/   /'
fi

say ""; say "6) $PAMGREETD (สำรองไว้ที่ $BACKUP)"
if grep -q "$MARK" "$PAMGREETD"; then
  say "   มีบรรทัด $MARK แล้ว · ไม่เพิ่มซ้ำ"
elif [ "$MODE" = "apply" ]; then
  install -d -o root -g root -m 0700 "$(dirname "$BACKUP")"
  [ -f "$BACKUP" ] || cp -p "$PAMGREETD" "$BACKUP"
  TMP="$(mktemp)"
  # บรรทัดแรกของไฟล์ต้องเป็น #%PAM-1.0 ถ้ามี · ใส่บรรทัด auth ต่อจากนั้น
  awk -v a="$AUTH_LINE" 'NR==1 && /^#%PAM/ {print; print a; next} NR==1 {print a} {print}' "$PAMGREETD" > "$TMP"
  printf '%s\n' "$SESSION_LINE" >> "$TMP"
  install -o root -g root -m 0644 "$TMP" "$PAMGREETD"
  rm -f "$TMP"
  say "+ เพิ่มบรรทัด auth (ต้นไฟล์) และ session (ท้ายไฟล์)"
else
  say "[จะเพิ่ม] ต้นไฟล์: $AUTH_LINE"
  say "[จะเพิ่ม] ท้ายไฟล์: $SESSION_LINE"
fi

say ""; say "7) เปิด service"
if [ "$MODE" = "apply" ]; then
  systemctl daemon-reload
  systemctl enable --now aipc-visiond.service
  sleep 3
  if [ -S /run/aipc-vision/visiond.sock ]; then say "+ visiond พร้อม (/run/aipc-vision/visiond.sock)"
  else say "!! visiond ยังไม่ขึ้น · ดู: journalctl -u aipc-visiond -n 30 · หน้า Login ยังใช้รหัสผ่านได้"; fi
else
  say "[จะทำ] systemctl enable --now aipc-visiond.service"
fi

say ""
if [ "$MODE" = "apply" ]; then
  say "เสร็จ · ตรวจ: sudo -l -U $USER_ ต้องเห็นแค่ aipc-accounts · หน้า Login ใหม่: sudo systemctl restart greetd (เฉพาะตอนไม่มีใครใช้จอ) หรือรีบูต"
else
  say "ยังไม่ได้เปลี่ยนอะไร · ถ้าข้างบนถูกต้อง: sudo ./scripts/pi/install-visiond.sh --apply"
fi
