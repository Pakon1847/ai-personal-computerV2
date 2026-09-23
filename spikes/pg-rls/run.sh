#!/usr/bin/env bash
# Spike 0.6 (ADR-004): พิสูจน์ว่า PostgreSQL + peer auth + FORCE RLS แยกข้อมูลระหว่างผู้ใช้ได้จริง
#
#   bash spikes/pg-rls/run.sh            ดูว่าจะทำอะไร (ไม่ทำอะไรจริง) ← ค่าเริ่มต้น
#   bash spikes/pg-rls/run.sh --apply    สร้างของทดสอบ รันทุกกรณี เขียนผลลง docs/benchmarks/
#   bash spikes/pg-rls/run.sh --cleanup  ลบของทดสอบทั้งหมด
#
# สิ่งที่ --apply แตะ: สร้าง Linux user ระบบ 2 คน (aipc_spike_a, aipc_spike_b ไม่มี home ล็อกอินไม่ได้)
# และฐานข้อมูล aipc_spike ใน PostgreSQL · ไม่แก้ pg_hba.conf ไม่แก้ไฟล์บูต ไม่แตะข้อมูลอื่น
# ต้องติดตั้ง PostgreSQL ก่อน: sudo apt install -y postgresql
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
USERS=(aipc_spike_a aipc_spike_b)
MODE="${1:-plan}"

plan() {
  cat <<EOF
โหมดดูอย่างเดียว — ยังไม่ได้ทำอะไร

--apply จะทำตามลำดับ:
  1. ตรวจว่ามี psql และ pg_hba.conf มีบรรทัด 'local ... peer' (อ่านอย่างเดียว ไม่แก้)
  2. sudo useradd --system --no-create-home --shell /usr/sbin/nologin ${USERS[*]}
  3. sudo -u postgres psql -f $HERE/setup.sql   (สร้าง role 3 ตัว + ฐานข้อมูล aipc_spike)
  4. รัน 15 กรณีทดสอบ ในฐานะผู้ใช้ A, B และ postgres
  5. เขียนผลลง docs/benchmarks/<วันที่>-<เครื่อง>-pg-rls.{csv,md}

--cleanup จะ: ลบฐานข้อมูลและ role ตาม cleanup.sql แล้ว userdel ผู้ใช้ทั้งสอง
EOF
}

cleanup() {
  (cd /tmp && sudo -u postgres psql -X -q -f "$HERE/cleanup.sql")
  for u in "${USERS[@]}"; do
    if id "$u" >/dev/null 2>&1; then sudo userdel "$u"; fi
  done
  echo "ลบของทดสอบแล้ว"
}

# รัน SQL ในฐานะ Linux user คนหนึ่ง · cd /tmp เพราะ user ระบบไม่มีสิทธิ์อ่านโฟลเดอร์ปัจจุบัน
# คืนข้อความผลลัพธ์ และไม่ให้ error ของ psql ทำให้สคริปต์หยุด (error คือผลที่เราอยากเห็นในบางกรณี)
q() {
  local user="$1"; shift
  (cd /tmp && sudo -u "$user" psql -X -q -At -v ON_ERROR_STOP=1 -d aipc_spike "$@" 2>&1) || echo "ERROR_EXIT"
}

CSV=""
PASSES=0
FAILS=0

# record <id> <ผู้ทดสอบ> <สิ่งที่ลอง> <ที่คาดไว้> <ผลจริง> <ผ่าน/ไม่ผ่าน/สังเกต>
record() {
  local out="${5//$'\n'/ \\ }"
  out="${out//\"/\'}"
  printf '%-3s %-6s %-9s %s\n     ผล: %s\n' "$1" "$2" "$6" "$3" "$out"
  CSV+="$1,$2,\"$3\",\"$4\",\"$out\",$6"$'\n'
  case "$6" in ผ่าน) PASSES=$((PASSES + 1)) ;; ไม่ผ่าน) FAILS=$((FAILS + 1)) ;; esac
}

expect_value() {  # ผลต้องตรงค่านี้พอดี
  local id="$1" who="$2" what="$3" want="$4" got="$5"
  if [[ "$got" == "$want" ]]; then record "$id" "$who" "$what" "$want" "$got" ผ่าน
  else record "$id" "$who" "$what" "$want" "$got" ไม่ผ่าน; fi
}

expect_error() {  # ต้องถูกปฏิเสธ
  local id="$1" who="$2" what="$3" got="$4"
  if [[ "$got" == *ERROR* || "$got" == *FATAL* || "$got" == *failed* ]]; then
    record "$id" "$who" "$what" "ถูกปฏิเสธ" "$got" ผ่าน
  else record "$id" "$who" "$what" "ถูกปฏิเสธ" "$got" ไม่ผ่าน; fi
}

apply() {
  command -v psql >/dev/null || { echo "ไม่เจอ psql — ติดตั้งก่อน: sudo apt install -y postgresql"; exit 1; }
  local hba
  hba="$(cd /tmp && sudo -u postgres psql -X -At -c 'SHOW hba_file')"
  if ! sudo grep -Eq '^local[[:space:]]+all[[:space:]]+all[[:space:]]+peer' "$hba"; then
    echo "pg_hba.conf ($hba) ไม่มีบรรทัด 'local all all peer' — สคริปต์นี้ไม่แก้ให้ หยุดก่อน"; exit 1
  fi

  if [[ "$(cd /tmp && sudo -u postgres psql -X -At -c "SELECT 1 FROM pg_roles WHERE rolname = 'aipc_spike_owner'")" == 1 ]]; then
    echo "มีของทดสอบจากรอบก่อนค้างอยู่ — รัน --cleanup ก่อน"; exit 1
  fi

  local stamp board out
  stamp="$(date +%F)"
  board="$("$REPO/.venv/bin/python" -c 'from aipc.bench import machine; print(machine.collect().board_class)')"
  out="$REPO/docs/benchmarks/$stamp-$board-pg-rls"
  [[ -e "$out.csv" ]] && { echo "$out.csv มีอยู่แล้ว — ห้ามเขียนทับ"; exit 1; }

  for u in "${USERS[@]}"; do
    id "$u" >/dev/null 2>&1 || sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$u"
  done
  (cd /tmp && sudo -u postgres psql -X -q -f "$HERE/setup.sql")

  local A=aipc_spike_a B=aipc_spike_b
  echo "=== กรณีทดสอบ ==="
  expect_value 1 A "A เขียนแชทของตัวเอง" "1" \
    "$(q $A -c "INSERT INTO chats(body) VALUES ('secret-a') RETURNING 1")"
  expect_value 2 A "A นับแถวของตัวเอง" "1" "$(q $A -c 'SELECT count(*) FROM chats')"
  expect_value 3 B "B อ่านตาราง (ต้องไม่เห็นแถวของ A)" "0" "$(q $B -c 'SELECT count(*) FROM chats')"
  expect_error 4 B "B เขียนแถวโดยอ้างว่าเป็นของ A" \
    "$(q $B -c "INSERT INTO chats(owner, body) VALUES ('$A', 'fake')")"
  expect_value 5 B "B แก้แถวของ A" "0" \
    "$(q $B -c "WITH u AS (UPDATE chats SET body = 'hacked' RETURNING 1) SELECT count(*) FROM u")"
  expect_value 6 B "B ลบแถวของ A" "0" \
    "$(q $B -c 'WITH d AS (DELETE FROM chats RETURNING 1) SELECT count(*) FROM d')"
  expect_value 7 A "A ตรวจว่าแถวของตัวเองยังอยู่ครบ" "secret-a" "$(q $A -c 'SELECT body FROM chats')"
  expect_error 8 B "B ปิด RLS ของตาราง" "$(q $B -c 'ALTER TABLE chats DISABLE ROW LEVEL SECURITY')"
  expect_error 9 B "B สลับตัวเป็น A ด้วย SET ROLE" "$(q $B -c "SET ROLE $A")"
  expect_error 10 B "B ต่อ DB โดยอ้างชื่อ A (peer auth)" \
    "$(cd /tmp && sudo -u $B psql -X -At -U $A -d aipc_spike -c 'SELECT 1' 2>&1 || true)"
  expect_value 11 owner "เจ้าของตาราง (FORCE RLS ต้องบังคับด้วย)" "0" \
    "$(q postgres -c 'SET ROLE aipc_spike_owner' -c 'SELECT count(*) FROM chats')"
  expect_value 12 B "B อ่านผ่าน view แบบ security_invoker" "0" \
    "$(q $B -c 'SELECT count(*) FROM chats_invoker')"
  record 13 B "B อ่านผ่าน view แบบธรรมดา (ไม่มี security_invoker)" "บันทึกผล" \
    "$(q $B -c 'SELECT count(*) FROM chats_definer')" สังเกต
  expect_error 14 B "B ยิง query ค้างนาน (statement_timeout 2 วิ)" "$(q $B -c 'SELECT pg_sleep(4)')"
  record 15 root "superuser postgres อ่านตาราง" "เห็นได้ — root/superuser อยู่นอกขอบเขต (THREAT_MODEL)" \
    "$(q postgres -c 'SELECT count(*) FROM chats')" สังเกต

  printf 'id,ผู้ทดสอบ,สิ่งที่ลอง,ที่คาดไว้,ผลจริง,ตัดสิน\n%s' "$CSV" >"$out.csv"
  "$REPO/.venv/bin/python" -m aipc.bench machine >"$out.machine.json"
  {
    echo "# Spike 0.6 PostgreSQL peer auth + FORCE RLS ($board)"
    echo
    echo "ผ่าน $PASSES · ไม่ผ่าน $FAILS · สังเกต 2 · PostgreSQL $(psql --version)"
    echo
    echo "ผลรายกรณีอยู่ใน \`$(basename "$out").csv\` · สภาพเครื่องใน \`$(basename "$out").machine.json\`"
    echo
    echo "ผลนี้พิสูจน์ความถูกต้องของการแยกสิทธิ์ (ใช้ Pi 4 ได้) ไม่ใช่ความเร็ว"
    echo
    echo "## หมายเหตุของผู้วัด"
    echo
    echo "(เขียนเพิ่ม: กรณี 13 เห็นกี่แถว และแปลว่าอะไร)"
  } >"$out.md"
  echo "=== ผ่าน $PASSES ไม่ผ่าน $FAILS === เขียนผลที่ $out.{csv,md,machine.json}"
  echo "ลบของทดสอบ: bash spikes/pg-rls/run.sh --cleanup"
}

case "$MODE" in
  plan) plan ;;
  --apply) apply ;;
  --cleanup) cleanup ;;
  *) echo "ใช้: $0 [--apply|--cleanup]"; exit 2 ;;
esac
