#!/usr/bin/env bash
# ตรวจว่าระบบเก่า ("D:\ai computer" และ "D:\ai-pc-2") ยังติดตั้งอะไรไว้บน Pi บ้าง · **อ่านอย่างเดียว**
#
#   ./scripts/pi/check-old-system.sh
#
# ไม่เปลี่ยน ไม่ลบ ไม่ใช้ sudo · ผลเขียนลง ~/aipc-old-system-report.txt ด้วย เพื่อส่งกลับมาให้ดู
# รายการที่ตรวจมาจากเอกสารของ repo เก่า (deploy/greetd, deploy/pam, deploy/kiosk, docs/operations.md,
# scripts/aipc-homes.sh) · ของที่เอกสารบอกว่าอยู่บนบอร์ดเท่านั้น ต้องเห็นของจริงก่อนตัดสินว่าจะเอาออกยังไง
set -uo pipefail

OUT="$HOME/aipc-old-system-report.txt"
exec > >(tee "$OUT") 2>&1

h() { printf '\n===== %s =====\n' "$*"; }
show() {  # แสดงไฟล์ถ้ามี (อ่านได้โดยไม่ต้อง sudo)
  if [ -e "$1" ]; then
    printf -- '--- %s (%s)\n' "$1" "$(stat -c '%U:%G %a %y' "$1" 2>/dev/null)"
    if [ -r "$1" ] && [ -f "$1" ]; then cat "$1"; elif [ -d "$1" ]; then ls -la "$1"; else echo "(อ่านไม่ได้)"; fi
  else
    printf -- '--- %s : ไม่มี\n' "$1"
  fi
}
unit() { printf '%-32s enabled=%-10s active=%s\n' "$1" "$(systemctl is-enabled "$1" 2>&1)" "$(systemctl is-active "$1" 2>&1)"; }

h "เครื่อง"
date -Is; uname -a; cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|VERSION_CODENAME)='
python3 -c 'import os; print("glibc", os.confstr("CS_GNU_LIBC_VERSION"))' 2>/dev/null
echo "ผู้ใช้: $(id)"

h "ตัวจัดการหน้า login (display manager)"
for u in greetd lightdm display-manager ai-pc-control ai-pc-ui ai-pc-recovery; do unit "$u"; done
ls -la /etc/systemd/system/display-manager.service 2>&1
echo "user units:"; systemctl --user list-unit-files 'ai-pc*' 2>&1 | head -20
loginctl show-user "$USER" -p Linger 2>&1

h "greetd"
show /etc/greetd/config.toml
show /etc/greetd/config.toml.packaged
ls -la /etc/greetd/ 2>&1

h "PAM (ของระบบเก่าแก้ /etc/pam.d/greetd)"
show /etc/pam.d/greetd
show /etc/pam.d/greetd.before-006
show /etc/pam.d/greetd-greeter
show /etc/pam.d/ai-pc-face-test
ls -la /etc/pam.d/ | grep -Ei 'greet|ai-pc|login' 2>&1

h "lightdm (บรรทัดที่ระบบเก่าตั้ง autologin)"
grep -nE '^\s*(greeter-session|user-session|autologin-user|autologin-session)\s*=' /etc/lightdm/lightdm.conf 2>&1

h "ไฟล์ของระบบเก่า"
ls -la /usr/local/bin/ | grep -Ei 'ai-pc|whisper|llama' 2>&1
show /usr/share/wayland-sessions/ai-pc.desktop
show /usr/local/share/ai-pc/REVERT.txt
show /etc/systemd/system/ai-pc-control.service
show "$HOME/.config/systemd/user/ai-pc-remote-screen.service"
ls -la /opt/ 2>&1
ls -la /opt/ai-pc /opt/ai-pc/releases 2>&1
show /opt/ai-pc/current
du -sh /opt/ai-pc /opt/ai-pc-runtime /var/lib/ai-pc 2>&1

h "ของ ai-pc-2 (บ้านเข้ารหัส)"
grep -n 'aipc' /etc/fstab 2>&1
findmnt /srv/aipc/home 2>&1
ls -la /var/lib/aipc 2>&1
show /etc/fscrypt.conf
getent passwd usera userb pamcheck006 2>&1

h "repo เก่าใน home"
ls -d "$HOME"/ai-pc "$HOME"/ai-pc-2 "$HOME"/aipc "$HOME"/llama.cpp "$HOME"/whisper.cpp 2>&1
du -sh "$HOME"/ai-pc "$HOME"/ai-pc-2 2>&1

h "ทางเข้าสำรอง (ต้องมีก่อนเปลี่ยนหน้า login)"
unit ssh
echo "คอนโซลข้อความ: กด Ctrl+Alt+F2 ที่หน้าจอ Pi แล้ว login ด้วยชื่อ/รหัสผ่านได้ไหม → ตอบเองด้วยมือ"

h "เสร็จ"
echo "ไม่ได้เปลี่ยนอะไรในเครื่อง · ส่งไฟล์ $OUT กลับมา"
