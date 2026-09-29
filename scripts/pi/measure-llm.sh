#!/bin/sh
# วัด LLM 1 ตัวบน Pi 5 ตาม runbook ขั้น 7 + 7.1 + ชุดเลือกสกิล (ADR-007 ข้อ 1–6) · commit ผลทีละขั้น
#   ./scripts/pi/measure-llm.sh <ไฟล์ใน models/> <label> <ชั้น: 3-4b | 1b>
# ไม่แตะหน้า Login, ไฟล์บูต หรือ service ของระบบ · ใช้ llama-server แบบ TCP 127.0.0.1 ชั่วคราวแล้วปิด
# commit หลังทุกขั้น เพราะเครื่องมือวัดไม่นับเป็นระดับ 4 ถ้ามีไฟล์ค้างแก้
set -eu
M="${1:?ไฟล์โมเดล}"; LABEL="${2:?label}"; SIZE="${3:?ชั้น 3-4b หรือ 1b}"
cd "$(dirname "$0")/../.."
B="$HOME/llama.cpp/build/bin"
L="$(git -C "$HOME/llama.cpp" rev-parse --short HEAD)"
DAY="$(date +%F)"
PY=./.venv/bin/python
[ -f "models/$M" ] || { echo "หยุด: ไม่มี models/$M"; exit 1; }
commit() { git add docs/benchmarks && git commit -q -m "$1" && echo "+ commit: $1"; }

echo "== 1) ความเร็ว threads 4 และ 3 (llama-bench)"
for t in 4 3; do
  sfx=""; [ "$t" = 3 ] && sfx="-t3"
  $PY -m aipc.spikes.llm --bench "$B/llama-bench" --model "models/$M" --label "$LABEL$sfx" --size "$SIZE" \
      --threads "$t" --meta "llama_cpp=$L" | tail -4
  commit "bench(pi5): llm $LABEL threads $t"
done

echo "== 2) เปิด llama-server ชั่วคราว (127.0.0.1:8080 · --jinja เป็นค่าเริ่มต้น = tool calling)"
"$B/llama-server" -m "models/$M" --host 127.0.0.1 --port 8080 -c 4096 -t 4 --no-webui > "/tmp/llama-$LABEL.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && break
  sleep 2
done
curl -sf http://127.0.0.1:8080/health >/dev/null || { echo "หยุด: llama-server ไม่พร้อม"; tail -20 "/tmp/llama-$LABEL.log"; exit 1; }
echo "   พร้อมหลัง ~$((i * 2)) วิ (รวมโหลดโมเดลจาก microSD)"

echo "== 3) คำตอบคำถามไทย 30 ข้อ (ADR-007 ข้อ 1 · ให้คนให้คะแนนทีหลัง)"
$PY -m aipc.spikes.llm_quality ask --label "$LABEL" --out "docs/benchmarks/$DAY-llm-thai/$LABEL.json" | tail -3
commit "bench(pi5): คำตอบไทย 30 ข้อ $LABEL"

echo "== 4) เลือกสกิล: กฎ + AI (ADR-007 ข้อ 6)"
$PY -m aipc.spikes.skill_select --label "$LABEL" --server http://127.0.0.1:8080 \
    --out "docs/benchmarks/$DAY-skill-select-pi5/$LABEL.json"
commit "bench(pi5): เลือกสกิล $LABEL"
echo "เสร็จ: $LABEL"
