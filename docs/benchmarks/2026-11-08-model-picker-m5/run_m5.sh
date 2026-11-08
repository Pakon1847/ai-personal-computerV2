#!/bin/sh
# M5 (การ์ด 0076): S2a รอบ 2 ของการ์ด 0074 กับโมเดลใหม่ 2 ตัว · โค้ดชุดเดียวกับ Gemma รอบ 2 (32ee013)
# วางไว้ที่ scripts/bench/ ของ checkout ~/aipc-0074r2 บน Pi (ไม่ commit ที่นั่น) แล้วเรียก:
#   M=/opt/aipc-models/Qwen3.5-2B-Q4_K_M.gguf OUT=<โฟลเดอร์ผล> sh scripts/bench/run_m5.sh
# ต่างจาก run_skill_guard.sh (32ee013) แค่ 2 อย่าง: M = ไฟล์โมเดล (แทน MODEL ใน /etc/aipc/llm.conf · template ว่าง = ตัวใน GGUF
#   แบบเดียวกับ llm-compare และ llm-models.conf) · OUT = โฟลเดอร์ผล · ไม่แตะ /etc
set -u
: "${M:?ต้องบอก M=<ไฟล์โมเดล>}" "${OUT:?ต้องบอก OUT=<โฟลเดอร์ผล>}"
cd "$(dirname "$0")/../.."
src=scripts/bench/run_skill_guard.sh
tmp=$(mktemp)
sed -e 's#^\. /etc/aipc/llm.conf$#. /etc/aipc/llm.conf; MODEL="$M"; TEMPLATE=""#' \
    -e 's#^PY=#O="$OUT"; PY=#' "$src" > "$tmp"
grep -q 'MODEL="$M"' "$tmp" && grep -q 'O="$OUT"' "$tmp" || { echo "แก้ตัวรันไม่สำเร็จ (โค้ดไม่ตรงที่คาด)"; exit 1; }
# ตัวรันใช้ dirname $0 → ต้องอยู่ใน scripts/bench
cp "$tmp" scripts/bench/.run_m5_inner.sh; rm -f "$tmp"
R=r2 sh scripts/bench/.run_m5_inner.sh s2a-user0 s2a-user50
rc=$?
rm -f scripts/bench/.run_m5_inner.sh
exit $rc
