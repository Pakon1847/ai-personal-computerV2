#!/bin/bash
# การ์ด 0026: เทียบโมเดล · รอ Pi เย็น (< 65°C) ก่อนแต่ละโมเดล เพื่อให้เวลาเทียบกันได้
cd ~/aipc-0026 || exit 1
export PYTHONPATH=src
PY=~/aipc-0025/.venv/bin/python
OUT=~/voice-bench/models
SETS="tests/data/browse_v1.json tests/data/browse_v2.json tests/data/browse_v4.json"
mkdir -p $OUT
cool() { while [ "$(vcgencmd measure_temp | tr -dc 0-9 | cut -c1-2)" -ge 65 ]; do sleep 10; done; }
for m in thonburian-distill-small-f16 thonburian-distill-small-q5_0 thonburian-small-q5_0 thonburian-small-f16 thonburian-medium-q5_0; do
  cool; echo "== $m start $(vcgencmd measure_temp) $(date +%T)"
  $PY -m aipc.spikes.voice_models_eval ~/voice-bench/$m.bin ~/voice-bench/synth $SETS --out $OUT/$m.json > $OUT/$m.log 2>&1
  echo "   end $(vcgencmd measure_temp) $(vcgencmd get_throttled) rc=$?"
done
for hw in "" --hotwords; do
  cool; echo "== zipformer$hw start $(vcgencmd measure_temp) $(date +%T)"
  ~/voice-bench/sherpa-venv/bin/python -m aipc.spikes.voice_zipformer_eval ~/voice-bench/zipformer-th ~/voice-bench/synth $SETS $hw --out $OUT/zipformer$hw.json > $OUT/zipformer$hw.log 2>&1
  echo "   end $(vcgencmd measure_temp) $(tail -1 $OUT/zipformer$hw.log)"
done
echo DONE
