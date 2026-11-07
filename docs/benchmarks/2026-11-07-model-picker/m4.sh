#!/usr/bin/env bash
# M4 (การ์ด 0076): Qwen3.5 4B + Chromium 3 แท็บ 10 นาที → ไม่ถูก OOM kill
# ข้อจำกัด: ไม่มีคนเข้าจอตอนวัด → Chromium แบบ headless (ไม่มีหน้าต่าง/GPU compositor) · RAM อาจน้อยกว่าใช้งานจริง
# 2 รอบแรก (m4-invalid*.log) ส่ง URL 3 อันตอนเปิด → headless ไม่รับ ("Multiple targets are not supported in headless mode")
#   ปิดเองทันที = ไม่ได้วัด · รอบนี้: เปิด 1 ตัว แล้วเปิดแท็บผ่าน DevTools ที่ 127.0.0.1 ชั่วคราว (เบราว์เซอร์ 1 ตัว 3 แท็บ)
set -u
CHOICE="${XDG_CONFIG_HOME:-$HOME/.config}/aipc/llm-model"
SOCK="$XDG_RUNTIME_DIR/aipc/llm.sock"
BEFORE="$(cat "$CHOICE" 2>/dev/null || true)"
echo qwen3.5-4b > "$CHOICE"; systemctl --user restart aipc-llm
until curl -sf --unix-socket "$SOCK" http://x/health >/dev/null; do sleep 1; done
echo "model $(curl -s --unix-socket "$SOCK" http://x/v1/models | grep -o '"id":"[^"]*"' | head -1)"

P=$(mktemp -d)
DT=19333
chromium --headless=new --user-data-dir="$P" --no-first-run --remote-debugging-port=$DT about:blank >/dev/null 2>&1 &
until curl -sf "http://127.0.0.1:$DT/json/version" >/dev/null; do sleep 1; done
for u in https://www.youtube.com \
         https://th.wikipedia.org/wiki/%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B9%80%E0%B8%97%E0%B8%A8%E0%B9%84%E0%B8%97%E0%B8%A2 \
         https://news.google.com; do
  curl -sf -X PUT "http://127.0.0.1:$DT/json/new?$u" >/dev/null || echo "เปิดแท็บไม่ได้: $u"
done
tabs() { curl -s "http://127.0.0.1:$DT/json/list" | grep -c '"type": "page"'; }
procs() { pgrep -fc "[c]hrom.*user-data-dir=$P"; }
crss() { ps -o rss= -p "$(pgrep -d, -f "[c]hrom.*user-data-dir=$P")" 2>/dev/null | awk '{s+=$1} END {printf "%.2f", s/1024/1024}'; }

echo "start $(date '+%F %T') · $(vcgencmd measure_temp)"
min=999999
for i in $(seq 0 10 600); do
  av=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  sw=$(awk '/SwapTotal/ {t=$2} /SwapFree/ {f=$2} END {print int((t-f)/1024)}' /proc/meminfo)
  [ "$av" -lt "$min" ] && min=$av
  [ $((i % 60)) -eq 0 ] && echo "t=${i}s avail_mb=$av swap_used_mb=$sw llama=$(pgrep -c llama-server) chromium_procs=$(procs) tabs=$(tabs) chromium_rss_gb=$(crss)"
  sleep 10
done
# Qwen3.5 คิดก่อนตอบ (reasoning) · รอบก่อน max_tokens 200 ได้คำตอบว่าง → ให้ 1500 และแยกส่วนคิดออก
resp=$(curl -s --unix-socket "$SOCK" http://x/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"ตอบคำเดียว: 2+2 เท่ากับเท่าไร"}],"max_tokens":1500}')
ans=$(echo "$resp" | grep -o '"content":"[^"]*"' | tail -1)
reason=$(echo "$resp" | grep -o '"reasoning_content":"[^"]*"' | head -c 80)
fin=$(echo "$resp" | grep -o '"finish_reason":"[^"]*"')
echo "min_avail_mb=$min · llama_alive=$(pgrep -c llama-server) · chromium_procs=$(procs) · tabs=$(tabs) · answer=$ans · $fin · reasoning_head=$reason"
pkill -f "[c]hrom.*user-data-dir=$P"; sleep 2; rm -rf "$P"
if [ -n "$BEFORE" ]; then echo "$BEFORE" > "$CHOICE"; else rm -f "$CHOICE"; fi
systemctl --user restart aipc-llm
echo "end $(date '+%F %T') · $(vcgencmd measure_temp) · $(vcgencmd get_throttled)"
