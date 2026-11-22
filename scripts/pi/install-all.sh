#!/usr/bin/env bash
# ตัวติดตั้งรวม (การ์ด 0077): Raspberry Pi OS ที่ลงใหม่ → เครื่องผู้ช่วย AI ครบ ในคำสั่งเดียว
# ใช้กับ Pi 5 8GB · ต้องมี repo นี้ในเครื่องแล้ว (git clone หรือคัดจาก USB) · ต้องใช้อินเทอร์เน็ต (apt · โหลดโมเดล)
#
#   ./scripts/pi/install-all.sh                 ดูว่าจะทำอะไร + ตรวจเครื่อง (ไม่เปลี่ยนอะไรเลย)
#   sudo ./scripts/pi/install-all.sh --apply    ทำจริงทีละขั้น · ขั้นไหนไม่ผ่าน = หยุดทันที บอกว่าทำถึงไหน
#   sudo ./scripts/pi/install-all.sh --apply    (รันซ้ำ) ข้ามขั้นที่เสร็จแล้ว ทำต่อจากขั้นที่หยุด
#
# ไม่ได้ทำเอง: แต่ละขั้นเรียกสคริปต์ install-*.sh เดิมที่ใช้ติดตั้งเครื่องจริงมาแล้ว (ลำดับตาม runbook pi5-setup.md ข้อ 9)
#   ตัวนี้แค่เรียงลำดับ · ตรวจก่อนเริ่ม · จดว่าขั้นไหนเสร็จ · หยุดเมื่อพัง
# ขั้นที่ถามผู้ใช้: หน้า Login (install-greeter.sh ถามให้พิมพ์ YES เรื่องทางเข้าสำรอง)
# จดความคืบหน้า: /var/lib/aipc/install-all.done (ชื่อขั้นละบรรทัด) · ลบไฟล์นี้ = เริ่มนับใหม่ (สคริปต์ย่อยรันซ้ำได้อยู่แล้ว)
# ไม่แตะ: ไฟล์บูต · พาร์ทิชัน · บัญชีผู้ใช้ที่มีอยู่ · ไม่รีบูตเอง (บอกให้รีบูตตอนจบ)
# ไม่รองรับ: Windows / Mac / พีซี Linux ทั่วไป (หน้าเข้าสู่ระบบผูกกับ greetd + PAM + labwc ของ Pi OS)
set -euo pipefail

MODE="dry-run"
case "${1:-}" in
  "") ;;
  --apply) MODE="apply" ;;
  *) echo "ไม่รู้จัก: $1 (ใช้ได้: --apply)" >&2; exit 2 ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
STATE_DIR="${AIPC_STATE_DIR:-/var/lib/aipc}"
DONE="$STATE_DIR/install-all.done"
BUILD="${AIPC_BUILD_DIR:-/var/cache/aipc-build}"
MIN_FREE_GB=15

# llama.cpp commit เดียวกับที่ใช้วัดผลทั้งหมดบน Pi 5 (git -C ~/llama.cpp rev-parse --short HEAD · 2026-11-07)
LLAMA_REPO=https://github.com/ggml-org/llama.cpp
LLAMA_COMMIT=86ea01d
# โมเดลเริ่มต้น (ADR-007) · ไลเซนส์ Apache-2.0 (ADR-014) · sha256 = ไฟล์ที่ใช้วัดผลบน Pi 5 (ตรวจ 2026-11-07)
MODEL_REPO=unsloth/gemma-4-E2B-it-GGUF
MODEL_FILE=gemma-4-E2B-it-Q4_K_M.gguf
MODEL_SHA256=740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8

say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }
done_() { [ -f "$DONE" ] && grep -qx "$1" "$DONE"; }
mark() { mkdir -p "$STATE_DIR"; echo "$1" >> "$DONE"; }

# ---------- ขั้นตอน (ชื่อ · คำอธิบาย) ตามลำดับ ----------
STEPS=(
  "llama|สร้าง llama.cpp ($LLAMA_COMMIT) ที่ $BUILD/llama.cpp (apt: git cmake build-essential libcurl4-openssl-dev)"
  "model|โหลดโมเดล $MODEL_FILE (~3.1 GB) จาก $MODEL_REPO แล้วตรวจ sha256"
  "greeter|หน้า Login ของ V2 เป็นหน้าเข้าเครื่องจริง (install-greeter.sh --session v2 · ถาม YES)"
  "app|ย้ายแอปเข้าโครงสร้างรุ่น + โหลดโมเดลใบหน้า (update-app.sh)"
  "accounts|สมัคร/กู้คืนที่หน้า Login + ปิด autologin (install-accounts.sh)"
  "llm|AI ในเครื่อง: llama-server + โมเดล + service (install-llm.sh)"
  "voice|เสียงอ่านภาษาไทย (install-voice.sh)"
  "visiond|สแกนหน้าที่หน้า Login (install-visiond.sh)"
  "lockscreen|จอล็อกปลดด้วยใบหน้า (apt: gtklock · install-lockscreen.sh)"
  "browser|Chromium ไม่ถามรหัส keyring (install-browser.sh)"
  "wifi|ทุกบัญชีเลือก Wi-Fi ได้ (install-wifi-access.sh)"
  "apps|ตัวติดตั้งแอปจากรายการที่อนุญาต (install-apps.sh)"
)

run_step() {
  local llama="$BUILD/llama.cpp" model="$BUILD/models/$MODEL_FILE"
  case "$1" in
    llama)
      apt-get install -y git cmake build-essential libcurl4-openssl-dev
      [ -d "$llama/.git" ] || git clone "$LLAMA_REPO" "$llama"
      git -C "$llama" fetch --quiet origin && git -C "$llama" checkout --quiet "$LLAMA_COMMIT"
      cmake -S "$llama" -B "$llama/build" -DCMAKE_BUILD_TYPE=Release
      cmake --build "$llama/build" --config Release -j4
      [ -x "$llama/build/bin/llama-server" ] ;;
    model)
      mkdir -p "$BUILD/models"
      curl -L --fail -C - -o "$model" "https://huggingface.co/$MODEL_REPO/resolve/main/$MODEL_FILE"
      local got; got="$(sha256sum "$model" | cut -d' ' -f1)"
      if [ "$got" != "$MODEL_SHA256" ]; then
        say "sha256 ไม่ตรง (ได้ $got) · ลบไฟล์แล้ว · รันใหม่เพื่อโหลดอีกครั้ง"; rm -f "$model"; return 1
      fi ;;
    greeter) "$HERE/install-greeter.sh" --apply --session v2 ;;
    app) "$HERE/update-app.sh" --apply ;;
    accounts) "$HERE/install-accounts.sh" --apply ;;
    llm) "$HERE/install-llm.sh" --apply --model "$model" --threads 3 --llama "$llama" ;;
    voice) "$HERE/install-voice.sh" --apply ;;
    visiond) "$HERE/install-visiond.sh" --apply ;;
    lockscreen)
      apt-get install -y gtklock gtklock-playerctl-module playerctl
      "$HERE/install-lockscreen.sh" --apply ;;
    browser) "$HERE/install-browser.sh" --apply ;;
    wifi) "$HERE/install-wifi-access.sh" --apply ;;
    apps) "$HERE/install-apps.sh" --apply ;;
    *) say "ไม่รู้จักขั้น $1"; return 1 ;;
  esac
}

# ---------- ตรวจเครื่องก่อนเริ่ม (ทั้งสองโหมด) ----------
say "== ตัวติดตั้งรวม · โหมด: $MODE · repo: $REPO =="
PROBLEMS=0
model_name="ไม่รู้"
[ -r /proc/device-tree/model ] && model_name="$(tr -d '\0' < /proc/device-tree/model)"
case "$model_name" in
  *"Raspberry Pi 5"*) say "เครื่อง: $model_name" ;;
  *) say "เตือน: เครื่องนี้คือ \"$model_name\" · ทดสอบแล้วบน Pi 5 8GB เท่านั้น (Pi 4 ใช้ตรวจความถูกต้องได้ แต่ช้า)" ;;
esac
[ "$(uname -m)" = "aarch64" ] || { say "หยุด: ต้องเป็น ARM 64 บิต (ได้ $(uname -m))"; PROBLEMS=1; }
mem_gb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0) / 1024 / 1024 ))
[ "$mem_gb" -ge 7 ] || say "เตือน: RAM ${mem_gb} GB · ออกแบบไว้สำหรับ 8 GB (AI ในเครื่องใช้ ~4.5 GB)"
free_gb=$(( $(df -Pk "$REPO" | awk 'NR==2 {print $4}') / 1024 / 1024 ))
if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then say "หยุด: ดิสก์ว่าง ${free_gb} GB · ต้องมีอย่างน้อย ${MIN_FREE_GB} GB"; PROBLEMS=1
else say "ดิสก์ว่าง: ${free_gb} GB"; fi
[ -f "$REPO/pyproject.toml" ] || { say "หยุด: ไม่พบ repo ของโปรเจกต์ที่ $REPO"; PROBLEMS=1; }

say ""
say "ขั้นตอน:"
n=0
for s in "${STEPS[@]}"; do
  n=$((n + 1)); name="${s%%|*}"
  if done_ "$name"; then say "  $n. [เสร็จแล้ว] ${s#*|}"; else say "  $n. ${s#*|}"; fi
done

if [ "$MODE" != "apply" ]; then
  say ""
  if [ "$PROBLEMS" -ne 0 ]; then say "ยังติดตั้งไม่ได้: แก้ข้อที่ขึ้นว่า \"หยุด\" ก่อน"; exit 1; fi
  say "ถ้าถูกต้อง: sudo $0 --apply"
  exit 0
fi

need_root
[ "$PROBLEMS" -eq 0 ] || { say "หยุด: แก้ข้อที่ขึ้นว่า \"หยุด\" ก่อน · ยังไม่ได้เปลี่ยนอะไร"; exit 1; }
n=0
for s in "${STEPS[@]}"; do
  n=$((n + 1)); name="${s%%|*}"
  if done_ "$name"; then say ""; say "== $n/${#STEPS[@]} $name: เสร็จไปแล้ว · ข้าม"; continue; fi
  say ""; say "== $n/${#STEPS[@]} $name: ${s#*|}"
  # รันใน subshell นอก if: ใน if/|| bash ปิด set -e ทำให้คำสั่งกลางขั้นพังแล้วยังนับว่าผ่าน
  set +e
  (set -e; run_step "$name")
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    say ""
    say "หยุดที่ขั้น $n ($name) · ขั้นก่อนหน้าเสร็จแล้ว (จดไว้ใน $DONE)"
    say "แก้ตามข้อความด้านบน แล้วรันคำสั่งเดิมอีกครั้ง จะทำต่อจากขั้นนี้"
    exit 1
  fi
  mark "$name"
done
say ""
say "เสร็จครบ ${#STEPS[@]} ขั้น · รีบูต 1 ครั้ง (sudo reboot) แล้วสมัครบัญชีแรกที่หน้า Login"
