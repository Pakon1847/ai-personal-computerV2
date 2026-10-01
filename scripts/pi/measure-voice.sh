#!/usr/bin/env bash
# วัดความเร็วเสียงไทยบน Pi 5 (การ์ด 0019 ข้อ 6) · ไม่แตะแอป · ติดตั้งเครื่องมือใน ~/voice-bench
#   ./scripts/pi/measure-voice.sh [ผลลัพธ์.json]
# 1) build whisper.cpp (ggml-org · tag ที่ระบุ) · 2) โหลด Thonburian Whisper medium q5_0 + Piper + เสียง th_TH-tsync2 (ตรวจ sha256 ที่ได้ไว้ในผล)
# 3) Piper สร้างเสียงประโยคคำสั่ง 10 ประโยค (วัดเวลา TTS) → whisper.cpp ถอดกลับ (วัดเวลา STT · RTF)
# เสียงสังเคราะห์ใช้วัด "ความเร็ว" เท่านั้น · ข้อความที่ถอดได้เก็บไว้ดูแต่ห้ามอ้างเป็นความแม่น
set -euo pipefail
OUT="${1:-$HOME/voice-bench/result.json}"
DIR="$HOME/voice-bench"
WHISPER_TAG="${WHISPER_TAG:-v1.9.4}"
# รุ่นถอดเสียง (ไฟล์ใน ~/voice-bench) · STT_ARGS เพิ่มตัวเลือกให้ whisper-cli เช่น "-ac 512"
export STT_MODEL="${STT_MODEL:-thonburian-medium-q5_0.bin}" STT_ARGS="${STT_ARGS:-}"
mkdir -p "$DIR" && cd "$DIR"

if [ ! -x whisper.cpp/build/bin/whisper-cli ]; then
  git clone -q --depth 1 --branch "$WHISPER_TAG" https://github.com/ggml-org/whisper.cpp
  cmake -S whisper.cpp -B whisper.cpp/build -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build whisper.cpp/build -j4 --target whisper-cli >/dev/null
fi
[ -f thonburian-medium-q5_0.bin ] || curl -fsSL -o thonburian-medium-q5_0.bin \
  https://huggingface.co/suebphatt/thonburian-whisper-ggml/resolve/main/thonburian-medium-q5_0.bin
# Piper รุ่นเก่า (ไบนารี 2023.11.14-2) อ่านเสียง tsync2 ไม่ได้ ("Phonemes must be one codepoint") → ใช้ piper-tts จาก pip
# ตัวแปลงหน่วยเสียงไทยของ piper-tts ใช้ tltk · tltk ระบุ scikit-learn~=1.2 ซึ่ง build บน Python 3.13 ไม่ได้
# → ติดตั้ง tltk แบบ --no-deps แล้วเติมโมดูลที่ขาดเอง (ต้นทุนจริงที่ต้องรายงาน: ไลบรารีหนักหลายตัว)
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
  venv/bin/pip install -q piper-tts && venv/bin/pip install -q --no-deps tltk
  venv/bin/pip install -q nltk scikit-learn pandas sklearn_crfsuite requests gensim unicode_rbnf
fi
V=https://huggingface.co/rhasspy/piper-voices/resolve/main/th/th_TH/tsync2/medium
[ -f th_TH-tsync2-medium.onnx ] || curl -fsSL -o th_TH-tsync2-medium.onnx "$V/th_TH-tsync2-medium.onnx"
[ -f th_TH-tsync2-medium.onnx.json ] || curl -fsSL -o th_TH-tsync2-medium.onnx.json "$V/th_TH-tsync2-medium.onnx.json"

python3 - "$OUT" <<'PY'
import hashlib, json, os, subprocess, sys, time, wave
d = os.path.expanduser("~/voice-bench")
sents = ["เปิดยูทูบ", "ปรับเสียงเป็นสามสิบ", "เปิดหน้าตั้งค่า", "ปิดเสียงหน่อย", "เตือนส่งรายงานพรุ่งนี้บ่ายสอง",
         "ทำไมเครื่องช้า", "วันนี้ต้องทำอะไรบ้าง", "เปิดโหมดทำงานให้หน่อย", "แปลคำว่าขอบคุณเป็นภาษาอังกฤษ",
         "ช่วยสรุปข่าวนี้ให้หน่อย"]
def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()
rows = []
for i, s in enumerate(sents):
    wav = f"{d}/s{i}.wav"
    t0 = time.monotonic()
    subprocess.run([f"{d}/venv/bin/python", "-m", "piper", "-m", f"{d}/th_TH-tsync2-medium.onnx", "-f", wav],
                   input=s.encode(), capture_output=True, check=True)
    tts = time.monotonic() - t0
    with wave.open(wav) as w:
        dur = w.getnframes() / w.getframerate()
    wav16 = f"{d}/s{i}-16k.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "16000", "-ac", "1", wav16], check=True)
    t0 = time.monotonic()
    r = subprocess.run([f"{d}/whisper.cpp/build/bin/whisper-cli", "-m", f"{d}/{os.environ['STT_MODEL']}",
                        "-l", "th", "-t", "4", "-nt", *os.environ["STT_ARGS"].split(), "-f", wav16],
                       capture_output=True, text=True)
    stt = time.monotonic() - t0
    rows.append({"text": s, "audio_s": round(dur, 2), "tts_s": round(tts, 2), "stt_s": round(stt, 2),
                 "rtf": round(stt / dur, 2), "heard": r.stdout.strip()})
    print(f"{s} · เสียง {dur:.1f} วิ · TTS {tts:.1f} วิ · STT {stt:.1f} วิ (RTF {stt/dur:.2f}) · ได้ยิน: {r.stdout.strip()}")
med = lambda k: sorted(x[k] for x in rows)[len(rows) // 2]
out = {"rows": rows, "tts_s_median": med("tts_s"), "stt_s_median": med("stt_s"), "rtf_median": med("rtf"),
       "models": {f: sha(f"{d}/{f}") for f in (os.environ["STT_MODEL"], "th_TH-tsync2-medium.onnx")},
       "stt_args": os.environ["STT_ARGS"],
       "note": "เสียงสังเคราะห์จาก Piper · ใช้อ้างความเร็วเท่านั้น ไม่ใช่ความแม่น"}
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("TTS มัธยฐาน", out["tts_s_median"], "วิ · STT มัธยฐาน", out["stt_s_median"], "วิ · RTF", out["rtf_median"])
PY
