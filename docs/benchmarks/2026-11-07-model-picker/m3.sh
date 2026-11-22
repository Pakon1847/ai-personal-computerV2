#!/usr/bin/env bash
# M3 (การ์ด 0076): สลับครบ 3 ตัวไปกลับ 3 รอบ · AI กลับมาพร้อมทุกครั้ง ≤ 180 วิ · ไม่มี OOM
# รันบน Pi 5 เป็นบัญชีที่ใช้ทดสอบ (เหมือนผู้ใช้กดเลือกในหน้าตั้งค่า: เขียนชื่อ → restart user service)
set -u
CHOICE="${XDG_CONFIG_HOME:-$HOME/.config}/aipc/llm-model"
SOCK="$XDG_RUNTIME_DIR/aipc/llm.sock"
mkdir -p "$(dirname "$CHOICE")"
BEFORE="$(cat "$CHOICE" 2>/dev/null || true)"
T0="$(date '+%F %T')"
echo "start $T0 · $(vcgencmd measure_temp) · $(vcgencmd get_throttled)"
for round in 1 2 3; do
  for key in gemma4-e2b qwen3.5-2b qwen3.5-4b; do
    echo "$key" > "$CHOICE"
    s=$(date +%s.%N)
    systemctl --user restart aipc-llm
    ok=0
    for _ in $(seq 1 360); do
      if curl -sf --unix-socket "$SOCK" http://x/health >/dev/null 2>&1; then ok=1; break; fi
      sleep 0.5
    done
    t=$(echo "$(date +%s.%N) - $s" | bc)
    model=$(curl -s --unix-socket "$SOCK" http://x/v1/models | grep -o '"id":"[^"]*"' | head -1)
    rss=$(ps -o rss= -C llama-server | awk '{s+=$1} END {printf "%.1f", s/1024/1024}')
    echo "round=$round key=$key ready=$ok seconds=$(printf %.1f "$t") $model rss_gb=$rss"
  done
done
if [ -n "$BEFORE" ]; then echo "$BEFORE" > "$CHOICE"; else rm -f "$CHOICE"; fi
systemctl --user restart aipc-llm
echo "oom_lines=$(journalctl -k --since "$T0" --no-pager 2>/dev/null | grep -ci 'out of memory\|oom-kill')"
echo "end $(date '+%F %T') · $(vcgencmd measure_temp) · $(vcgencmd get_throttled)"
