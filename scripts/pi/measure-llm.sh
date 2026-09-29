#!/bin/sh
# วัด LLM 1 ตัวบน Pi 5 ตาม runbook ขั้น 7 + 7.1 + ชุดเลือกสกิล (ADR-007 ข้อ 1–6) · commit ผลทีละขั้น
#   ./scripts/pi/measure-llm.sh <ไฟล์ใน models/> <label> <ชั้น: 3-4b | 1b>
#   STEPS="4" ./scripts/pi/measure-llm.sh ...   วัดเฉพาะบางขั้น (ค่าเริ่มต้น "1 3 4")
# ไม่แตะหน้า Login, ไฟล์บูต หรือ service ของระบบ · ใช้ llama-server แบบ TCP 127.0.0.1 ชั่วคราวแล้วปิด
# commit หลังทุกขั้น เพราะเครื่องมือวัดไม่นับเป็นระดับ 4 ถ้ามีไฟล์ค้างแก้
# chat template: ใช้ scripts/pi/chat-templates/<ชื่อโมเดล>.jinja ถ้ามี (เหมือน install-llm.sh · ตัวใน GGUF บางตัวไม่มี tool calling)
set -eu
M="${1:?ไฟล์โมเดล}"; LABEL="${2:?label}"; SIZE="${3:?ชั้น 3-4b หรือ 1b}"
STEPS="${STEPS:-1 3 4}"
cd "$(dirname "$0")/../.."
B="$HOME/llama.cpp/build/bin"
L="$(git -C "$HOME/llama.cpp" rev-parse --short HEAD)"
DAY="$(date +%F)"
PY=./.venv/bin/python
[ -f "models/$M" ] || { echo "หยุด: ไม่มี models/$M"; exit 1; }
commit() { git add docs/benchmarks && git commit -q -m "$1" && echo "+ commit: $1"; }
has() { case " $STEPS " in *" $1 "*) return 0 ;; esac; return 1; }
TPL="scripts/pi/chat-templates/${M%.gguf}.jinja"

if has 1; then
  echo "== 1) ความเร็ว threads 4 และ 3 (llama-bench)"
  for t in 4 3; do
    sfx=""; [ "$t" = 3 ] && sfx="-t3"
    $PY -m aipc.spikes.llm --bench "$B/llama-bench" --model "models/$M" --label "$LABEL$sfx" --size "$SIZE" \
        --threads "$t" --meta "llama_cpp=$L" | tail -4
    commit "bench(pi5): llm $LABEL threads $t"
  done
fi
has 3 || has 4 || { echo "เสร็จ: $LABEL"; exit 0; }

echo "== 2) เปิด llama-server ชั่วคราว (127.0.0.1:8080 · --jinja เป็นค่าเริ่มต้น = tool calling · -fa off เหมือนแอป)"
if [ -f "$TPL" ]; then
  echo "   chat template: $TPL"
  "$B/llama-server" -m "models/$M" --chat-template-file "$TPL" --host 127.0.0.1 --port 8080 -c 4096 -t 4 \
      -fa off --no-webui > "/tmp/llama-$LABEL.log" 2>&1 &
else
  echo "   chat template: ตัวที่ฝังใน GGUF"
  "$B/llama-server" -m "models/$M" --host 127.0.0.1 --port 8080 -c 4096 -t 4 -fa off --no-webui \
      > "/tmp/llama-$LABEL.log" 2>&1 &
fi
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && break
  sleep 2
done
curl -sf http://127.0.0.1:8080/health >/dev/null || { echo "หยุด: llama-server ไม่พร้อม"; tail -20 "/tmp/llama-$LABEL.log"; exit 1; }
echo "   พร้อมหลัง ~$((i * 2)) วิ (รวมโหลดโมเดลจาก microSD)"

if has 3; then
  echo "== 3) คำตอบคำถามไทย 30 ข้อ (ADR-007 ข้อ 1 · ให้คนให้คะแนนทีหลัง)"
  $PY -m aipc.spikes.llm_quality ask --label "$LABEL" --out "docs/benchmarks/$DAY-llm-thai/$LABEL.json" | tail -3
  commit "bench(pi5): คำตอบไทย 30 ข้อ $LABEL"
fi

if has 4; then
  echo "== 4) เลือกสกิล (ADR-007 ข้อ 6) · 2 แบบ: กฎก่อน (แอปตอนนี้) และ AI ก่อน · หยุดเองถ้า server ไม่รับรายการเครื่องมือ"
  for mode in rules-first ai-first; do
    $PY -m aipc.spikes.skill_select --label "$LABEL" --server http://127.0.0.1:8080 --mode "$mode" \
        --out "docs/benchmarks/$DAY-skill-select-pi5/$LABEL-$mode.json"
  done
  # RAM ของ llama-server หลังใช้งานจริง (ctx 4096 · ADR-007 ข้อ 4) · VmHWM = สูงสุดตั้งแต่เริ่ม · รวมหน้าไฟล์โมเดลที่ mmap
  {
    echo "label=$LABEL model=$M ctx=4096 threads=4 llama_cpp=$L template=$( [ -f "$TPL" ] && echo "$TPL" || echo gguf)"
    grep -E "VmHWM|VmRSS|RssAnon|RssFile" "/proc/$PID/status"
    free -m
  } > "docs/benchmarks/$DAY-skill-select-pi5/$LABEL-server-ram.txt"
  commit "bench(pi5): เลือกสกิล $LABEL (กฎก่อน + AI ก่อน) + RAM ของ llama-server"
fi
echo "เสร็จ: $LABEL"
