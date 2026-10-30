#!/bin/sh
# วัดเวลาสร้างเสียง Wayu-Paxa-TTS-Edge เทียบ Piper บน Pi 5 · 2026-10-30
# docs/benchmarks/2026-10-30-tts-wayu/README.md · ไม่แตะ venv ของแอป · /opt อ่านอย่างเดียว
#   sh scripts/bench/run_tts.sh
set -u
cd "$(dirname "$0")/../.."
O=docs/benchmarks/2026-10-30-tts-wayu
S=tests/data/tts_wayu_sentences.json
KEEP="$HOME/tts-wayu-wav"   # ไฟล์เสียงให้ Pakon ฟัง · ไม่ใส่ git
export PYTHONIOENCODING=utf-8
mkdir -p "$O"
state() { echo "$1 $(date -Iseconds) $(vcgencmd measure_temp) $(vcgencmd get_throttled)"; }

state before
"$HOME/wayu-venv/bin/python" scripts/bench/tts_speed.py --engine wayu --model "$HOME/wayu-model" \
    --voices f_young_clear m_young_clear f_mid_clear --sentences "$S" \
    --out "$O/wayu-pi5.json" --keep "$KEEP" || echo "WAYU-FAIL"
state mid
/opt/aipc-voice/venv/bin/python scripts/bench/tts_speed.py --engine piper \
    --model /opt/aipc-voice/th_TH-tsync2-medium.onnx --voices piper-th --sentences "$S" \
    --out "$O/piper-pi5.json" --keep "$KEEP" || echo "PIPER-FAIL"
state after
echo ALL-DONE
