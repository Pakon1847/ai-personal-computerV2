#!/bin/bash
# การ์ด 0026 รอบ 2–3 บน Pi 5: เวลา + RAM + ความแม่น (ทำซ้ำของโน้ตบุ๊ก) · เสียง Piper บน Pi
set -u
cd ~/aipc-0026
OUT=~/voice-bench/round2-pi; mkdir -p $OUT
cool() { while [ "$(vcgencmd measure_temp | grep -o "[0-9]*" | head -1)" -ge 65 ]; do sleep 10; done; }
echo "== synth start $(vcgencmd measure_temp) $(date +%T)"
PYTHONPATH=src /opt/aipc-voice/venv/bin/python -m aipc.spikes.voice_models2_eval synth ~/voice-bench/round2-audio /opt/aipc-voice/th_TH-tsync2-medium.onnx v1 v2 d h2 h3 2>&1 | grep -v "Dropping\|No phonemes"
for m in zip-hw5 ty-free; do
  cool; echo "== $m start $(vcgencmd measure_temp) $(vcgencmd get_throttled) $(date +%T)"
  PYTHONPATH=src ~/voice-bench/sherpa-venv/bin/python -c "import resource,subprocess,sys; subprocess.run(sys.argv[1:]); print(\"peak_rss_mb\", round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,1))" \
    ~/voice-bench/sherpa-venv/bin/python -m aipc.spikes.voice_models2_eval run ~/voice-bench/round2-audio ~/voice-bench/models2 --sets v1 v2 d h2 h3 --models $m --out $OUT/$m.json
  echo "   end $(vcgencmd measure_temp) $(vcgencmd get_throttled) $(date +%T)"
done
echo "== done $(date +%T)"
