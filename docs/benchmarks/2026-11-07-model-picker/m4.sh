#!/usr/bin/env bash
# M4 (การ์ด 0076): Qwen3.5 4B + Chromium 3 แท็บ 10 นาที → ไม่ถูก OOM kill
# ข้อจำกัด: ไม่มีคนเข้าจอตอนวัด → Chromium แบบ headless (ไม่มีหน้าต่าง/GPU compositor) · RAM อาจน้อยกว่าใช้งานจริง
set -u
CHOICE="${XDG_CONFIG_HOME:-$HOME/.config}/aipc/llm-model"
SOCK="$XDG_RUNTIME_DIR/aipc/llm.sock"
BEFORE="$(cat "$CHOICE" 2>/dev/null || true)"
echo qwen3.5-4b > "$CHOICE"; systemctl --user restart aipc-llm
until curl -sf --unix-socket "$SOCK" http://x/health >/dev/null; do sleep 1; done
P=$(mktemp -d)
# รอบแรก (m4-invalid.log) นับ Chromium ด้วย pgrep ชื่อโปรเซส = ผิด (ชื่อจริงไม่ใช่ chromium) · พิสูจน์ไม่ได้ว่าเปิดอยู่ → ไม่นับ
chromium --headless=new --user-data-dir="$P" --no-first-run \
  https://www.youtube.com https://th.wikipedia.org/wiki/ประเทศไทย https://news.google.com >/dev/null 2>&1 &
CH=$!
echo "start $(date '+%F %T') · $(vcgencmd measure_temp)"
min=999999
for i in $(seq 0 10 600); do
  av=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  sw=$(awk '/SwapTotal/ {t=$2} /SwapFree/ {f=$2} END {print int((t-f)/1024)}' /proc/meminfo)
  [ "$av" -lt "$min" ] && min=$av
  llm=$(pgrep -c llama-server); chr=$(pgrep -fc "user-data-dir=$P")
  [ $((i % 60)) -eq 0 ] && echo "t=${i}s avail_mb=$av swap_used_mb=$sw llama=$llm chromium_procs=$chr"
  sleep 10
done
ans=$(curl -s --unix-socket "$SOCK" http://x/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"ตอบคำเดียว: 2+2 เท่ากับเท่าไร"}],"max_tokens":200}' | grep -o '"content":"[^"]*"' | tail -1)
echo "min_avail_mb=$min · llama_alive=$(pgrep -c llama-server) · chromium_procs=$(pgrep -fc "user-data-dir=$P") · answer=$ans"
pkill -f "user-data-dir=$P"; sleep 2; rm -rf "$P"
if [ -n "$BEFORE" ]; then echo "$BEFORE" > "$CHOICE"; else rm -f "$CHOICE"; fi
systemctl --user restart aipc-llm
echo "end $(date '+%F %T') · $(vcgencmd measure_temp) · $(vcgencmd get_throttled)"
