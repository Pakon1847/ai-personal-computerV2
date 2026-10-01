#!/usr/bin/env bash
# ติดตั้งตัวอ่านออกเสียงภาษาไทย (การ์ด 0019 · Pakon เลือก "ทำแค่อ่านออกเสียงไปก่อน" 2026-10-01)
#
#   ./scripts/pi/install-voice.sh             ดูว่าจะทำอะไร
#   sudo ./scripts/pi/install-voice.sh --apply
#   sudo ./scripts/pi/install-voice.sh --rollback
#   sudo ./scripts/pi/install-voice.sh --apply --stt-model <thonburian-distill-small-f16.bin>   + กดค้างเพื่อพูด
#     (ไฟล์ ggml แปลงจาก biodatlab/distill-whisper-th-small ด้วย whisper.cpp models/convert-h5-to-ggml.py ·
#      docs/benchmarks/2026-10-01-voice-small · ตรวจ sha256) · build whisper.cpp v1.9.4 ลง /opt/aipc-voice/whisper
#
# ทำอะไร: /opt/aipc-voice (root · อ่านได้ทุกคน)
#   venv/   piper-tts 1.8.0 + รุ่นตาม scripts/pi/voice-requirements.txt
#           tltk 1.11 ติดตั้งแบบ --no-deps (tltk ระบุ scikit-learn~=1.2 ซึ่ง build บน Python 3.13 ไม่ได้)
#   th_TH-tsync2-medium.onnx(.json)   เสียงไทยของ Piper · ตรวจ sha256 ตามที่วัดไว้
# ไลเซนส์: piper-tts GPL-3.0 · เสียง tsync2 CC BY-NC-SA 3.0 (ห้ามใช้เชิงพาณิชย์) → ใช้ได้ตาม ADR-014 (งานศึกษา)
# แอปเปิดตัวอ่านเมื่อกดปุ่มลำโพงครั้งแรก ไม่มี service · ไม่แตะ greetd, PAM, ไฟล์บูต · ไม่รีบูต
set -euo pipefail

MODE="dry-run"; STT_MODEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) MODE="apply" ;;
    --rollback) MODE="rollback" ;;
    --stt-model) STT_MODEL="${2:?}"; shift ;;
    *) echo "ไม่รู้จัก: $1" >&2; exit 2 ;;
  esac
  shift
done
WHISPER_TAG=v1.9.4
STT_SHA=c7affd39e55fd160835e22794eacf8c74e1aefd404b6b57e44ddb00b27ae28ea  # distill-small f16 (แปลง 2026-10-01)
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPT=/opt/aipc-voice
V=https://huggingface.co/rhasspy/piper-voices/resolve/main/th/th_TH/tsync2/medium
ONNX_SHA=136669378ee72dd27012604994099ca3c833e625c7cfdff05ccdf468a1a2115f
say() { printf '%s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { say "ต้องรันด้วย sudo" >&2; exit 1; }; }

if [ "$MODE" = "rollback" ]; then
  need_root
  rm -rf "$OPT"
  say "เสร็จ · ลบ $OPT แล้ว · ปุ่มลำโพงในแอปจะหายเอง"
  exit 0
fi

say "จะติดตั้งที่ $OPT: venv (piper-tts 1.8.0 + tltk 1.11) + เสียง th_TH-tsync2-medium (~60 MB) · ต้องใช้อินเทอร์เน็ต"
command -v pw-play >/dev/null || command -v aplay >/dev/null || say "เตือน: ไม่มี pw-play/aplay (เล่นเสียงไม่ได้)"
[ "$MODE" = "apply" ] || { say "== โหมดดูก่อน: ยังไม่เปลี่ยนอะไร · ใส่ --apply เพื่อทำจริง =="; exit 0; }
need_root
umask 022
mkdir -p "$OPT"
[ -x "$OPT/venv/bin/python" ] || python3 -m venv "$OPT/venv"
"$OPT/venv/bin/pip" install -q -r "$SRC/scripts/pi/voice-requirements.txt"
"$OPT/venv/bin/pip" install -q --no-deps tltk==1.11
for f in th_TH-tsync2-medium.onnx th_TH-tsync2-medium.onnx.json; do
  [ -f "$OPT/$f" ] || { curl -fsSL -o "$OPT/$f.part" "$V/$f" && mv "$OPT/$f.part" "$OPT/$f"; }
done
echo "$ONNX_SHA  $OPT/th_TH-tsync2-medium.onnx" | sha256sum -c --quiet \
  || { say "หยุด: sha256 ของเสียงไม่ตรงกับที่วัดไว้" >&2; rm -f "$OPT/th_TH-tsync2-medium.onnx"; exit 1; }
chmod -R a+rX "$OPT"
# ลองสังเคราะห์ 1 ประโยค (ตัวแปลงหน่วยเสียงไทยโหลดครั้งแรกตรงนี้)
echo "ทดสอบเสียง" | "$OPT/venv/bin/python" -m piper -m "$OPT/th_TH-tsync2-medium.onnx" -f /tmp/aipc-voice-test.wav >/dev/null 2>&1 \
  && rm -f /tmp/aipc-voice-test.wav && say "เสร็จ · สังเคราะห์เสียงได้ · ออกจากระบบแล้วเข้าใหม่ (หรือเปิดแอปใหม่) จะเห็นปุ่มลำโพง" \
  || { say "ติดตั้งแล้วแต่สังเคราะห์เสียงไม่ได้ · ดูข้อความด้วย: echo ทดสอบ | $OPT/venv/bin/python -m piper -m $OPT/th_TH-tsync2-medium.onnx -f /tmp/t.wav" >&2; exit 1; }

# ---------- กดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) ----------
[ -n "$STT_MODEL" ] || { say "ไม่ได้ใส่ --stt-model · ข้ามตัวถอดเสียง (ปุ่มไมค์จะไม่ขึ้น)"; exit 0; }
[ -f "$STT_MODEL" ] || { say "หยุด: ไม่มีไฟล์ $STT_MODEL" >&2; exit 1; }
echo "$STT_SHA  $STT_MODEL" | sha256sum -c --quiet || { say "หยุด: sha256 ของโมเดลถอดเสียงไม่ตรงกับที่วัดไว้" >&2; exit 1; }
if [ ! -x "$OPT/whisper/bin/whisper-cli" ]; then
  B=$(mktemp -d)
  git clone -q --depth 1 --branch "$WHISPER_TAG" https://github.com/ggml-org/whisper.cpp "$B/src"
  cmake -S "$B/src" -B "$B/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_TESTS=OFF >/dev/null
  cmake --build "$B/build" -j4 --target whisper-cli >/dev/null
  install -D -m 0755 "$B/build/bin/whisper-cli" "$OPT/whisper/bin/whisper-cli"
  rm -rf "$B"
fi
install -m 0644 "$STT_MODEL" "$OPT/thonburian-distill-small-f16.bin"
chmod -R a+rX "$OPT"
"$OPT/whisper/bin/whisper-cli" --help >/dev/null 2>&1 && say "เสร็จ · ตัวถอดเสียงพร้อม · ออกจากระบบแล้วเข้าใหม่จะเห็นปุ่มไมค์"   || { say "build whisper-cli ไม่สำเร็จ" >&2; exit 1; }
