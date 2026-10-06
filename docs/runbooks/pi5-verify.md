# ทดสอบบน Pi 5 ด้วยตัวเอง (จาก audit 2026-09-29/30)

ที่มา: [รายงาน audit](../reviews/2026-09-30-pi5-audit.md) · ข้อค้นพบ 98 ข้อ รวมเป็นชุดทดสอบ 62 ชุด · แต่ละชุดมีผู้ร่าง 1 และผู้ตรวจแย้ง 1 (ตรวจคำสั่งกับโค้ดจริง ความปลอดภัย และคำสั่งย้อน)

## อ่านก่อนเริ่ม

- **สถานะเครื่องตอนเขียน (2026-09-30 04:15):** ขั้น 9 ทำแล้ว (หน้า Login V2 ทำงาน · `/opt/aipc-v2` → รุ่น `ebd0bf80` · AI ติดตั้งแล้ว threads 3 + template ต้นฉบับ) · linger ของ aipc2030 ปิดแล้ว · rpcbind ปิดแล้ว · **memory cgroup ยังปิด** (`cgroup_disable=memory`) · ชุดทดสอบที่เขียนว่า "ยังไม่ติดตั้ง" ให้ข้ามขั้นติดตั้ง ทำเฉพาะขั้นตรวจ
- ทำตามลำดับหมวด A → E · ในหมวดเดียวกันทำตามลำดับที่เขียน · ข้อที่บอก "ก่อนเริ่ม" ต้องครบก่อน
- **ห้ามเขียนรหัสผ่านลงไฟล์/commit** · คำสั่ง `sudo` ให้พิมพ์รหัสเอง
- วัดระดับ 4: `git status --porcelain` ต้องว่าง · อุณหภูมิเริ่ม < 55°C · ไม่มีดาวน์โหลดหรือการวัดอื่นค้าง (`pgrep -af 'llama|curl|aipc.spikes'`)
- เกณฑ์ "ผ่านเมื่อ" ประกาศไว้ก่อนรันแล้ว (H9) · ห้ามแก้เกณฑ์หรือชุดข้อมูลหลังเห็นผล · ไม่ผ่าน = บันทึกว่าไม่ผ่าน
- ผลทุกข้อ commit บน Pi แล้วส่งกลับ PC ด้วย git bundle ([pi-phase0.md](pi-phase0.md))

## สารบัญ

- **A · อ่านอย่างเดียว (ไม่เปลี่ยนอะไร · ทาง SSH ได้)** · 9 ชุด · ~1.4 ชม.
  - V01 สแนปช็อตเครื่อง OS เฟิร์มแวร์ cgroup การ์ด journald (~10 นาที)
  - V02 เตรียม shell: ตัวแปรและคำสั่งช่วยที่ทุก section ใช้ (~5 นาที)
  - V03 ข้อมูลประกอบผลวัด LLM (sha256 · llama.cpp · ตัวเลือกของ server · ตัวอักษรไทย/วิ) (~10 นาที)
  - V04 ตัดคำไทย (libthai) และเทสต์หน้าจอบน Pi 5 (~10 นาที)
  - V05 ภาพรวมความปลอดภัยก่อนเปลี่ยน (~10 นาที)
  - V06 audit หลัง OOBE (~10 นาที)
  - V07 ตรวจล็อก llama.cpp และ sha256 โมเดล (~10 นาที)
  - V08 เช็กเครื่องว่าง + เทียบ LLM รอบ 1 กับรอบ 2 (~15 นาที)
  - V09 ความพร้อมก่อนสาธิต: เวลา เขตเวลา จอ และ claude (~5 นาที)
- **B · วัดผล (ไม่เปลี่ยนระบบ · ห้ามมีงานหนักอื่นระหว่างวัด)** · 20 ชุด · ~11.9 ชม.
  - V10 เวลาโหลดโมเดลจาก microSD แบบเย็นและอุ่น (~25 นาที)
  - V11 RAM ของ llama-server ที่ context 4096 ใต้ MemoryMax=4G (~35 นาที)
  - V12 soak 10 นาที ความร้อน พัดลม และไฟ (~25 นาที)
  - V13 เลือกสกิลแบบ AI ก่อน วัด 3 รอบให้เป็นระดับ 4 (~60 นาที)
  - V14 เวลาถึงคำแรกของแชทจริง (มีรายการสกิล) แบบเย็นและแบบอุ่นก่อน (~25 นาที)
  - V15 cache หลังสลับไปใช้สกิลและหลังเริ่มตัดประวัติ (~60 นาที)
  - V16 ข้อความยาว: ความเร็วอ่าน prompt 1000/2000 token และตอนเกิน context (~50 นาที)
  - V17 คุณภาพคำตอบตอนใช้สกิลสรุป/จดหมาย และแชทที่มีรายการสกิล (~75 นาที)
  - V18 สกิลที่ Claude เขียน ผ่านตัวเลือกสกิลของแอปบน Pi 5 (~70 นาที)
  - V19 ตัวเลือกความเร็วหลังเลือกโมเดล: Q4_0 · flash attention · KV q8_0 (~70 นาที)
  - V20 ตัวช่วยร่าง Qwen3-0.6B (speculative decoding) (~50 นาที)
  - V21 หน้าจอวาดด้วย GPU จริงไหม · เฟรมแรก · RAM/CPU ขณะว่าง (~20 นาที)
  - V22 ต้นทุนตอนกด Enter: สร้างรายการแชทใหม่ + อ่านไฟล์ประวัติ (~15 นาที)
  - V23 งานตรวจเครื่องทุก 10 วิบนเธรดหลัก ขณะ LLM ทำงาน (~12 นาที)
  - V24 เวลาเปิดหน้าจอ Shell ที่ HEAD (ระดับ 4 ด้วย aipc.bench) (~10 นาที)
  - V25 forge (claude -p) บน Pi 5 และที่เก็บ credential (~25 นาที)
  - V26 เวอร์ชันไลบรารีและเทสต์ทั้งชุดบน Pi 5 (~15 นาที)
  - V27 สำรองข้อมูลผู้ใช้และลองกู้ลงโฟลเดอร์ชั่วคราว (~25 นาที)
  - V28 เทสต์ทั้งชุด + รุ่นไลบรารีบน Pi 5 (~10 นาที)
  - V29 ใบหน้าจากไฟล์ LFW: เวลา RAM ความแม่นยำ fp32/int8 (~35 นาที)
- **C · เปลี่ยนค่าระบบ (สำรองก่อน · มีคำสั่งย้อนทุกข้อ)** · 8 ชุด · ~3.7 ชม.
  - V30 จำกัดขนาด journald 200 MB (~5 นาที)
  - V31 เปิด memory cgroup ให้ MemoryMax มีผลจริง (~25 นาที)
  - V32 เปิดชาร์จแบต RTC (~15 นาที · หน้าเครื่อง)
  - V33 forge บน Pi 5 (Claude Code ARM64) และค่าตั้งของบัญชีผู้ดูแล (~20 นาที)
  - V34 ปิด Pi Connect, linger และ rpcbind (~25 นาที)
  - V35 จำกัด SSH + กล้อง/ไมค์ข้ามบัญชี (~40 นาที · หน้าเครื่อง)
  - V36 ขั้น 9 + อัปเดตครั้งแรกและ rollback ไป-กลับบน Pi 5 (~60 นาที · หน้าเครื่อง)
  - V37 T14 รุ่นที่พังต้องไม่ถูกสลับ (~30 นาที)
- **D · ต้องอยู่หน้าเครื่อง (จอ คีย์บอร์ด ถอดปลั๊ก กล้อง)** · 23 ชุด · ~19.6 ชม.
  - V38 นาฬิกาหลังปิดเครื่องแบบออฟไลน์ (~45 นาที · หน้าเครื่อง)
  - V39 ใช้งานจริง 60 นาที: RAM ทั้งระบบ การเขียนการ์ด และ log (~75 นาที · หน้าเครื่อง)
  - V40 สั่งเครื่องจริงบนเดสก์ท็อป Pi 5 (แอป · เว็บ · เสียง) + สกิล 4 ที่ HEAD (~25 นาที · หน้าเครื่อง)
  - V41 ครบเส้นบนหน้าจอ V2: Claude สร้างสกิล → ติดตั้ง → AI ในเครื่องเลือกใช้ (~45 นาที · หน้าเครื่อง)
  - V42 fps ขณะ AI ตอบ และหน้าจอทำให้ LLM ช้าลงเท่าไร (~50 นาที · หน้าเครื่อง)
  - V43 เวลาเปิดเครื่องถึงหน้า Login และ login ถึง Shell (~35 นาที · หน้าเครื่อง)
  - V44 RAM ของหน้าจอและ labwc ในเซสชัน V2 จริง (~30 นาที · หน้าเครื่อง)
  - V45 ติดตั้งหน้า Login V2 + T1–T3 (~75 นาที · หน้าเครื่อง)
  - V46 สมัคร 5 บัญชี ตัวช่วย root PIN และ home (~50 นาที · หน้าเครื่อง)
  - V47 ออกจากระบบแล้ว AI ต้องหาย (T4) (~30 นาที · หน้าเครื่อง)
  - V48 socket ของ AI: T7 กับ T12 (~20 นาที · หน้าเครื่อง)
  - V49 T6 นับการเชื่อมต่อขาออก 30 นาที (~40 นาที · หน้าเครื่อง)
  - V50 Image การ์ด + การ์ดสำรองบูตได้ + ลายนิ้วมือตรงกัน (~120 นาที · หน้าเครื่อง)
  - V51 อัปเดตตอนไม่มีเน็ตจาก wheel ที่เก็บไว้ (~25 นาที · หน้าเครื่อง)
  - V52 T10 ดึงปลั๊กระหว่างบันทึกข้อมูล (~90 นาที · หน้าเครื่อง)
  - V53 ดึงปลั๊กทันทีหลังสลับรุ่นแอป (~90 นาที · หน้าเครื่อง)
  - V54 T13 ดิสก์เต็ม (~45 นาที · หน้าเครื่อง)
  - V55 กล้อง USB + ลงทะเบียน + สแกนจริง 20 ครั้ง (~25 นาที · หน้าเครื่อง)
  - V56 ใบหน้าพร้อม LLM (แย่ง CPU) (~25 นาที · หน้าเครื่อง)
  - V57 PAD spot test: รูปพิมพ์และรูปบนจอมือถือ (~40 นาที · หน้าเครื่อง)
  - V58 หน้าจอ V2: RAM หลังใช้กล้อง + ลงทะเบียน 5 ท่า (~25 นาที · หน้าเครื่อง)
  - V59 T1 บูต · T7 AI พัง · T12 สองบัญชี (~120 นาที · หน้าเครื่อง)
  - V60 T6 ไม่รั่ว 2 ช่วง: ใช้งานปกติ / ระหว่าง forge (~50 นาที · หน้าเครื่อง)
- **E · คนจริง (ซ้อมสาธิต ผู้ใช้ทดลอง)** · 2 ชุด · ~4.0 ชม.
  - V61 ซ้อมสาธิต 3 รอบ (มีเน็ต 2 · ออฟไลน์ 1) (~90 นาที · หน้าเครื่อง)
  - V62 pilot ผู้ใช้จริง 5 คน + SUS (~150 นาที · หน้าเครื่อง)

## A · อ่านอย่างเดียว (ไม่เปลี่ยนอะไร · ทาง SSH ได้)

### V01 สแนปช็อตเครื่อง OS เฟิร์มแวร์ cgroup การ์ด journald
- **ตอบข้อ audit:** hw-os-8, hw-os-9, deploy-5, hw-os-1 (ส่วนอ่านค่า), hw-os-4 (รุ่นการ์ด), hw-os-7 และ data-5 (ส่วนอ่านค่า)
- **ทำไมต้องทดสอบ:** ค่าที่วัดวันนี้ (governor, EEPROM, page size, cgroup, journald, รุ่นการ์ด) อยู่แค่ในแชต ยังไม่มีไฟล์ใน repo ที่ผูก commit · `aipc.bench machine` ไม่จดค่าเหล่านี้ · ยังไม่มีรายการแพ็กเกจ OS เลย · ยังไม่รู้ว่าเฟิร์มแวร์อัปเดตตัวเองตอนบูตไหม (ระดับ 4 มีเฉพาะผล doctor ของ 2026-09-29)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี (อ่านอย่างเดียว · `rpi-eeprom-update` ที่ไม่ใส่ `-a` แค่แสดงสถานะ) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** measure-llm.sh รอบ 2 จบแล้ว · ไม่มีดาวน์โหลดค้าง · **ห้ามรีบูตก่อนทำข้อนี้** (บิต throttle ตั้งแต่บูต และ log ใน /tmp จะหาย) · `git status --porcelain` ต้องว่าง
```sh
cd ~/aipc
git status --porcelain      # ต้องว่าง (machine.json จด git_dirty)
# เก็บนอก repo ก่อน แล้วค่อยคัดเข้า repo = ไฟล์ที่เขียนระหว่างทางไม่ทำให้ git_dirty เป็น true
O=~/os-snapshot-$(date +%F); mkdir -p $O; U=$(id -u)
./.venv/bin/python -m aipc.bench machine > $O/machine.json
./.venv/bin/python -m aipc.doctor --save --out $O > /dev/null
{
  echo "== บอร์ด เคอร์เนล เฟิร์มแวร์"
  tr -d '\0' < /proc/device-tree/model; echo
  uname -r; echo "PAGESIZE $(getconf PAGESIZE)"
  echo "governor $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) · max $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq) kHz"
  vcgencmd version; vcgencmd bootloader_version
  echo "== ไฟและความร้อน (ค่าตั้งแต่บูตรอบนี้)"
  vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V; vcgencmd measure_temp
  echo "== cgroup"
  tr ' ' '\n' < /proc/cmdline | grep -i cgroup
  echo "top: $(cat /sys/fs/cgroup/cgroup.controllers)"
  echo "user@$U: $(cat /sys/fs/cgroup/user.slice/user-$U.slice/user@$U.service/cgroup.controllers)"
  echo "== microSD"
  for f in name manfid oemid date type; do echo "$f $(cat /sys/block/mmcblk0/device/$f)"; done
  findmnt -no SOURCE,OPTIONS /
  echo "== swap zram"; cat /proc/swaps; /usr/sbin/zramctl
  echo "== journald"
  journalctl --disk-usage
  [ -d /var/log/journal ] && echo "เก็บลงการ์ด (มี /var/log/journal)" || echo "เก็บใน RAM (ไม่มี /var/log/journal)"
  systemd-analyze cat-config systemd/journald.conf | grep -Ev '^\s*(#|$)'
  echo "== อัปเดตอัตโนมัติ"
  dpkg-query -W -f='${Package} ${Status}\n' unattended-upgrades packagekit
  echo "hold: $(apt-mark showhold | tr '\n' ' ')"
  systemctl list-timers --all --no-pager | grep -Ei 'apt|unattended|update' || echo "ไม่มี timer ของ apt"
  echo "rpi-eeprom-update.service: $(systemctl is-enabled rpi-eeprom-update.service 2>&1)"
  grep -E '^FIRMWARE_RELEASE_STATUS' /etc/default/rpi-eeprom-update
} > $O/snapshot.txt 2>&1
# สองคำสั่งนี้ใช้ sudo (พิมพ์รหัสเอง)
sudo rpi-eeprom-update >> $O/snapshot.txt 2>&1
sudo sh -c 'for f in /sys/kernel/debug/mmc*/ios; do echo "== $f"; cat "$f"; done' >> $O/snapshot.txt 2>&1   # โหมดบัส (บรรทัด timing spec)
# รายการแพ็กเกจ OS ทั้งหมด (ไว้ diff ก่อนวันสอบ)
dpkg-query -W -f='${Package}\t${Version}\n' > $O/dpkg.txt
# log ของ llama-server จากรอบวัดที่เพิ่งจบ (/tmp หายเมื่อรีบูต)
for f in /tmp/llama-*.log; do [ -f "$f" ] || continue
  echo "$f $(wc -c < "$f") ไบต์ · คำขอแชท $(grep -c 'POST /v1/chat/completions' "$f")"; done > $O/llama-log-size.txt
cat $O/snapshot.txt $O/llama-log-size.txt
D=docs/benchmarks/$(date +%F)-pi5-os-snapshot; mkdir -p $D; cp $O/* $D/
git add $D && git commit -m "bench(pi5): สแนปช็อตเครื่อง OS เฟิร์มแวร์ cgroup การ์ด journald"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) commit สำเร็จ และในโฟลเดอร์มีครบ: snapshot.txt, dpkg.txt, machine.json (`git_dirty: false`), `<วันที่>-pi5-hardware.md/.json`, llama-log-size.txt · get_throttled ไม่มีบิต 0x10000 (ไม่เคยไฟตก · ค่าวันนี้ 0xe0000 ผ่านข้อนี้) · doctor ข้อไฟเลี้ยงยัง "ผ่าน" · `unattended-upgrades` ต้องขึ้น "no packages found" หรือ "not-installed" · timer `apt-daily` ที่มีอยู่ไม่นับว่าไม่ผ่าน (แค่โหลดรายการแพ็กเกจ) · ถ้ามี unattended-upgrades หรือ rpi-eeprom-update.service เป็น enabled ให้จดไว้ และให้ Pakon ตัดสินก่อนทำ image สอบ (ห้ามถอดเองในข้อนี้) · ค่า cgroup, journald, noatime, EXT5V จดตามจริง (เป็นค่าก่อนเปลี่ยนของ section ถัดไป) · ถ้า llama-log-size.txt ว่างหรือ 0 คำขอ ให้จดว่าวัดไม่ได้
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-os-snapshot/` · รันซ้ำหลังขั้น 9 ของ runbook (โฟลเดอร์วันใหม่ หรือเติม `-after9` ท้ายชื่อถ้าวันเดียวกัน) แล้ว `diff` dpkg.txt สองไฟล์ ต้องต่างแค่แพ็กเกจที่ขั้น 9 ติดตั้ง (greetd, cage ฯลฯ) · หลังทำ image สอบ diff กับไฟล์ล่าสุดต้องว่าง

### V02 เตรียม shell: ตัวแปรและคำสั่งช่วยที่ทุก section ใช้
- **ตอบข้อ audit:** evidence-9, llm-2 (ทำให้ทุกการวัดตรวจเงื่อนไขระดับ 4 แบบเดียวกัน)
- **ทำไม:** ร่างเดิมเขียน `pgrep ... && echo "หยุด"` ซึ่งไม่หยุดจริง · วนรอ `/health` แบบไม่มีเวลาหมด (server ล้ม = ค้างตลอดไป) · และหลาย section ไม่ได้จดเครื่อง/commit เลย
- **ต้องอยู่หน้าเครื่อง:** ไม่ · **เวลา:** ~5 นาที · **ความเสี่ยง:** ไม่มี (ประกาศตัวแปรและฟังก์ชันใน shell นี้เท่านั้น) · **ย้อนกลับ:** ปิด shell
- **ใช้เมื่อไร:** วางทุกครั้งที่เปิด SSH ใหม่ ก่อน section อื่น
```sh
cd ~/aipc
# repo บน Pi ต้องมี commit ของ PC แล้ว (skill_author route · chat template)
git log --oneline -1
git merge-base --is-ancestor 2c6b690 HEAD && echo "repo ใหม่พอ" || echo "หยุด: ย้าย git bundle จาก PC มาก่อน"
B=~/llama.cpp/build/bin; M=models/typhoon2.5-qwen3-4b-q4_k_m.gguf
TPL=scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja; T=3; LABEL=typhoon25-4b-q4km
L=$(git -C ~/llama.cpp rev-parse --short HEAD); PY=./.venv/bin/python
# ready: ไม่มีงานวัด/ดาวน์โหลดค้าง · git tree สะอาด · อุณหภูมิ < 55°C
ready() {
  if pgrep -af 'llama-server|llama-bench|measure-llm|fetch-models|curl .*huggingface'; then echo "หยุด: มีงานค้าง (ข้างบน)"; return 1; fi
  if [ -n "$(git status --porcelain)" ]; then git status --short; echo "หยุด: git tree ไม่สะอาด"; return 1; fi
  t=$(vcgencmd measure_temp | tr -dc '0-9.')
  if ! awk -v t="$t" 'BEGIN{exit !(t<55)}'; then echo "หยุด: $t°C ยังร้อน รอให้ต่ำกว่า 55"; return 1; fi
  echo "ready: ผ่าน · $t°C · $(vcgencmd get_throttled)"
}
# wait_up <อาร์กิวเมนต์ของ curl>: รอ server พร้อมไม่เกิน 4 นาที · server ล้ม = บอกทันที (ต้องตั้ง P= ก่อน)
wait_up() {
  for i in $(seq 120); do
    curl -sf "$@" >/dev/null 2>&1 && { echo "server พร้อมหลัง ~$((i*2)) วิ"; return 0; }
    kill -0 "$P" 2>/dev/null || { echo "หยุด: llama-server ล้ม (ดู log ใน /tmp)"; return 1; }
    sleep 2
  done; echo "หยุด: server ไม่พร้อมใน 4 นาที"; return 1
}
# เฝ้าความร้อนลง /tmp (ไฟล์ใน repo ระหว่างวัด = dirty) · บิต 0-3 ของ get_throttled = ปัญหาที่เกิดตอนนั้น
thermal_on() { ( while :; do echo "$(date +%T) $(vcgencmd measure_temp) $(vcgencmd get_throttled) fan=$(cat /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input 2>/dev/null)"; sleep 10; done ) > "$1" 2>&1 & MON=$!; }
thermal_off() { kill $MON 2>/dev/null; python3 -c "import sys;b=[l for l in open(sys.argv[1]) if 'throttled=' in l and int(l.split('throttled=')[1].split()[0],16)&0xF];print('throttle ขณะวัด:',len(b),'บรรทัด')" "$1"; }
# snap <ไฟล์ใน /tmp>: เครื่อง + commit + dirty (aipc.bench.machine) + โหลดอื่น เช่น desktop ที่ login ค้าง
snap() { { $PY -c "import json,pathlib;from aipc.bench import machine as m;c,d=m.git_commit(pathlib.Path('.'));t=m.throttled_raw();print(json.dumps({'board':m.board_model(),'ram_mb':m.ram_total_mb(),'temp_c':m.cpu_temp_c(),'throttled':hex(t) if t is not None else None,'commit':c,'dirty':d,'llama_cpp':'$L','threads':$T}))"; uptime; ps -eo pcpu,rss,comm --sort=-pcpu | head -8; } > "$1"; }
ready
```
- **ผ่านเมื่อ:** เห็น `repo ใหม่พอ` และ `ready: ผ่าน` · ถ้าขึ้น "หยุด" ห้ามทำ section ถัดไป แก้ตามข้อความก่อน
- **บันทึกผล:** ไม่มี (ไฟล์ของ `snap` และ `thermal_on` ถูกคัดลงโฟลเดอร์ผลใน section ที่ใช้)
- **หมายเหตุ:** ขณะนี้ measure-llm.sh รอบ 2 กำลังรัน · `ready` จะหยุดให้เองจนกว่าจะจบ

### V03 ข้อมูลประกอบผลวัด LLM (sha256 · llama.cpp · ตัวเลือกของ server · ตัวอักษรไทย/วิ)
- **ตอบข้อ audit:** gaps-4, llm-8 (ส่วนตรวจว่า build นี้มีตัวเลือกอะไร)
- **ทำไมต้องทดสอบ:** ไฟล์คำตอบไทย `docs/benchmarks/2026-09-29-llm-thai/typhoon25-4b-q4km.json` ไม่มี sha256 โมเดล ไม่มีรุ่น llama.cpp ไม่มีข้อมูลเครื่อง และไม่มีตัวอักษรไทยต่อวินาที (ADR-007 บรรทัด 40 สั่งให้รายงาน) · คำนวณบน PC จากไฟล์นี้แล้ว: ตัวอักษร/วิ กลาง 7.7 · อ่าน prompt กลาง 17.9 tok/s · ชน 512 token 0/30 (ยาวสุด 289) · ข้อมูลดิบมาจาก Pi 5 แต่ไฟล์ไม่มีข้อมูลเครื่อง จึงยังไม่นับเป็นระดับ 4 · section นี้ผูกตัวเลขกับไฟล์โมเดลจริงบน Pi
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี (อ่านไฟล์ + อ่าน --help) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** วาง section "เตรียม shell" แล้ว · `ready` ผ่าน (sha256sum อ่านดิสก์หนัก ~2 นาที ห้ามรันคู่กับการวัด)
```sh
ready || echo "หยุด ห้ามรันต่อ"
D=docs/benchmarks/$(date +%F)-pi5-llm-meta; mkdir -p $D
{ git -C ~/llama.cpp rev-parse HEAD; $B/llama-server --version 2>&1 | tail -2; } | tee $D/llama_cpp.txt
# sha256 · ไฟล์ Qwen3-4B-Instruct และ gemma ที่โหลดค้าง = ค่าของไฟล์ไม่ครบ ห้ามใช้อ้างอิง
ls -l models/ | tee $D/models-ls.txt
sha256sum models/*.gguf $TPL | tee $D/sha256.txt
# ตัวเลือกที่ build 86ea01d มีจริง (ใช้ใน section cache · ตัวเลือกความเร็ว · ตัวช่วยร่าง)
$B/llama-server --help 2>&1 | grep -E -- '--parallel|--kv-unified|--cache-reuse|--cache-ram|--flash-attn|--cache-type-k|--model-draft|--slot-prompt-similarity|--no-repack|--threads-batch' | tee $D/server-flags.txt
$B/llama-bench --help 2>&1 | grep -E -- '-fa|-ctk|-ctv|n-depth|--repetitions' | tee $D/bench-flags.txt
# ตัวอักษรไทยต่อวินาที + ความเร็วอ่าน prompt + ชน 512 จากผลคำตอบไทยที่มีแล้ว
$PY - <<'EOF' | tee $D/thai-chars-per-s.txt
import json, glob, statistics as st
for f in sorted(glob.glob('docs/benchmarks/*-llm-thai/*.json')):
    a = json.load(open(f, encoding='utf-8'))['answers']
    t = [x.get('timings') or {} for x in a]
    cps = [len(x['answer']) / (y['predicted_ms'] / 1000) for x, y in zip(a, t) if y.get('predicted_ms')]
    pps = [y['prompt_per_second'] for y in t if y.get('prompt_per_second')]
    hit = sum((x.get('usage') or {}).get('completion_tokens', 0) >= 512 for x in a)
    print(f, 'timings ครบ', len(cps), '/', len(a), '· ตัวอักษร/วิ (กลาง)', round(st.median(cps), 1),
          '· อ่าน prompt tok/s (กลาง)', round(st.median(pps), 1), '· ชน 512 token', hit)
EOF
git add $D && git commit -m "bench(pi5): sha256 โมเดล + รุ่น llama.cpp + ตัวอักษรไทยต่อวินาที"
```
- **ผ่านเมื่อ:** timings ครบ 30/30 · sha256 ของ `typhoon2.5-qwen3-4b-q4_k_m.jinja` = `64f85b198065d0fba2a81f37e10ed68161ce2c19a754c7100e67e0ca2ee9c326` (ตาม `scripts/pi/chat-templates/README.md`) · sha256 ของ `typhoon2.5-qwen3-4b-q4_k_m.gguf` = `b365302922688f3a3c9ac8e3c00ab97a152cac0cdbf4eb5a734ecb483ae3e511` (ค่า `files_sha256` ใน `docs/benchmarks/2026-09-29-pi5-llm-typhoon25-4b-q4km-t3-t3.json`) · ตัวอักษร/วิ 7.7 และอ่าน prompt 17.9 (ต่างจาก PC ไม่เกิน 0.1 = คำนวณถูก) · ชน 512 = 0 · `server-flags.txt` และ `bench-flags.txt` เป็นข้อมูล ไม่ใช่เกณฑ์ผ่าน: จดว่ามี/ไม่มีแต่ละ flag
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-meta/` (llama_cpp.txt · models-ls.txt · sha256.txt · server-flags.txt · bench-flags.txt · thai-chars-per-s.txt) · commit ในคำสั่งข้างบน
- **หมายเหตุ:** ผู้ให้คะแนนคนที่ 2 ของ ADR-007 ข้อ 1 ยังไม่มีชื่อ · ต้องได้ชื่อก่อนตัดสิน ADR-007

### V04 ตัดคำไทย (libthai) และเทสต์หน้าจอบน Pi 5
- **ตอบข้อ audit:** ui-3, ui-9
- **ทำไมต้องทดสอบ:** `AppText.qml` ใช้ `WrapAtWordBoundaryOrAnywhere` · บน Linux ต้องมี libthai ถึงจะตัดตามคำ · ถ้าไม่มีจะตัดกลางคำ · ตอนนี้มีแค่ภาพตรวจบนเครื่องพัฒนา (ระดับ 3) · `tests.test_ui_qml` (warning = 0) ผ่านบนวินโดวส์ แต่ยังไม่มีผลบน Pi 5
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** `measure-llm.sh` รอบ 2 จบและ commit แล้ว · `pgrep -af 'llama-|measure-llm'` ต้องไม่ขึ้นอะไร · ทำ section นี้ก่อน section อื่นของหมวดหน้าจอ
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-ui-thai-wrap; mkdir -p $D
git log --oneline -1 | tee $D/commit.txt
# 1) มี libthai ไหม (ldconfig อยู่ /usr/sbin · -p อ่านได้โดยไม่ต้อง sudo)
/usr/sbin/ldconfig -p | grep libthai | tee $D/libthai.txt
dpkg -l libthai0 | tail -1 | tee -a $D/libthai.txt
# 2) Qt ใน venv หาจุดตัดคำไทยได้ไหม (ประโยคยาว 29 ตัวอักษร)
./.venv/bin/python - <<'EOF' | tee $D/boundaries.txt
from PySide6.QtCore import QTextBoundaryFinder as F
s = "ภาษาไทยไม่มีช่องว่างระหว่างคำ"
f = F(F.BoundaryType.Word, s)
b = list(iter(f.toNextBoundary, -1))
print(b)
print("จำนวนจุดตัด =", len(b), "· มี 1/2/3 =", any(x in b for x in (1, 2, 3)))
EOF
# 3) เทสต์หน้าจอทุกหน้า (offscreen วาดด้วย CPU) ต้องไม่มี warning
./.venv/bin/python -m unittest tests.test_ui_qml -v 2>&1 | tail -5 | tee $D/test-ui-qml.txt
```
- **ผ่านเมื่อ:** (1) เห็น `libthai.so.0` และ dpkg ขึ้น `ii  libthai0` · (2) ตัวสุดท้ายเป็น 29 · `มี 1/2/3 = False` · จำนวนจุดตัด 5–12 (ถ้าได้ 29 จุด `[1, 2, 3, …]` = Qt ไม่ได้ใช้ libthai = ไม่ผ่าน) · (3) บรรทัดท้ายเป็น `OK` ไม่มี FAILED/ERROR
- **หมายเหตุ:** ไม่บังคับว่าต้องได้ 4 กับ 7 เพราะพจนานุกรม libthai อาจนับ "ภาษาไทย" เป็นคำเดียว (ได้ 7 ไม่มี 4)
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): ตัดคำไทย libthai + เทสต์หน้าจอ QML"`

### V05 ภาพรวมความปลอดภัยก่อนเปลี่ยน
- **ตอบข้อ audit:** hw-os-0, hw-os-5, security-0, security-1, security-3, security-4, security-7, vision-6, llm-7
- **ทำไมต้องทดสอบ:** audit 2026-09-29 (ระดับ 4 · `docs/benchmarks/2026-09-29-pi5-image-audit.md`) อ่านแค่ TCP · ไม่ได้ดู UDP การเชื่อมต่อขาออก ค่า sshd และ flag ของ llama-server build 86ea01d · ต้องมีค่า "ก่อน" ไว้เทียบกับทุก section ถัดไป
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** การวัด LLM รอบ 2 ต้องจบแล้ว (สองบรรทัดแรกต้องว่าง) · SSH เข้าในชื่อ aipc2030
```sh
# ต้องไม่มีการวัดค้าง (ว่างทั้งสองบรรทัด)
pgrep -a llama-server; pgrep -af 'measure-llm|llama-bench'
cd ~/aipc
D=docs/benchmarks/$(date +%F)-pi5-security-baseline; mkdir -p "$D"
{
  echo "== เวลา/commit"; date -Is; git log -1 --oneline; git status --porcelain | wc -l
  echo "== linger"; ls /var/lib/systemd/linger
  echo "== logind"; grep -rs KillUserProcesses /etc/systemd/logind.conf /etc/systemd/logind.conf.d/ || echo "ไม่ได้ตั้ง (ค่าเริ่มต้น no)"
  echo "== Pi Connect ของ aipc2030"
  systemctl --user list-unit-files --no-legend 'rpi-connect*'
  systemctl --user is-active rpi-connect.service rpi-connect-wayvnc.service
  dpkg-query -W 'rpi-connect*' 2>&1
  echo "== rpcbind/NFS"; systemctl is-enabled rpcbind.socket rpcbind.service nfs-client.target
  echo "NFS ที่ mount อยู่: $(findmnt -t nfs,nfs4 -n | wc -l)"; echo "nfs ใน fstab: $(grep -c nfs /etc/fstab)"
  apt-cache rdepends --installed rpcbind
  echo "== unit ที่ล้ม: $(systemctl --failed --no-legend | wc -l)"
  echo "== journal เก็บข้ามรอบบูตไหม"; ls -d /var/log/journal 2>&1; echo "รอบบูตที่ journal จำได้: $(journalctl --list-boots --no-pager 2>/dev/null | grep -c .)"
  echo "== พอร์ตที่ฟัง TCP+UDP (มีชื่อโปรเซส)"; sudo ss -tulnpH
  echo "== การเชื่อมต่อขาออกตอนนี้ (ไม่นับ loopback)"; sudo ss -tunpH state established | grep -v -E '127\.0\.0\.1|\[::1\]'
  echo "== RAM ของบริการที่จะปิด (KB)"; ps -eo rss,user,comm | grep -E 'rpi-connect|wayvnc|rpcbind|rpc\.statd'
  echo "== SSH"; systemctl is-enabled ssh.service ssh.socket 2>&1
  sudo sshd -T | grep -Ei '^(passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|permitrootlogin|allowgroups|allowusers)'
  ls -l /etc/ssh/sshd_config.d/
  echo "== สิทธิ์ home เริ่มต้นของ OS"; grep -E '^\s*HOME_MODE' /etc/login.defs; grep -E '^\s*DIR_MODE' /etc/adduser.conf
  echo "== กล้อง/เสียง"; ls -l /dev/v4l/by-id/ /dev/snd/ 2>&1; command -v getfacl || echo "ไม่มี getfacl (ใช้ ls -l ดูเครื่องหมาย + แทน)"
  echo "== llama-server 86ea01d รับตัวเลือกที่ aipc-llm-start ใช้ไหม"
  H=$(~/llama.cpp/build/bin/llama-server --help 2>&1)
  for f in --no-slots --no-webui --chat-template-file .sock; do printf '%s ' "$f"; echo "$H" | grep -qF -- "$f" && echo มี || echo ไม่มี; done
} 2>&1 | tee "$D/baseline.txt"
# audit ของโปรเจกต์ (อ่านอย่างเดียว) · --out = โฟลเดอร์ · ชื่อไฟล์ซ้ำจะหยุดเอง ไม่เขียนทับ
sudo ./.venv/bin/python -m aipc.doctor --audit --save --out "$D"
sudo chown -R "$USER": "$D"
```
- **ผ่านเมื่อ:** ได้ baseline.txt ครบทุกหัวข้อ + ไฟล์ audit .md/.json (section นี้เก็บค่า ไม่มีตก) · ค่าที่คาดไว้ก่อนรัน: linger มี aipc2030 · rpi-connect ทั้ง 2 ตัว enabled · พอร์ต 111 ทั้ง TCP และ UDP · NFS ที่ mount = 0 · **ถ้า flag ใด "ไม่มี" ให้หยุด ห้ามรัน install-llm.sh** (service จะเปิดไม่ขึ้นแล้ววนเปิดใหม่ทุก 3 วิ) · **จดค่า "รอบบูตที่ journal จำได้"**: ถ้าเป็น 1 และไม่มี /var/log/journal = journal ไม่ข้ามรอบบูต (section หน้า Login จดผลทีละรอบแทน)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-security-baseline/` (baseline.txt + ไฟล์ audit) · `git add "$D" && git commit -m "bench(pi5): ภาพรวมความปลอดภัยก่อนปิดบริการ"`

### V06 audit หลัง OOBE
- **ตอบข้อ audit:** security-3, security-4, security-7, hw-os-0, hw-os-5, vision-6
- **ทำไมต้องทดสอบ:** docstring ของ `image_audit.py` บรรทัด 6 บอกว่าหลัง OOBE ต้องผ่านทุกข้อ · ยังไม่มีผล audit หลังติดตั้งบน Pi 5 เลย · ตัวตรวจรุ่นปัจจุบันจะให้ข้อ sudo "ไม่ผ่าน" กับกฎของ aipc เอง (อ่านโค้ด: บรรทัด 40 นับทุกบรรทัดที่มี NOPASSWD) และไม่ได้ดู UDP (บรรทัด 163)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลังทุก section ข้างบน · รอบแรกรันได้เลยด้วยโค้ดเดิม (ยืนยันปัญหา) · รอบสองรันหลังดึงโค้ดที่แก้ตัวตรวจแล้วจาก PC (git bundle) · รีบูตมาแล้วอย่างน้อย 1 ครั้งหลังแก้ sshd
```sh
cd ~/aipc; git log -1 --oneline
D=docs/benchmarks/$(date +%F)-pi5-after-oobe; mkdir -p "$D"   # รอบสองใช้ชื่อ ...-pi5-after-oobe-fixed
sudo ./.venv/bin/python -m aipc.doctor --audit --save --out "$D"
{ sudo ss -tulnpH; sudo sshd -T | grep -i '^allowgroups'; echo "linger: $(ls /var/lib/systemd/linger | wc -l)"
  for u in testa testb testc testd teste; do printf '%s: ' "$u"; id -nG "$u" 2>&1; done; } 2>&1 | tee "$D/ports-ssh.txt"
sudo chown -R "$USER": "$D"
```
- **ผ่านเมื่อ:** รอบแรก (โค้ดเดิม · คาดไว้ก่อนรัน): ข้อ sudo = "ไม่ผ่าน" และแสดงบรรทัด `/etc/sudoers.d/aipc-accounts` = ยืนยันว่าต้องแก้ตัวตรวจ · ข้อ logout = ผ่าน · ข้อ remote = `ssh.service` ตัวเดียว · ข้อ ports = `22/tcp, 22/tcp6` (ไม่มี 111) · รอบสอง (โค้ดที่แก้แล้ว): ไม่มีข้อไหน "ไม่ผ่าน" · ข้อ sudo = ผ่าน (กฎของ aipc ที่ตั้งใจ) · ข้อ ports = `22/tcp, 22/tcp6` + พอร์ต UDP ที่ไม่ใช่ loopback ครบเท่ากับใน ports-ssh.txt (ไม่มี 111) · ข้อ home ผ่าน ≥ 6 โฟลเดอร์ · ข้อกลุ่มสิทธิ์สูง: ชื่อที่ขึ้นใต้ video ต้องตรงกับบัญชีที่ ports-ssh.txt บอกว่าอยู่กลุ่ม video (บัญชีที่สมัครก่อนแก้ GROUPS ยังอยู่ video เป็นเรื่องที่คาดไว้ · จะเหลือแค่ aipc2030 ได้ต่อเมื่อแก้ GROUPS แล้วและเอา video ออกจากบัญชีทดสอบเก่าหรือลบบัญชีเหล่านั้น) · sudo มีแค่ aipc2030 · `allowgroups sudo` ยังอยู่หลังรีบูต (ถ้าเจ้าของเลือกใช้)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-after-oobe/` และ `...-after-oobe-fixed/` · `git add "$D" && git commit -m "bench(pi5): audit หลัง OOBE"`

### V07 ตรวจล็อก llama.cpp และ sha256 โมเดล
- **ตอบข้อ audit:** deploy-3
- **ทำไมต้องทดสอบ:** ผลวัด Pi 5 ทั้ง 2 ไฟล์มี `"llama_cpp": "86ea01d"` และ `files_sha256` ของ Typhoon `b365302922688f3a…e511` (`docs/benchmarks/2026-09-29-pi5-llm-typhoon25-4b-q4km-t3-t3.json`, `…-t4.json`) · แต่ตอนติดตั้งไม่มีอะไรบังคับ (`install-llm.sh:59,77` แค่พิมพ์ออกจอ) · ต้องยืนยันว่าของในเครื่องตรงกับของที่วัด
- **ต้องอยู่หน้าเครื่อง:** ไม่ (SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ต่ำ อ่านอย่างเดียว · อ่านโมเดล 2.5 GB สองชุด ดิสก์ทำงานหนักราว 1–2 นาที · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** วัดรอบ 2 เสร็จและ commit แล้ว · ไม่มีดาวน์โหลดค้าง · ส่วนท้าย (หลัง install-llm) ทำหลังขั้น 9
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-pi5-lock && mkdir -p "$D"
{
echo "== llama.cpp ที่ build ไว้"
git -C ~/llama.cpp rev-parse --short HEAD          # ต้องขึ้นต้นด้วย 86ea01d
git -C ~/llama.cpp status --porcelain | wc -l       # ต้องได้ 0
echo "== llama_cpp ในผลวัดทุกไฟล์"
grep -ho '"llama_cpp": "[0-9a-f]*"' docs/benchmarks/*-pi5-llm-*.json | sort | uniq -c
echo "== sha256 ของโมเดลเทียบกับ files_sha256 ในผลวัด"
./.venv/bin/python - <<'EOF'
import glob, hashlib, json, pathlib
want = {}
for f in glob.glob("docs/benchmarks/*-pi5-llm-*.json"):
    for p, h in json.load(open(f, encoding="utf-8")).get("files_sha256", {}).items():
        want.setdefault(pathlib.Path(p).name, set()).add(h)
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
for d in ("models", "/opt/aipc-models"):
    for p in sorted(pathlib.Path(d).glob("*.gguf")):
        w = want.get(p.name)
        if not w:
            print("ไม่มีในผลวัด (ไม่นับ)", p)
            continue
        print("ตรง" if sha(p) in w else "ไม่ตรง!", p, "· ผลวัดมี", len(w), "ค่า")
EOF
} 2>&1 | tee "$D/check.txt"

# ส่วนท้าย: ทำหลัง install-llm.sh --apply (ขั้น 9) แล้วเท่านั้น
{
echo "== หลัง install-llm"
LD_LIBRARY_PATH=/opt/aipc-llm/lib ldd /opt/aipc-llm/bin/llama-server | grep -E 'not found|/home/' || echo "ldd สะอาด"
LD_LIBRARY_PATH=/opt/aipc-llm/lib /opt/aipc-llm/bin/llama-server --version 2>&1 | head -2
cat /etc/aipc/llm.conf
} 2>&1 | tee -a "$D/check.txt"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) commit ขึ้นต้น `86ea01d` · porcelain = 0 · `uniq -c` มีค่า llama_cpp ค่าเดียวคือ `86ea01d` · Typhoon ขึ้น "ตรง" ทั้งใน `models/` และ `/opt/aipc-models` · ไม่มีบรรทัด "ไม่ตรง!" เลย (ไฟล์ที่โหลดค้าง เช่น Qwen3/gemma ขึ้น "ไม่มีในผลวัด" ได้) · หลัง install-llm: ขึ้น "ldd สะอาด" · `--version` มี `86ea01d` · llm.conf มี `TEMPLATE=/opt/aipc-models/<ชื่อโมเดล>.jinja` (ไม่ว่าง)
- **บันทึกผล:** `git add docs/benchmarks && git commit -m "bench(pi5): ล็อก llama.cpp 86ea01d + sha256 โมเดลตรงกับผลวัด"`

### V08 เช็กเครื่องว่าง + เทียบ LLM รอบ 1 กับรอบ 2
- **ตอบข้อ audit:** evidence-3, evidence-8
- **ทำไมต้องทดสอบ:** กฎระดับ 4 ของ `aipc.bench` ดูแค่บอร์ด, throttle และ git (`src/aipc/bench/runner.py` judge() บรรทัด 144–163) ไม่ดูโหลดของโปรแกรมอื่น · รอบ 1 (2026-09-29) วัดตอนยังดาวน์โหลดโมเดลอื่นอยู่ แต่เครื่องมือให้ระดับ 4 ไฟล์ `-t3-t3` ไปแล้ว จึงต้องเทียบกับรอบ 2 · `skill_select` เขียนทับไฟล์ผลเดิมโดยไม่ถาม (`src/aipc/spikes/skill_select.py` บรรทัด 168–169) และรอบ 2 ใช้ชื่อโฟลเดอร์วันนี้ซ้ำกับรอบแรกของวัน
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~15 นาที (รวมรอ load ลด) · **ความเสี่ยง:** ไม่มี อ่านอย่างเดียว · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** `measure-llm.sh` รอบ 2 จบแล้ว (ขึ้น `เสร็จ: typhoon25-4b-q4km`) · ทำ section นี้ก่อน section อื่น · ท่อนที่ 1 คือ "เช็กเครื่องว่าง" ใช้ซ้ำก่อนทุกการวัด
```sh
cd ~/aipc
# 1) เช็กเครื่องว่าง (ใช้ซ้ำก่อนทุกการวัด)
pgrep -af 'llama-|curl|wget|sha256sum|measure-llm|skill_select|llm_quality|apt|dpkg' || echo ไม่มีงานค้าง
# รอ load 1 นาที < 0.5 (หลังงานหนักจบต้องรอ 3–5 นาที) · รอครบ 15 นาทีแล้วยังไม่ลง = หยุด ดู top ก่อน
for i in $(seq 60); do awk '{exit !($1 < 0.5)}' /proc/loadavg && break; sleep 15; done; cat /proc/loadavg
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # ตอนนี้ ondemand
vcgencmd measure_temp; vcgencmd get_throttled
loginctl list-sessions --no-legend    # desktop ของ aipc2030 ที่ tty1 = โหลดพื้นหลัง จดไว้
git status --porcelain | wc -l        # ต้องได้ 0

# 2) เทียบผล LLM ของ Typhoon ทุกไฟล์ (รอบ 1 = ไฟล์ 2026-09-29)
./.venv/bin/python - <<'EOF' | tee /tmp/llm-rerun-check.txt
import glob, json
for f in sorted(glob.glob('docs/benchmarks/*-pi5-llm-typhoon25-4b-q4km*.json')):
    d = json.load(open(f, encoding='utf-8'))
    m = d['summary_metrics']
    print(f.split('/')[-1], 'L4=%s' % d['verdict']['evidence_level4'],
          'pp=%.2f' % m['pp_tok_s']['median'], 'tg=%.3f' % m['tg_tok_s']['median'],
          'prefill=%.2f' % m['prefill_s']['median'], 'before=%s' % hex(d['throttled_before'] or 0))
EOF

# 3) ผลเลือกสกิลรอบแรกของวันยังอยู่ใน git ไหม (รอบ 2 เขียนทับชื่อเดิม)
git log --oneline -- docs/benchmarks/$(date +%F)-skill-select-pi5
git status --short docs/benchmarks
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ท่อน 1: ไม่มีงานค้าง · load 1 นาที < 0.5 · `git status` = 0 · ท่อน 2: ไฟล์ `-t3-t3` ของรอบ 1 เทียบรอบ 2 ต่างกัน ≤ 5% ทั้ง pp และ tg median → รอบ 1 ใช้ได้ · ต่าง > 5% → ใช้รอบ 2 และเขียนหมายเหตุ "ปนโหลด (ดาวน์โหลดพร้อมกัน)" ในไฟล์ .md ของรอบ 1 · ไฟล์ `-t4` ต้องเป็น `L4=False` · ท่อน 3: `git log` เห็น commit ผลเลือกสกิลรอบแรก ≥ 1 ตัว (ไม่เห็น = ผลแรกหายเพราะถูกทับ ให้จดไว้)
- **บันทึกผล:**
```sh
D=docs/benchmarks/$(date +%F)-pi5-llm-rerun-check; mkdir -p $D
{ date -Is; cat /proc/loadavg; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; loginctl list-sessions --no-legend; } > $D/machine-state.txt
cp /tmp/llm-rerun-check.txt $D/compare.txt
git log --oneline -- docs/benchmarks/$(date +%F)-skill-select-pi5 > $D/skill-select-history.txt
git add $D && git commit -m 'bench(pi5): เทียบ LLM รอบ 1 กับรอบ 2 + สภาพเครื่องตอนวัด'
```

### V09 ความพร้อมก่อนสาธิต: เวลา เขตเวลา จอ และ claude
- **ตอบข้อ audit:** gaps-2, gaps-1
- **ทำไมต้องทดสอบ:** แอปใช้เขตเวลาของ OS (`src/aipc/skills/reminders.py` บรรทัด 37, 56) แต่ `aipc.doctor` ไม่ตรวจเขตเวลา/NTP (`run_all` ใน `src/aipc/doctor/hardware.py` บรรทัด 288–303 ไม่มีข้อเวลา) · หลักฐานตอนนี้เป็นทางอ้อม (commit บน Pi 5 มีเวลา +0700) · doctor 2026-09-29 เตือน RTC `charging_voltage = 0` · ยังไม่รู้ว่า Pi 5 มีคำสั่ง `claude` สำหรับเดโม forge ไหม
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · ต้องเสียบจอที่จะใช้ไว้ก่อน) · **เวลา:** ~5 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ไม่มีการวัดค้าง (ท่อน "เช็กเครื่องว่าง" ของ section แรก)
```sh
cd ~/aipc; F=/tmp/demo-readiness.txt
{
  date -Is
  timedatectl | grep -E 'Time zone|synchronized|NTP service'
  echo rtc_drift_s $(( $(date +%s) - $(cat /sys/class/rtc/rtc0/since_epoch) ))
  echo rtc_charging_uV $(cat /sys/class/rtc/rtc0/charging_voltage 2>/dev/null)
  for d in /sys/class/drm/card*-HDMI-A-*; do echo $d $(cat $d/status) $(head -1 $d/modes 2>/dev/null); done
  grep -lx 1280x720 /sys/class/drm/card*-HDMI-A-*/modes || echo จอนี้ไม่มีโหมด 1280x720
  if command -v claude >/dev/null; then claude --version; else echo ไม่มี claude บน Pi 5; fi
  ls docs/benchmarks/2026-09-29-skill-forge/   # ผล forge ที่บันทึกไว้ = ทางสำรองตอนไม่มีเน็ต
} 2>&1 | tee $F
```
- **ผ่านเมื่อ:** `Time zone: Asia/Bangkok (+07, +0700)` · `System clock synchronized: yes` · `rtc_drift_s` อยู่ระหว่าง −2 ถึง 2 · จอที่ต่อขึ้น `connected` · ข้อมูลเฉย ๆ (ไม่ใช่ผ่าน/ไม่ผ่าน): `rtc_charging_uV` (0 = ไม่ได้ชาร์จแบต RTC), โหมด 1280x720, มี claude ไหม · หมายเหตุ: ตอนมีเน็ต kernel เขียนเวลาลง RTC ให้เอง drift จึงเล็กเสมอ · การทดสอบจริงว่า RTC เก็บเวลาได้ตอนไม่มีเน็ต อยู่ใน section ซ้อมสาธิตรอบ 3 · ไม่มี claude = เดโม forge ใช้ผลที่บันทึกไว้ (ตัดสินก่อนซ้อม)
- **บันทึกผล:**
```sh
D=docs/benchmarks/$(date +%F)-pi5-demo-readiness; mkdir -p $D
cp /tmp/demo-readiness.txt $D/readiness.txt
git add $D && git commit -m 'bench(pi5): ความพร้อมก่อนสาธิต เขตเวลา RTC จอ claude'
```

## B · วัดผล (ไม่เปลี่ยนระบบ · ห้ามมีงานหนักอื่นระหว่างวัด)

### V10 เวลาโหลดโมเดลจาก microSD แบบเย็นและอุ่น
- **ตอบข้อ audit:** hw-os-4, llm-6
- **ทำไมต้องทดสอบ:** ADR-001 ให้ใส่เวลาโหลดจาก microSD ในเล่ม · ตอนนี้มีแค่ "พร้อมหลัง ~N วิ" ที่ measure-llm.sh พิมพ์ออกจอ (ละเอียด 2 วิ · ไฟล์อยู่ใน page cache แล้ว) ไม่มีไฟล์ผล · runbook ขั้น 7.1 ใช้ `sleep 60` แทนการวัด · T7 (AI พังแล้วกลับมาเองใน 60 วิ) ขึ้นกับเวลาโหลดแบบอุ่น
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · อ่านการ์ดหนักช่วงสั้น · `drop_caches` ใช้ sudo แต่ไม่แตะข้อมูล · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section memory cgroup (หรือจด memcg=off) · ไม่มีการวัดอื่นหรือดาวน์โหลด · `git status --porcelain` ว่าง · `vcgencmd get_throttled` ต้องเป็น `throttled=0x0` ถ้าไม่ใช่ให้ `sudo reboot` ก่อน (ไม่มีคนใช้หน้าจอ) เพราะตัววัดตอนนี้มองไม่เห็น throttle ถ้าบิตค้างมาก่อน
```sh
cd ~/aipc; git status --porcelain        # ต้องว่าง
vcgencmd get_throttled                    # ต้อง 0x0
M=models/typhoon2.5-qwen3-4b-q4_k_m.gguf
T=scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja
L=$(git -C ~/llama.cpp rev-parse --short HEAD)
# 1) ความเร็วอ่านการ์ดตรง ๆ (ข้าม page cache) · เก็บนอก repo ระหว่างวัด
dd if=$M of=/dev/null bs=4M iflag=direct 2>&1 | tail -1 | tee ~/sd-read.txt
# 2) ตัวโหลด 1 ครั้ง: ล้าง cache (ถ้า COLD=1) → เปิด llama-server → รอ /health ตอบ 200 → ปิด
cat > /tmp/load-once.sh <<'EOF'
#!/bin/sh
set -eu
M=$1; T=$2
if [ "${COLD:-0}" = 1 ]; then sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null; fi
~/llama.cpp/build/bin/llama-server -m "$M" --chat-template-file "$T" --host 127.0.0.1 --port 8081 \
  -c 4096 -t 3 --no-webui > /tmp/load-once.log 2>&1 &
P=$!
n=0
until curl -sf http://127.0.0.1:8081/health >/dev/null 2>&1; do
  kill -0 $P 2>/dev/null || { echo "llama-server ล้ม" >&2; exit 1; }
  n=$((n + 1)); [ $n -le 3000 ] || { kill $P; echo "เกิน 300 วิ" >&2; exit 1; }
  sleep 0.1
done
kill $P; wait $P 2>/dev/null || true
EOF
sudo -v     # จำรหัส sudo ไว้ 15 นาที ให้ล้าง cache ทุกรอบได้ (พิมพ์รหัสเอง)
./.venv/bin/python -m aipc.bench run --topic llm-load-cold-sd --file $M --meta storage=microSD-SD64G \
  --meta cache=dropped --meta threads=3 --meta llama_cpp=$L -- env COLD=1 sh /tmp/load-once.sh $M $T
git add docs/benchmarks && git commit -m "bench(pi5): เวลาโหลดโมเดลจาก microSD แบบเย็น"
./.venv/bin/python -m aipc.bench run --topic llm-load-warm-sd --file $M --meta storage=microSD-SD64G \
  --meta cache=warm --meta threads=3 --meta llama_cpp=$L -- sh /tmp/load-once.sh $M $T
git add docs/benchmarks && git commit -m "bench(pi5): เวลาโหลดโมเดลแบบอุ่น (page cache)"
# 3) ความเร็วอ่านการ์ด + รุ่นการ์ด
D=docs/benchmarks/$(date +%F)-pi5-sd; mkdir -p $D; cp ~/sd-read.txt $D/
echo "การ์ด SD64G manfid 0x00009f ผลิต 03/2024 58.2G · โหมดบัส: ดูบรรทัด timing spec ใน pi5-os-snapshot/snapshot.txt" > $D/README.md
git add $D && git commit -m "bench(pi5): ความเร็วอ่าน microSD (dd direct)"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ทั้งสองรายงานขึ้น "ใช้เป็นหลักฐานระดับ 4 ได้" · แบบอุ่น median ≤ 57 วิ (T7 60 วิ ลบ RestartSec 3 วิ) · แบบเย็น median ≤ 60 วิ (ค่าเสนอ ตาม `sleep 60` ใน runbook) · ถ้าแบบเย็นเกิน ให้เขียนเป็นข้อจำกัดในเล่ม และยืนยันที่หน้าจอว่าขึ้น "AI กำลังเริ่ม" ระหว่างรอ · เวลาที่วัดรวมการปิด server ด้วย ให้เขียนไว้ในเล่ม · ถ้า sudo -n ล้ม (รหัสหมดอายุ) รอบนั้นหยุดทั้งชุด ให้ `sudo -v` แล้วเริ่มชุดใหม่ (ไฟล์ชื่อซ้ำจะไม่ถูกเขียนทับ ต้องลบไฟล์ที่ไม่สมบูรณ์เองก่อน · ถาม Pakon ก่อนลบ)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-load-cold-sd.*` · `<วันที่>-pi5-llm-load-warm-sd.*` · `<วันที่>-pi5-sd/`

### V11 RAM ของ llama-server ที่ context 4096 ใต้ MemoryMax=4G
- **ตอบข้อ audit:** llm-3, evidence-1 (ADR-007 ข้อ 4), hw-os-2 ส่วน ก
- **ทำไมต้องทดสอบ:** ค่าที่มีตอนนี้ (Pi 5 แต่ prompt สั้น) คือ `docs/benchmarks/2026-09-30-skill-select-pi5/typhoon25-4b-q4km-server-ram.txt`: VmHWM 5,641,872 kB · RssAnon 3,205,808 kB · RssFile 2,433,904 kB (ctx 4096 · threads 4 · prompt ยาวสุด ~1,020 token · ไม่มี MemoryMax) · `peak_rss_mb` 4866 ของ llama-bench ใช้ตัดสินไม่ได้ (context สั้น) · ยังไม่เคยส่ง prompt ≥ 3,000 token และยังไม่เคยรันใต้เพดาน 4G ที่บังคับได้จริง
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · ถ้า hotspot หลุดบ่อย ให้รันที่ terminal หน้าเครื่อง เพราะ SSH หลุด = สคริปต์หยุด) · **เวลา:** ~35 นาที (prompt ยาว 3 ข้อ ข้อละ ~4 นาทีที่ 16 tok/s) · **ความเสี่ยง:** ต่ำ · unit ชั่วคราวของผู้ใช้ หยุดแล้วหาย · เกินเพดาน = unit ถูกปิด ไม่กระทบระบบ · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (`systemctl --user stop aipc-llmram; systemctl --user reset-failed aipc-llmram`)
- **ก่อนเริ่ม:** ทำหลัง section memory cgroup (ถ้าไม่เปิด รันได้ แต่ meta จะขึ้น memcg=off และข้อ MemoryMax ไม่มีความหมาย) · ไม่มีการวัดอื่นหรือดาวน์โหลด · อุณหภูมิ < 55°C · **ก่อนรัน (H9):** Pakon เขียน `PLAN.md` ในโฟลเดอร์ผลแล้ว commit ก่อน ระบุว่า "RAM สูงสุด" ของ ADR-007 ข้อ 4 ใช้ค่าไหน (ค่าเสนอ: RssAnon หลัง prompt ยาว เพราะ VmHWM นับหน้าไฟล์โมเดลที่ mmap ซึ่งเคอร์เนลคืนได้) และหน่วย (3.5 GB = 3,417,969 kB หรือ 3.5 GiB = 3,670,016 kB) · เขียนด้วยว่ารู้ค่าเดิมแล้ว (VmHWM เดิม 5.6 GB ไม่ผ่านแน่นอน) · ADR-007 ค่อยแก้ตามบน PC
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-llm-ram-ctx4096; mkdir -p $D
nano $D/PLAN.md     # นิยาม RAM สูงสุด + หน่วย + เกณฑ์ ตามด้านบน
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์ RAM ctx 4096 ก่อนวัด"
L=$(git -C ~/llama.cpp rev-parse --short HEAD)
M=$PWD/models/typhoon2.5-qwen3-4b-q4_k_m.gguf
T=$PWD/scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja
O=~/ram-ctx4096; mkdir -p $O
vcgencmd get_throttled > $O/throttled-before.txt
# 1) llama-server แบบเดียวกับ service (MemoryMax=4G · Nice=5 · template · ctx 4096) แต่ threads 3 และใช้ TCP ชั่วคราว
systemd-run --user --unit=aipc-llmram -p MemoryMax=4G -p Nice=5 \
  ~/llama.cpp/build/bin/llama-server -m $M --chat-template-file $T \
  --host 127.0.0.1 --port 8080 -c 4096 -t 3 --no-webui
n=0; until curl -sf http://127.0.0.1:8080/health >/dev/null; do
  n=$((n + 1)); [ $n -le 300 ] || { echo "หยุด: server ไม่พร้อมใน 300 วิ"; systemctl --user status aipc-llmram; break; }; sleep 1; done
P=$(systemctl --user show aipc-llmram -p MainPID --value)
CG=/sys/fs/cgroup$(systemctl --user show aipc-llmram -p ControlGroup --value)
snap() { echo "== $1"; grep -E 'VmHWM|VmRSS|RssAnon|RssFile|VmSwap' /proc/$P/status
  echo "memory.max $(cat $CG/memory.max 2>&1) · memory.peak $(cat $CG/memory.peak 2>&1) · swap.peak $(cat $CG/memory.swap.peak 2>&1)"
  cat $CG/memory.events 2>&1; grep -E '^(anon|file) ' $CG/memory.stat 2>&1; free -m; }
snap "หลังโหลด" > $O/ram.txt
# context ต่อ slot จริง (ถ้าน้อยกว่า 4096 = service ก็รับแชทยาวไม่ได้)
curl -s http://127.0.0.1:8080/props | python3 -c "import json,sys; d=json.load(sys.stdin); print('n_ctx ต่อ slot', d.get('default_generation_settings',{}).get('n_ctx'), '· slots', d.get('total_slots'))" | tee -a $O/ram.txt
# 2) prompt ยาว 3 ข้อความไม่ซ้ำกัน · ชุดข้อมูล: 30 คำถามใน tests/data/llm_thai_questions.json (commit แล้ว) คนละลำดับ วนจนได้ ≥ 3,300 token
cat > /tmp/longctx.py <<'EOF'
import json, urllib.request, urllib.error
URL = "http://127.0.0.1:8080"
def post(path, body, timeout=60):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
qs = [q["text"] for q in json.load(open("tests/data/llm_thai_questions.json", encoding="utf-8"))["questions"]]
for k in range(3):
    order = qs[k * 10:] + qs[:k * 10]  # ขึ้นต้นต่างกัน = ไม่ใช้ cache ของข้อก่อน
    text, i = "", 0
    while len(post("/tokenize", {"content": text})["tokens"]) < 3300:
        text += order[i % len(order)] + "\n"
        i += 1
    body = {"messages": [{"role": "user", "content": "สรุปคำถามต่อไปนี้เป็น 3 ข้อสั้น ๆ\n" + text}], "max_tokens": 200}
    try:
        t = post("/v1/chat/completions", body, timeout=1800)["timings"]
        print(json.dumps({"k": k, "prompt_n": t["prompt_n"], "prompt_per_second": t["prompt_per_second"], "predicted_n": t["predicted_n"]}))
    except urllib.error.HTTPError as e:
        print(json.dumps({"k": k, "error": e.code, "body": e.read().decode()[:300]}, ensure_ascii=False))
EOF
python3 /tmp/longctx.py | tee $O/prompts.jsonl
snap "หลัง prompt ยาว 3 ข้อความ" >> $O/ram.txt
systemctl --user show aipc-llmram -p NRestarts -p MemoryPeak >> $O/ram.txt
# บรรทัดใน log ที่บอกขนาด KV, slot และการ repack น้ำหนัก (อธิบายว่าทำไม RssAnon ~3.2 GB)
{ journalctl --user -u aipc-llmram -o cat --no-pager; journalctl _SYSTEMD_USER_UNIT=aipc-llmram.service -o cat --no-pager; } 2>/dev/null \
  | grep -Ei 'n_ctx|n_seq|slot|repack|buffer size|kv' | head -60 > $O/server-log.txt
systemctl --user stop aipc-llmram
vcgencmd get_throttled >> $O/throttled-before.txt
{ journalctl -k -b --no-pager | grep -iE 'out of memory|oom-kill' || echo "ไม่มี OOM ใน kernel log"; } >> $O/ram.txt
cp $O/* $D/
echo "model=$(basename $M) sha256=$(sha256sum $M | cut -c1-64) llama_cpp=$L ctx=4096 threads=3 repo=$(git rev-parse --short HEAD) memcg=$(grep -qw memory /sys/fs/cgroup/cgroup.controllers && echo on || echo off)" > $D/meta.txt
git add $D && git commit -m "bench(pi5): RAM llama-server ctx 4096 prompt ~3300 token ใต้ MemoryMax=4G"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ทั้ง 3 ข้อความมี `prompt_n` ≥ 3,000 และไม่มี error (ได้ HTTP 400 หรือ n_ctx ต่อ slot < 4096 = ไม่ผ่าน · ต้องแก้ค่า slot ใน aipc-llm-start) · memory.events มี `oom_kill 0` · NRestarts=0 · ไม่มี OOM ใน kernel log · ADR-007 ข้อ 4: ค่าตามนิยามใน PLAN.md ≤ เกณฑ์ที่ประกาศ · จดทั้ง VmHWM, RssAnon, RssFile, VmSwap, memory.peak เสมอ ไม่ว่าจะใช้ค่าไหนตัดสิน · ถ้า memcg=off ให้จดว่าข้อ oom_kill/memory.peak วัดไม่ได้
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-ram-ctx4096/` (PLAN.md, ram.txt, prompts.jsonl, server-log.txt, throttled-before.txt, meta.txt) · ทำซ้ำกับโมเดลอื่นเมื่อโหลดครบ (เปลี่ยน M/T และชื่อโฟลเดอร์ · ประกาศ PLAN.md ใหม่)

### V12 soak 10 นาที ความร้อน พัดลม และไฟ
- **ตอบข้อ audit:** hw-os-3, hw-os-8 (ไฟตอนโหลดเต็ม), hw-os-9 (ความถี่/governor), evidence-1 (ADR-007 ข้อ 5)
- **ทำไมต้องทดสอบ:** ยังไม่เคย soak บน Pi 5 · วันนี้ threads 4 throttle ทุกรอบ (พัดลม pwm 250/255 · ชิป 78.5–81.5°C · get_throttled 0xe0000) และ t3 อยู่ที่ 77–79°C (`2026-09-29-pi5-llm-typhoon25-4b-q4km-t3-t3.csv`) · ADR-007 ข้อ 5 ต้องการ get_throttled = 0x0 ซึ่งตรวจได้เฉพาะหลังบูตใหม่
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · ถ้า hotspot หลุดบ่อย ให้รันที่ terminal หน้าเครื่อง · SSH หลุดกลางทาง = ผลรอบนั้นใช้ไม่ได้) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · ชิปร้อน ~80°C ช่วงสั้น (firmware ลดความเร็วเองเพื่อกันเสียหาย) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section RAM และโหลดโมเดล · **ต้องรีบูตก่อน** (ไม่มีคนใช้หน้าจอ) ให้ get_throttled = 0x0 · รอให้เย็น < 52°C · ไม่มีงานอื่น (desktop ของ Pi OS ที่เปิดอยู่ ให้จดใน meta) · แก้ค่า ROOM และ CASE ในบรรทัดแรกให้ตรงจริงก่อนรัน
```sh
ROOM="ใส่อุณหภูมิห้อง"; CASE="ใส่ เปิดฝา หรือ ปิดฝา"     # แก้ให้ตรงก่อนรัน
vcgencmd get_throttled     # ต้องได้ throttled=0x0 · ถ้าไม่ใช่ ให้ sudo reboot ก่อน
vcgencmd measure_temp      # ต้อง < 52°C
cd ~/aipc; git status --porcelain   # ต้องว่าง
M=models/typhoon2.5-qwen3-4b-q4_k_m.gguf; D=docs/benchmarks/$(date +%F)-pi5-soak-t3
./.venv/bin/python -m aipc.bench machine > ~/soak-machine.json   # สภาพเครื่องก่อนเริ่ม (repo สะอาด)
# 1) ตัวบันทึกทุก 5 วิ: อุณหภูมิ ความถี่ throttled พัดลม pwm ไฟ 5V (อ่านอย่างเดียว · เก็บนอก repo)
cat > /tmp/thermal.sh <<'EOF'
#!/bin/sh
H=$(ls -d /sys/devices/platform/cooling_fan/hwmon/hwmon* | head -1)
printf 'time\ttemp_c\tfreq_mhz\tthrottled\tfan_rpm\tpwm\text5v\n'
while :; do
  t=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
  f=$(( $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) / 1000 ))
  th=$(vcgencmd get_throttled | cut -d= -f2)
  v=$(vcgencmd pmic_read_adc EXT5V_V | sed 's/.*=//; s/V$//')
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date +%T)" "$t" "$f" "$th" "$(cat $H/fan1_input)" "$(cat $H/pwm1)" "$v"
  sleep 5
done
EOF
sh /tmp/thermal.sh > ~/soak-thermal.tsv & S=$!
# 2) soak 10 นาที threads 3 (threads 4 throttle ทุกรอบแล้ว ไม่ต้องลอง)
./.venv/bin/python -m aipc.spikes.llm --bench ~/llama.cpp/build/bin/llama-bench --model $M \
  --label typhoon25-4b-q4km --size 3-4b --threads 3 --soak-minutes 10 --out $D | tee ~/soak-summary.txt
kill $S
vcgencmd get_throttled | tee -a ~/soak-summary.txt
# 3) เก็บผล (โหมด soak ยังไม่บันทึก commit/sha256/--meta เอง จึงเก็บแยก)
cp ~/soak-thermal.tsv ~/soak-summary.txt ~/soak-machine.json $D/
sha256sum $M > $D/model.sha256
echo "llama_cpp=$(git -C ~/llama.cpp rev-parse --short HEAD) governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) room_c=$ROOM case=$CASE cooler=Active-Cooler psu=27W desktop=<เปิด/ไม่เปิด>" > $D/meta.txt
awk -F'\t' 'NR>1{if(max==""||$2+0>max)max=$2+0; if(minv==""||$7+0<minv)minv=$7+0} END{print "อุณหภูมิสูงสุด",max,"· 5V ต่ำสุด",minv}' $D/soak-thermal.tsv | tee -a $D/meta.txt
awk -F'\t' 'NR>1 && $4=="0x0"{n++; if($3>=2400)h++} END{printf "แถวที่ไม่ throttle %d · ที่ 2400 MHz %d (%.0f%%)\n", n, h, n?100*h/n:0}' $D/soak-thermal.tsv | tee -a $D/meta.txt
git add $D && git commit -m "bench(pi5): soak 10 นาที typhoon25 threads 3 + ความร้อน/ไฟ"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน · ADR-007 ข้อ 5) ทุกแถวใน `...-llm-typhoon25-4b-q4km-t3-soak.csv` คอลัมน์ throttled = 0 · get_throttled หลังจบ = 0x0 · summary บอก "ลดลง" ≤ 10% · hw-os-8: ไม่มีค่า throttled ที่มีบิต 0x10000 หรือ 0x1 ตลอดไฟล์ tsv และ 5V ต่ำสุด ≥ 4.8 V (ค่าเสนอ) · hw-os-9: ถ้าแถวที่ไม่ throttle อยู่ที่ 2400 MHz ≥ 90% (ค่าเสนอ) แปลว่า ondemand ให้ความถี่สูงสุดอยู่แล้ว ไม่ต้องลอง governor performance (จดเป็นเหตุผล) · ถ้าต่ำกว่า ให้ประกาศการทดสอบ governor performance เป็นการทดสอบใหม่ · ถ้าไม่ผ่านที่ t3: จดเป็นผลไม่ผ่าน ห้ามรันซ้ำจนผ่าน · ทางเลือกต่อ (threads 2, ตรวจการติด cooler, ลดอุณหภูมิห้อง) ต้องประกาศเป็นการทดสอบใหม่ก่อนวัด
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-soak-t3/` (CSV จาก aipc.spikes.llm, soak-thermal.tsv, soak-summary.txt, soak-machine.json, model.sha256, meta.txt) · ผลนี้ใช้เลือก `--threads` ของ install-llm.sh ในขั้น 9 (ค่าเริ่มต้นของสคริปต์คือ 4)

### V13 เลือกสกิลแบบ AI ก่อน วัด 3 รอบให้เป็นระดับ 4
- **ตอบข้อ audit:** llm-0, skills-0, skills-2, evidence-9, skills-6 (ตัวเลขแยกตามสกิล)
- **ทำไมต้องทดสอบ:** ปัญหา "กฎก่อนมีเพดาน" ของ llm-0/skills-0 แก้แล้วใน b784515 (แอปใช้ `router.route_ai_first` เมื่อ AI พร้อม · `backend.py` บรรทัด 697) · ผลบน Pi 5 ที่มี: AI ก่อน ถูก 50/58 เรียกผิด 0/18 ทั้ง 2 วัน แต่ไฟล์ ai-first ทั้ง 2 วันมี `machine.dirty: true` (ไฟล์ rules-first ยังไม่ commit ตอนวัด) และวัดที่ `-t 4` ซึ่ง throttle → ยังไม่ใช่ระดับ 4 · วัดรอบเดียว n=58 ช่วงความเชื่อมั่นกว้าง (≈ ±10 จุด) · ข้อที่พลาด 8 ข้อ (สรุป 3 · แปล 5) AI ตอบเองทุกข้อ · ชน 48 token แค่ 2 ข้อ (`predicted_n` 48) อีก 6 ข้อจบเองก่อน 48 · จึงต้องดูว่าแอปจริง (stream 512 token) ได้ผลต่างไหม
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~60 นาที (3 รอบ × ~10 นาที + ข้อแรก ~60 วิ + stream 8 ข้อ ~15 นาที) · **ความเสี่ยง:** ต่ำ · CPU เต็ม · server ฟังแค่ 127.0.0.1 ชั่วคราว · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** measure-llm.sh รอบ 2 จบแล้ว · วาง section "เตรียม shell" · `ready` ผ่าน · ถ้าอยากให้บิตค้างของ `get_throttled` เป็น 0 ให้รีบูตก่อน (เฉพาะตอนไม่มีคนใช้จอ) · desktop ที่ login ค้างนับเป็นโหลด (`snap` จดให้)

ขั้น 1 ประกาศเกณฑ์ (H9) · ถ้า `ready` ไม่ผ่าน อย่าวางต่อ:
```sh
ready
D=docs/benchmarks/$(date +%F)-skill-select-pi5-3runs; mkdir -p $D
cat > $D/README.md <<EOF
# เลือกสกิลแบบ AI ก่อน วัด 3 รอบ (ประกาศก่อนวัด $(date +%F))
- ชุดประโยค: tests/data/skill_selection.json 58 ข้อ (ไม่แก้)
- server: llama-server -c 4096 -t $T --chat-template-file $TPL · llama.cpp $L
- ตัววัด: python -m aipc.spikes.skill_select --mode ai-first (router.route_ai_first ตัวเดียวกับแอป)
- ผ่าน ADR-007 ข้อ 6: ทุกรอบ ถูก >= 47/58 และเรียกผิด <= 1/18
- เป็นระดับ 4 เมื่อ: machine.dirty = false ทุกไฟล์ และ thermal.log ไม่มี throttle ขณะวัด
- ตรวจเพิ่ม: ชื่อเครื่องมือที่ไม่มีจริง = 0 · correct 3 รอบต่างกัน <= 3 · เส้นทาง stream: reason ว่าง และไม่มีข้อความดิบของ tool call หลุด
- แยกตามสกิล: summarize-text / letter-writer / translate เทียบ >= 7/8 (รายงาน ไม่ใช่เกณฑ์ ADR)
EOF
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์เลือกสกิล AI ก่อน 3 รอบ"
```
ขั้น 2 วัด:
```sh
snap /tmp/3runs-machine-before.txt
$B/llama-server -m $M --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t $T --no-webui > /tmp/llama-3runs.log 2>&1 & P=$!
wait_up http://127.0.0.1:8080/health
thermal_on /tmp/thermal-3runs.log
# 3 รอบ · commit หลังทุกรอบ (ไม่ commit = รอบถัดไป dirty)
for i in 1 2 3; do
  $PY -m aipc.spikes.skill_select --label $LABEL-run$i --server http://127.0.0.1:8080 \
      --mode ai-first --out $D/$LABEL-ai-first-run$i.json
  git add $D && git commit -q -m "bench(pi5): เลือกสกิล AI ก่อน $LABEL รอบ $i"
done
# ข้อที่พลาดในรอบ 1: ลองเส้นทางจริงของแอป (client.Stream · 512 token)
D=$D $PY - <<'EOF' | tee /tmp/stream-check.txt
import json, os
from aipc.chat import client
from aipc.skills import catalog, manifest
f = os.path.join(os.environ['D'], 'typhoon25-4b-q4km-ai-first-run1.json')
rows = [r for r in json.load(open(f, encoding='utf-8'))['rows'] if r['by'] == 'ai' and not r['ok']]
tools = catalog.tools(manifest.load_builtin(), {'llm'})
t = client.Target(url='http://127.0.0.1:8080')
for r in rows:
    msgs, _ = client.fit_context(catalog.SYSTEM + catalog.TOOLS_HINT, [{'role': 'user', 'content': r['text']}])
    x = client.Stream(t, msgs, tools=tools).run(lambda tok: None)
    leak = '<tool_call>' in x.text or '"name"' in x.text
    print(r['expect'], '| ตัววัด 48:', r['got'], r['timings'].get('predicted_n'), '| แอป 512:', x.tool_call or 'none',
          '| reason', repr(x.reason), '| หลุด', leak, '|', r['text'][:30])
EOF
kill $P; thermal_off /tmp/thermal-3runs.log | tee /tmp/throttle-3runs.txt
cp /tmp/thermal-3runs.log $D/thermal.log; cp /tmp/throttle-3runs.txt $D/throttle.txt
cp /tmp/stream-check.txt /tmp/3runs-machine-before.txt $D/
# สรุปต่อรอบ + แยกตามสกิล
D=$D $PY - <<'EOF' | tee $D/summary.txt
import json, glob, os, collections
for f in sorted(glob.glob(os.path.join(os.environ['D'], '*-run?.json'))):
    d = json.load(open(f, encoding='utf-8')); ai = [r for r in d['rows'] if r['by'] == 'ai']
    unknown = [r['raw_tool'] for r in ai if r['raw_tool'] and r['got'] == 'none']
    per = collections.defaultdict(lambda: [0, 0])
    for r in d['rows']:
        per[r['expect']][0] += r['ok']; per[r['expect']][1] += 1
    print(os.path.basename(f), 'ถูก', d['correct'], '/58 · เรียกผิด', d['false_calls'], '/18 · median', d['ai_seconds_median'],
          'วิ · ข้อแรก', d['ai_seconds_first'], 'วิ · dirty', d['machine']['dirty'], '· ชื่อที่ไม่มีจริง', unknown)
    print('   ', dict(d['by_kind']), {k: f'{a}/{b}' for k, (a, b) in per.items()})
EOF
git add $D && git commit -m "bench(pi5): สรุปเลือกสกิล AI ก่อน 3 รอบ + เส้นทาง stream"
```
- **ผ่านเมื่อ:** (ประกาศใน README ก่อนรัน) ทุกรอบ ถูก ≥ 47/58 และเรียกผิด ≤ 1/18 · `dirty False` ทั้ง 3 ไฟล์ · `throttle ขณะวัด: 0 บรรทัด` · ชื่อที่ไม่มีจริง = [] ทุกรอบ · correct สูงสุด−ต่ำสุด ≤ 3 · stream-check: `หลุด False` และ `reason ''` ทุกบรรทัด · จดจำนวนข้อที่ "แอป 512" เรียกสกิลถูกแต่ "ตัววัด 48" ได้ none (ไม่แก้ผลย้อนหลัง · ถ้า > 0 ให้ประกาศ max_tokens ใหม่ก่อนวัดรอบถัดไป) · แยกตามสกิล: จด summarize-text, letter-writer, translate เทียบ ≥ 7/8 (ผลเดิม 5/8, 8/8, 3/8)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-skill-select-pi5-3runs/` (README.md · 3 ไฟล์ run · thermal.log · throttle.txt · stream-check.txt · 3runs-machine-before.txt · summary.txt) · commit อยู่ในคำสั่งแล้ว

### V14 เวลาถึงคำแรกของแชทจริง (มีรายการสกิล) แบบเย็นและแบบอุ่นก่อน
- **ตอบข้อ audit:** llm-1, skills-1
- **ทำไมต้องทดสอบ:** ADR-007 ข้อ 2 วัดแค่ prompt 200 token ไม่มีสกิล (Typhoon t3 ใช้ 12.3 วิ · ระดับ 4) · prompt จริงที่มีรายการสกิล ≈ 1,020 token · ไฟล์ `2026-09-30-skill-select-pi5/typhoon25-4b-q4km-rules-first.json` (dirty false): ข้อแรกหลังเปิด server ใช้ 60.3 วิ ข้อต่อไป median 10.67 วิ (`cache_n` 972) · ยังไม่เคยวัดผ่าน Unix socket แบบแอป และยังไม่รู้ว่าอุ่น cache ตอน login ช่วยได้ไหม · งบ 3,000 ของ `fit_context` ไม่นับรายการสกิล (4096 − 512 − 1,020 = 2,564 < 3,000)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · socket อยู่ใน /tmp/aipc-ttft (0700) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (`rm -rf /tmp/aipc-ttft` ในคำสั่งท้าย)
- **ก่อนเริ่ม:** วาง section "เตรียม shell" · `ready` ผ่าน · ทำต่อจาก section "เลือกสกิลแบบ AI ก่อน 3 รอบ" ได้เมื่อเครื่องเย็นลง

ขั้น 1 ประกาศเกณฑ์:
```sh
ready
D=docs/benchmarks/$(date +%F)-pi5-chat-ttft; mkdir -p $D
cat > $D/README.md <<'EOF'
# เวลาถึงคำแรกของแชทที่มีรายการสกิล (ประกาศก่อนวัด)
- server แบบ aipc-llm-start: Unix socket · --no-slots · -c 4096 · -t 3 · template ต้นฉบับ · ไม่ใส่ -np
- cold = server เพิ่งเปิดแล้วพิมพ์ข้อความแรก · warmup = ส่ง system+รายการสกิล max_tokens 1 ก่อน 1 ครั้ง
- ผ่าน: cold ข้อ 2-3 prompt_s <= 10 · warmup ข้อ 1 prompt_s <= 10 (= หลักฐานให้ทำ code fix อุ่นตอน login)
- จด: cold ข้อ 1 prompt_n และ prompt_s (คาดว่า ~60 วิ) · seconds ของ warmup-request
- ทุกบรรทัด reason = "" และ leak = false
- 4096 - 512 - prompt_n(cold ข้อ 1) < 3000 = ยืนยัน code fix ให้ fit_context นับรายการสกิล
EOF
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์เวลาถึงคำแรกของแชทที่มีรายการสกิล"
```
ขั้น 2 วัด:
```sh
SD=/tmp/aipc-ttft; mkdir -p -m 0700 $SD; SOCK=$SD/llm.sock; EXTRA=""
start() { rm -f $SOCK; $B/llama-server -m $M --chat-template-file $TPL --host $SOCK -c 4096 -t $T --no-webui --no-slots $EXTRA > /tmp/ttft-$1.log 2>&1 & P=$!; wait_up --unix-socket $SOCK http://x/health; }
cat > /tmp/probe-ttft.py <<'EOF'
import json, sys, time
from aipc.chat import client
from aipc.skills import catalog, manifest
sock, mode = sys.argv[1], sys.argv[2]
t = client.Target(sock=sock)
tools = catalog.tools(manifest.load_builtin(), {'llm'})
system = catalog.SYSTEM + catalog.TOOLS_HINT
def show(d):
    print(json.dumps(d, ensure_ascii=False), flush=True)
if mode == 'warmup':  # แบบที่แอปอาจทำตอน login: ส่วนต้นคงที่ + max_tokens 1
    c = t.connect(900)
    body = {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'สวัสดี'}],
            'tools': tools, 'tool_choice': 'auto', 'max_tokens': 1, 'cache_prompt': True}
    s = time.monotonic()
    c.request('POST', '/v1/chat/completions', body=json.dumps(body), headers={'Content-Type': 'application/json'})
    tm = json.loads(c.getresponse().read()).get('timings', {}); c.close()
    show({'mode': 'warmup-request', 'prompt_n': tm.get('prompt_n'), 'seconds': round(time.monotonic() - s, 1)})
for text in ('คอมหน่วงมาก เปิดอะไรก็รอนาน เป็นอะไร',
             'อยากบอกเพื่อนต่างชาติว่ายินดีต้อนรับสู่เชียงใหม่ ต้องพูดยังไง',
             'เครื่องบินลำแรกของโลกบินได้เมื่อไร'):
    msgs, _ = client.fit_context(system, [{'role': 'user', 'content': text}])
    s = time.monotonic(); first = []
    r = client.Stream(t, msgs, tools=tools).run(lambda tok: first or first.append(time.monotonic() - s))
    tm = r.timings
    show({'mode': mode, 'text': text[:24], 'reason': r.reason, 'tool': r.tool_call,
          'prompt_n': tm.get('prompt_n'), 'cache_n': tm.get('cache_n'),
          'prompt_s': round(tm.get('prompt_ms', 0) / 1000, 1),
          'first_token_s': round(first[0], 1) if first else None,  # AI เรียกสกิล = ไม่มี token ข้อความ → None
          'total_s': round(time.monotonic() - s, 1),
          'leak': '<tool_call>' in r.text or '"name"' in r.text})
EOF
snap /tmp/ttft-machine-before.txt; thermal_on /tmp/ttft-thermal.log
# 1) เย็น: server เพิ่งเปิด = ผู้ใช้เพิ่ง login แล้วพิมพ์ข้อความแรก
start cold && $PY /tmp/probe-ttft.py $SOCK cold | tee /tmp/ttft.jsonl; kill $P; wait $P 2>/dev/null
# 2) อุ่นก่อน: ส่งส่วนต้นคงที่ 1 ครั้ง แล้วจึงพิมพ์ข้อความแรก
start warm && $PY /tmp/probe-ttft.py $SOCK warmup | tee -a /tmp/ttft.jsonl; kill $P; wait $P 2>/dev/null
thermal_off /tmp/ttft-thermal.log | tee /tmp/ttft-throttle.txt
# 3) slot และ context ต่อ slot ที่ build นี้ตั้งให้เอง (aipc-llm-start ไม่ได้ใส่ -np)
grep -iE 'n_slots|n_ctx_slot|n_ctx|kv_unified|cache_ram|parallel' /tmp/ttft-cold.log | head -20 > /tmp/ttft-slots.txt; cat /tmp/ttft-slots.txt
cp /tmp/ttft.jsonl /tmp/ttft-slots.txt /tmp/probe-ttft.py /tmp/ttft-machine-before.txt /tmp/ttft-thermal.log /tmp/ttft-throttle.txt $D/
git add $D && git commit -m "bench(pi5): เวลาถึงคำแรกของแชทที่มีรายการสกิล (เย็น/อุ่นก่อน)"
rm -rf $SD
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนวัด) cold ข้อ 2–3 `prompt_s` ≤ 10 · warmup ข้อ 1 `prompt_s` ≤ 10 · ทุกบรรทัด `reason` = "" และ `leak` = false · จด `prompt_n`/`prompt_s` ของ cold ข้อ 1 และ `seconds` ของ warmup-request · ถ้า `ttft-slots.txt` แสดง n_slots > 1 และ n_ctx_slot < 4096 → เพิ่ม code fix ใส่ `-np 1` ใน aipc-llm-start · 4096 − 512 − prompt_n(cold ข้อ 1) < 3,000 = ยืนยัน code fix เรื่อง fit_context · throttle ขณะวัด 0 บรรทัด และ `dirty` ใน ttft-machine-before.txt = false จึงใช้เป็นระดับ 4
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-chat-ttft/` (README.md · ttft.jsonl · ttft-slots.txt · probe-ttft.py · ttft-machine-before.txt · ttft-thermal.log · ttft-throttle.txt) · commit อยู่ในคำสั่งแล้ว

### V15 cache หลังสลับไปใช้สกิลและหลังเริ่มตัดประวัติ
- **ตอบข้อ audit:** llm-2
- **ทำไมต้องทดสอบ:** ยังไม่มีหลักฐานเลย (เทสต์บน PC ใช้ server ปลอม) · สกิลแปล/สรุป/จดหมายส่ง prompt ของสกิลเองโดยไม่มีรายการสกิล (`backend.py` บรรทัด 943) · แชทส่ง SYSTEM+HINT+รายการสกิล+ประวัติ (บรรทัด 945–946) · `fit_context` ตัดข้อความเก่าสุดทีละข้อ (`client.py` บรรทัด 163–179) ส่วนต้นของประวัติจึงเปลี่ยนทุกข้อความ · ถ้า cache หาย แต่ละข้อความต้องอ่านใหม่ ~2,500–3,000 token ≈ 3 นาทีที่ 16 tok/s
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~60 นาที (ถ้า cache หายทุกข้อความจะนานกว่านี้) · **ความเสี่ยง:** ต่ำ · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section "ข้อมูลประกอบ" (รู้ว่ามี `--cache-reuse` / `--kv-unified` ไหม) · วาง section "เตรียม shell" · `ready` ผ่าน

ขั้น 1 ประกาศเกณฑ์:
```sh
ready
D=docs/benchmarks/$(date +%F)-pi5-llm-cache; mkdir -p $D
cat > $D/README.md <<'EOF'
# cache ของ prompt หลังสลับสกิลและหลังตัดประวัติ (ประกาศก่อนวัด)
- บทสนทนาคงที่ใน probe-cache.py: แชท 12 ข้อความ · หลังข้อ 3 สลับไปสกิลแปล 1 ครั้ง · max_tokens 8
- ผ่าน (1): chat4 prompt_n <= 2 เท่าของ chat3 = cache อยู่รอดหลังสลับสกิล
- ผ่าน (2): ข้อความแรกที่ cut = true และข้อความถัดไป prompt_s <= 10
- ผ่าน (3): ไม่มี reason = error หรือ crashed · ถ้า detail = "AI ตอบรหัส 400" = context เกินจริง → ยืนยัน code fix fit_context
- ถ้า (1) หรือ (2) ไม่ผ่าน: ลองตัวเลือกทีละตัว (เฉพาะที่ server-flags.txt บอกว่ามี) บันทึกแยกไฟล์ · เกณฑ์เดิม
EOF
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์ cache หลังสลับสกิลและตัดประวัติ"
```
ขั้น 2 วัด:
```sh
SD=/tmp/aipc-cache; mkdir -p -m 0700 $SD; SOCK=$SD/llm.sock; EXTRA=""
start() { rm -f $SOCK; $B/llama-server -m $M --chat-template-file $TPL --host $SOCK -c 4096 -t $T --no-webui --no-slots $EXTRA > /tmp/cache-$1.log 2>&1 & P=$!; wait_up --unix-socket $SOCK http://x/health; }
cat > /tmp/probe-cache.py <<'EOF'
import json, sys, time
from aipc.chat import client
from aipc.skills import catalog, manifest
client.MAX_TOKENS = 8   # วัดเวลาอ่าน prompt · ไม่ต้องรอคำตอบยาว
t = client.Target(sock=sys.argv[1])
sk = {m.id: m for m in manifest.load_builtin()}
tools = catalog.tools(list(sk.values()), {'llm'})
system = catalog.SYSTEM + catalog.TOOLS_HINT
conv = []
def send(step, sysm, hist, tl):
    msgs, cut = client.fit_context(sysm, hist)
    s = time.monotonic()
    r = client.Stream(t, msgs, tools=tl, timeout=1800).run(lambda tok: None)
    tm = r.timings
    print(json.dumps({'step': step, 'cut': cut, 'sent': len(msgs) - 1, 'chars': sum(len(m['content']) for m in msgs),
        'reason': r.reason, 'detail': r.detail[:60], 'prompt_n': tm.get('prompt_n'), 'cache_n': tm.get('cache_n'),
        'prompt_s': round(tm.get('prompt_ms', 0) / 1000, 1), 'total_s': round(time.monotonic() - s, 1)}, ensure_ascii=False), flush=True)
for i in range(12):
    conv.append({'role': 'user', 'content': f'ข้อ {i}: ' + 'ช่วยเล่าวิธีปลูกผักสวนครัวบนระเบียงคอนโดให้ละเอียด ' * 10})
    send(f'chat{i}', system, conv, tools)
    conv.append({'role': 'assistant', 'content': 'ได้ครับ เริ่มจากเลือกกระถางและดินให้เหมาะ ' * 5})
    if i == 3:  # สลับไปสกิลแปลแบบที่แอปทำ: prompt ของสกิล + ข้อความล่าสุด · ไม่มีรายการสกิล
        conv.append({'role': 'user', 'content': 'แปลเป็นอังกฤษ: ขอบคุณที่มาร่วมงานวันนี้'})
        send('skill-translate', sk['translate'].prompt, conv[-1:], [])
        conv.append({'role': 'assistant', 'content': 'Thank you for joining us today.'})
EOF
snap /tmp/cache-machine-before.txt; thermal_on /tmp/cache-thermal.log
# 1) ค่าเริ่มต้นของ build นี้ (แบบที่แอปใช้ตอนนี้)
EXTRA=""; start default && $PY /tmp/probe-cache.py $SOCK | tee /tmp/cache-default.jsonl; kill $P; wait $P 2>/dev/null
grep -iE 'n_slots|n_ctx_slot|kv_unified|cache_ram|cache_reuse|similarity' /tmp/cache-default.log | head -20 > /tmp/cache-slots.txt
# 2) ถ้าข้อ 1 ไม่ผ่าน: ลองทีละตัวเลือกที่มีจริง แล้วรันซ้ำ เช่น
#    EXTRA="--cache-reuse 256"; start reuse && $PY /tmp/probe-cache.py $SOCK | tee /tmp/cache-reuse.jsonl; kill $P; wait $P 2>/dev/null
thermal_off /tmp/cache-thermal.log | tee /tmp/cache-throttle.txt
cp /tmp/cache-*.jsonl /tmp/cache-slots.txt /tmp/probe-cache.py /tmp/cache-machine-before.txt /tmp/cache-thermal.log /tmp/cache-throttle.txt $D/
git add $D && git commit -m "bench(pi5): cache ของ prompt หลังสลับสกิลและหลังตัดประวัติ"
rm -rf $SD
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนวัด) (1) `chat4` มี `prompt_n` ≤ 2 เท่าของ `chat3` (2) บรรทัดแรกที่ `cut: true` และบรรทัดถัดไปมี `prompt_s` ≤ 10 (3) ไม่มี `reason` = "error" หรือ "crashed" · throttle ขณะวัด 0 บรรทัด · ถ้าข้อ 1 หรือ 2 ไม่ผ่าน ให้ลองตัวเลือกทีละตัวแล้วบันทึกแยกไฟล์ · แก้โค้ดตัดประวัติ (เช่นตัดครั้งละครึ่ง) ทำบน PC ภายหลัง
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-cache/` (README.md · cache-default.jsonl · cache-slots.txt · probe-cache.py · cache-machine-before.txt · cache-thermal.log · cache-throttle.txt · ไฟล์ของตัวเลือกที่ลอง) · commit อยู่ในคำสั่งแล้ว

### V16 ข้อความยาว: ความเร็วอ่าน prompt 1000/2000 token และตอนเกิน context
- **ตอบข้อ audit:** llm-4, skills-4
- **ทำไมต้องทดสอบ:** มีแค่ pp ที่ 200 token (ระดับ 4 · 16.26 tok/s) · BRIEF 5.4 ให้รายงานที่ 2,000 token ด้วย · บน PC ยืนยันแล้ว (ระดับ 3) ว่า `fit_context` เก็บข้อความเดียวที่ยาวเกินไว้ทั้งก้อน และได้ `trimmed=False` · `Stream` ไม่อ่าน `finish_reason` · ยังไม่รู้ว่า llama-server 86ea01d ตอบอย่างไรเมื่อเกิน 4096 · ยังไม่รู้อัตรา token ต่อตัวอักษรไทยจริง (โค้ดเดา ÷2) · ส่วน "ชน 512 token" ตอบแล้วจากไฟล์ Pi: 0/30
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~50 นาที · **ความเสี่ยง:** ต่ำ · CPU เต็ม · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** วาง section "เตรียม shell" · `ready` ผ่าน (llm.py บันทึกลง docs/benchmarks และต้องผูก commit)

ขั้น 1 ประกาศเกณฑ์:
```sh
ready
D=docs/benchmarks/$(date +%F)-pi5-llm-long-text; mkdir -p $D
cat > $D/README.md <<'EOF'
# ข้อความยาวผ่านสกิลสรุป (ประกาศก่อนวัด)
- pp1000 / pp2000 ด้วย aipc.spikes.llm (threads 3) · ไม่มีเกณฑ์ ADR · จด prefill_s เพื่อตั้งเพดานข้อความ
  (ข้อความ "เกณฑ์ BRIEF 5.4 ... ไม่ผ่าน" ที่ llm.py พิมพ์ ใช้กับ 200 token เท่านั้น)
- ข้อความ: คำถามไทย 30 ข้อต่อกัน ตัด 1000 / 3000 / 6000 / 9000 / 20000 ตัวอักษร · cache_prompt false
- เพดานเสนอของสกิล AI = ขนาดใหญ่สุดที่ prompt_s <= 60
- 20000 ตัวอักษร: แบบตรงได้ HTTP 4xx ภายใน 5 วิ · แอป (Stream) ได้ reason = error และ detail ไม่ว่าง
  ถ้าได้ reason "" กับ text_chars 0 = ล้มเงียบ → ยืนยัน code fix
- ขนาดใดได้ finish = length → ยืนยัน code fix ให้ Stream อ่าน finish_reason
- ขนาดที่ est_tokens (ตัวอักษร÷2) เกิน 3000 แต่ cut = false → ยืนยันว่าข้อความเดี่ยวไม่ถูกตัด
- จด tok_per_char จริง (prompt_n ÷ ตัวอักษร) เทียบกับค่าเดา 0.5 ของ fit_context
EOF
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์ข้อความยาว"
```
ขั้น 2 วัด:
```sh
# 1) pp ที่ 1000 และ 2000 token ด้วยเครื่องมือเดิม (aipc.bench · ระดับ 4 ถ้าไม่ throttle)
for p in 1000 2000; do
  $PY -m aipc.spikes.llm --bench $B/llama-bench --model $M --label $LABEL-p$p \
      --size 3-4b --threads $T --prompt $p --meta llama_cpp=$L | tail -3
  git add docs/benchmarks && git commit -q -m "bench(pi5): llm $LABEL prompt $p threads $T"
done
# 2) ข้อความยาวผ่านสกิลสรุป: HTTP, finish_reason, เวลาอ่าน (cache ปิด = วัดแบบเย็น)
snap /tmp/long-machine-before.txt; thermal_on /tmp/long-thermal.log
$B/llama-server -m $M --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t $T --no-webui > /tmp/llama-long.log 2>&1 & P=$!
wait_up http://127.0.0.1:8080/health
$PY - <<'EOF' | tee /tmp/long-text.jsonl
import json, time, urllib.request, urllib.error
from aipc.chat import client
from aipc.skills import manifest
p = {m.id: m for m in manifest.load_builtin()}['summarize-text'].prompt
qs = json.load(open('tests/data/llm_thai_questions.json', encoding='utf-8'))['questions']
base = ' '.join(q['text'] for q in qs) * 20
for n in (1000, 3000, 6000, 9000, 20000):
    msgs, cut = client.fit_context(p, [{'role': 'user', 'content': 'สรุปข้อความนี้: ' + base[:n]}])
    body = {'messages': msgs, 'max_tokens': 512, 'temperature': 0.6, 'top_p': 0.95, 'cache_prompt': False}
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    s = time.monotonic()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=1800).read()); tm = d['timings']
        out = {'http': 200, 'finish': d['choices'][0]['finish_reason'], 'prompt_n': tm['prompt_n'],
               'tok_per_char': round(tm['prompt_n'] / sum(len(m['content']) for m in msgs), 3),
               'prompt_s': round(tm['prompt_ms'] / 1000, 1), 'gen_n': tm['predicted_n'],
               'answer_chars': len(d['choices'][0]['message'].get('content') or '')}
    except urllib.error.HTTPError as e:
        out = {'http': e.code, 'body': e.read()[:200].decode('utf-8', 'replace')}
    est = sum(len(m['content']) for m in msgs) // 2
    print(json.dumps({'chars': n, 'est_tokens': est, 'cut': cut, 'seconds': round(time.monotonic() - s, 1), **out}, ensure_ascii=False), flush=True)
# สิ่งที่แอปเห็น (Stream) เมื่อข้อความยาวเกิน context แน่นอน
msgs, cut = client.fit_context(p, [{'role': 'user', 'content': 'สรุปข้อความนี้: ' + base[:20000]}])
r = client.Stream(client.Target(url='http://127.0.0.1:8080'), msgs).run(lambda tok: None)
print(json.dumps({'app_20000': True, 'cut': cut, 'reason': r.reason, 'detail': r.detail[:120], 'text_chars': len(r.text)}, ensure_ascii=False))
EOF
kill $P; thermal_off /tmp/long-thermal.log | tee /tmp/long-throttle.txt
cp /tmp/long-text.jsonl /tmp/long-machine-before.txt /tmp/long-thermal.log /tmp/long-throttle.txt $D/
git add $D && git commit -m "bench(pi5): ข้อความยาวผ่านสกิลสรุป (เกิน context · finish_reason)"
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนวัด) (1) ไฟล์ p1000/p2000 เขียนว่า "ใช้เป็นหลักฐานระดับ 4 ได้" · จด prefill_s (2) เพดานเสนอ = ขนาดใหญ่สุดที่ `prompt_s` ≤ 60 (3) 20000 ตัวอักษร: แบบตรงได้ `http` 4xx และ `seconds` ≤ 5 · `app_20000` ได้ `reason` = "error" และ `detail` ไม่ว่าง (4) จดขนาดที่ได้ `finish` = "length" (5) บรรทัดที่ `est_tokens` > 3000 มี `cut` false = ยืนยันข้อความเดี่ยวไม่ถูกตัด (6) จด `tok_per_char` · throttle ขณะวัด 0 บรรทัด
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-typhoon25-4b-q4km-p1000-t3.*` และ `…-p2000-t3.*` (llm.py ตั้งชื่อเอง) · `docs/benchmarks/<วันที่>-pi5-llm-long-text/` (README.md · long-text.jsonl · long-machine-before.txt · long-thermal.log · long-throttle.txt) · commit อยู่ในคำสั่งแล้ว

### V17 คุณภาพคำตอบตอนใช้สกิลสรุป/จดหมาย และแชทที่มีรายการสกิล
- **ตอบข้อ audit:** gaps-3
- **ทำไมต้องทดสอบ:** คำตอบไทย 30 ข้อ (`2026-09-29-llm-thai`) ใช้แค่ system พื้นฐาน ไม่มี prompt ของสกิล และไม่มีรายการสกิล · ในแอป สกิล llm ส่ง `r.skill.prompt` แทน system และแชททั่วไปส่งรายการสกิลทุกครั้ง · ใน 30 ข้อเดิม งานจดหมาย/สรุปจริงมีแค่ q06 q07 q11 · จึงใช้ประโยค expect ของ 2 สกิลจาก `tests/data/skill_selection.json` (commit ไว้แล้ว · ทุกประโยคสรุปมีข้อความให้สรุปอยู่ท้าย `:`)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · ผู้ให้คะแนน 2 คนทำบน PC ได้ · **เวลา:** ~75 นาที (16 ข้อ + 30 ข้อ · คำตอบยาวถึง 512 token ≈ 110 วิ/ข้อ) ไม่รวมให้คะแนน · **ความเสี่ยง:** ต่ำ · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** วาง section "เตรียม shell" · `ready` ผ่าน

ขั้น 1 สร้างชุดคำถามจากข้อมูลที่ commit แล้ว + ประกาศเกณฑ์ (H9):
```sh
ready
D=docs/benchmarks/$(date +%F)-llm-skill-pi5; mkdir -p $D
D=$D $PY - <<'EOF'
import json, os
from aipc.skills import manifest
from aipc.spikes import skill_select
sk = {m.id: m for m in manifest.load_builtin()}
items = json.load(open(skill_select.DATASET, encoding='utf-8'))['items']
for sid in ('summarize-text', 'letter-writer'):
    qs = [{'id': f'{sid}-{i}', 'kind': sid, 'text': it['text']}
          for i, it in enumerate(x for x in items if x['expect'] == sid)]
    out = {'about': f'expect={sid} จาก tests/data/skill_selection.json · system_prompt = prompt ของสกิล',
           'system_prompt': sk[sid].prompt, 'questions': qs}
    json.dump(out, open(os.path.join(os.environ['D'], f'q-{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(sid, len(qs), 'ข้อ')
EOF
cat > $D/README.md <<'EOF'
# คุณภาพคำตอบตอนใช้สกิลจริง (ประกาศก่อนวัด)
- ชุด: q-summarize-text.json 8 ข้อ · q-letter-writer.json 8 ข้อ · ไม่แก้หลังวัด
- แชทที่มีรายการสกิล: คำถามไทย 30 ข้อเดิม + SYSTEM+TOOLS_HINT + รายการสกิล (ไม่ stream · ค่า sampling เดิม)
- ผ่าน: 2 คนให้คะแนนเฉลี่ย >= 3.5 ต่อสกิล (เกณฑ์ ADR-007 ข้อ 1)
- สรุป: 8/8 เป็นรายการขึ้นต้น "- " 3-5 ข้อ (ตาม prompt ของสกิล) · ผู้ให้คะแนนจดว่ามีข้อมูลที่ไม่อยู่ในข้อความไหม (ใช่/ไม่) ต้องเป็น "ไม่" 8/8
- จดหมาย: 8/8 มี "เรื่อง:" และ "เรียน" และเว้นชื่อผู้ส่งเป็น [ชื่อผู้ส่ง] หรือ <ชื่อผู้ส่ง> (prompt ของสกิลเขียนไว้ทั้ง 2 แบบ)
- แชทที่มีรายการสกิล: ข้อที่ AI เลือกสกิล ตัดสินด้วยตารางนี้ (ไม่ใช้ความเห็นผู้ให้คะแนน):
  เหมาะ = q06 q07 → letter-writer · q11 → summarize-text · q14 q15 q16 q17 → translate
  เลือกสกิลกับข้ออื่น 23 ข้อ = เลือกผิด · ผ่านเมื่อเลือกผิด <= 2/23
- ข้อที่ AI ตอบเอง: ให้คะแนนแบบปิดชื่อเทียบกับผลเดิม เฉพาะข้อเหล่านั้น · ผ่านเมื่อคะแนนเฉลี่ยลดไม่เกิน 0.3
EOF
git add $D && git commit -m "bench(pi5): ประกาศชุดคุณภาพคำตอบของสกิลสรุป/จดหมาย"
```
ขั้น 2 ถามและตรวจ:
```sh
snap /tmp/skillq-machine-before.txt; thermal_on /tmp/skillq-thermal.log
$B/llama-server -m $M --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t $T --no-webui > /tmp/llama-skillq.log 2>&1 & P=$!
wait_up http://127.0.0.1:8080/health
for sid in summarize-text letter-writer; do
  $PY -m aipc.spikes.llm_quality ask --label $LABEL-$sid --questions $D/q-$sid.json --out $D/$LABEL-$sid.json
  git add $D && git commit -q -m "bench(pi5): คำตอบสกิล $sid $LABEL"
done
# แชทที่มีรายการสกิล (30 ข้อเดิม) · รูปไฟล์เดียวกับ llm_quality เพื่อใช้ sheet ได้
$PY - $LABEL-tools $D/$LABEL-tools.json <<'EOF'
import json, sys, time, urllib.request
from datetime import date
from aipc.skills import catalog, manifest
from aipc.spikes import llm_quality as lq
tools = catalog.tools(manifest.load_builtin(), {'llm'})
qs = json.load(open(lq.QUESTIONS, encoding='utf-8'))
rows = []
for q in qs['questions']:
    body = {'messages': [{'role': 'system', 'content': catalog.SYSTEM + catalog.TOOLS_HINT}, {'role': 'user', 'content': q['text']}],
            'tools': tools, 'tool_choice': 'auto', 'stream': False, 'cache_prompt': True, **lq.SAMPLING}
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    t0 = time.monotonic(); d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    m = d['choices'][0]['message']; calls = m.get('tool_calls') or []
    ans = f"[AI เลือกสกิล {calls[0]['function']['name']}]" if calls else (m.get('content') or '')
    rows.append({'id': q['id'], 'answer': ans, 'seconds': round(time.monotonic() - t0, 2), 'usage': d.get('usage', {}),
                 'timings': d.get('timings', {}), 'finish_reason': d['choices'][0].get('finish_reason')})
    print(q['id'], rows[-1]['seconds'], 'วิ', ans[:40], file=sys.stderr)
json.dump({'label': sys.argv[1], 'date': date.today().isoformat(), 'sampling': lq.SAMPLING,
           'questions_file': lq.QUESTIONS.name, 'answers': rows}, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
EOF
kill $P; thermal_off /tmp/skillq-thermal.log | tee /tmp/skillq-throttle.txt
cp /tmp/skillq-machine-before.txt /tmp/skillq-thermal.log /tmp/skillq-throttle.txt $D/
# ตรวจรูปแบบอัตโนมัติ + ชุดคำถามเฉพาะข้อที่ AI ตอบเอง (ให้ผู้ให้คะแนนเดาไม่ได้ว่าคำตอบไหนมีรายการสกิล)
D=$D $PY - <<'EOF' | tee $D/auto-check.txt
import json, os
D = os.environ['D']; L = 'typhoon25-4b-q4km'
load = lambda f: json.load(open(f, encoding='utf-8'))
a = load(f'{D}/{L}-summarize-text.json')['answers']
print('สรุป: รายการ 3-5 ข้อ', sum(3 <= sum(l.strip().startswith('- ') for l in x['answer'].splitlines()) <= 5 for x in a), '/', len(a))
b = load(f'{D}/{L}-letter-writer.json')['answers']
ok = lambda s: 'เรื่อง:' in s and 'เรียน' in s and ('[ชื่อผู้ส่ง]' in s or '<ชื่อผู้ส่ง>' in s)
print('จดหมาย: เรื่อง/เรียน/ชื่อผู้ส่งเว้นไว้', sum(ok(x['answer']) for x in b), '/', len(b))
c = load(f'{D}/{L}-tools.json')['answers']
fit = {'q06': 'letter-writer', 'q07': 'letter-writer', 'q11': 'summarize-text',
       'q14': 'translate', 'q15': 'translate', 'q16': 'translate', 'q17': 'translate'}
picked = {x['id']: x['answer'][len('[AI เลือกสกิล '):-1] for x in c if x['answer'].startswith('[AI เลือกสกิล')}
print('แชทที่มีรายการสกิล: AI เลือกสกิล', picked)
print('  เลือกเหมาะ', sum(fit.get(k) == v for k, v in picked.items()), '/ 7 · เลือกผิด', sum(k not in fit or fit[k] != v for k, v in picked.items() if k not in fit), '/ 23')
q = load('tests/data/llm_thai_questions.json'); q['questions'] = [x for x in q['questions'] if x['id'] not in picked]
json.dump(q, open(f'{D}/q-tools-own.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('  ข้อที่ AI ตอบเอง', len(q['questions']), 'ข้อ → q-tools-own.json')
for f in ('summarize-text', 'letter-writer', 'tools'):
    t = [x['timings'].get('prompt_ms', 0) / 1000 for x in load(f'{D}/{L}-{f}.json')['answers']]
    print(f, 'อ่าน prompt สูงสุด', round(max(t), 1), 'วิ')
EOF
for sid in summarize-text letter-writer; do
  $PY -m aipc.spikes.llm_quality sheet $D/$LABEL-$sid.json --questions $D/q-$sid.json --out $D/rating-$sid
done
$PY -m aipc.spikes.llm_quality sheet docs/benchmarks/2026-09-29-llm-thai/$LABEL.json $D/$LABEL-tools.json \
    --questions $D/q-tools-own.json --out $D/rating-tools
git add $D && git commit -m "bench(pi5): คุณภาพคำตอบของสกิลสรุป/จดหมาย + แชทที่มีรายการสกิล"
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนถาม) คะแนนเฉลี่ย 2 คน ≥ 3.5 ต่อสกิล (`$PY -m aipc.spikes.llm_quality score --key $D/rating-<สกิล>/key.json rater1.csv rater2.csv`) · สรุป 8/8 เป็นรายการ 3–5 ข้อ และผู้ให้คะแนนตอบ "ไม่มีข้อมูลแต่ง" 8/8 · จดหมาย 8/8 · แชทที่มีรายการสกิล: เลือกผิด ≤ 2/23 และคะแนนของ `typhoon25-4b-q4km-tools` ลดจาก `typhoon25-4b-q4km` ไม่เกิน 0.3 (จาก `score` ของ rating-tools) · throttle ขณะวัด 0 บรรทัด · N เล็ก ต้องเขียนเป็นข้อจำกัดในเล่ม
- **บันทึกผล:** `docs/benchmarks/<วันที่>-llm-skill-pi5/` (README · q-*.json · คำตอบ 3 ไฟล์ · auto-check.txt · rating-*/ · skillq-*.txt/log) · ส่ง rating-*/rate-me.csv ให้ผู้ให้คะแนน · ห้ามเปิด key.json ก่อนให้คะแนนเสร็จ · commit อยู่ในคำสั่งแล้ว

### V18 สกิลที่ Claude เขียน ผ่านตัวเลือกสกิลของแอปบน Pi 5
- **ตอบข้อ audit:** skills-6
- **ทำไมต้องทดสอบ:** `forge.trial` ใช้ `router.route` (กฎอย่างเดียว · `forge.py` บรรทัด 143–159) แต่แอปใช้ `router.route_ai_first` เมื่อ AI พร้อม (`backend.py` บรรทัด 697) · ผล 10/10 และ 6/6 ของ forge จึงไม่ใช่เส้นทางจริง · มีชุดวัดที่เป็นกลางกว่าแล้ว: สกิล 10 ตัวที่ Claude เขียน (`docs/benchmarks/2026-09-30-skill-author/claude/` · ผ่านตัวตรวจ 10/10 · ระดับ 3) และเกณฑ์ใน `tests/data/skill_authoring.json` (commit ก่อนวัด · should 30 ประโยค · should_not 30 ประโยค) · ยังไม่เคยรันขั้น `route` กับ AI ในเครื่องบน Pi 5
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~70 นาที (ฐาน 58 ข้อ + 60 ประโยค + 58 ข้อหลังเพิ่มสกิล · รายการสกิลเปลี่ยนทุกสกิล จึงอ่าน prompt ใหม่ ~70 วิ ทุกครั้งที่เปลี่ยน) · **ความเสี่ยง:** ต่ำ · CPU เต็ม · prompt ยาวขึ้นเมื่อเพิ่ม 10 สกิล (~2,800 token ยังไม่เกิน 4096) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (สกิลอ่านจากโฟลเดอร์ผลวัด ไม่ได้ติดตั้ง)
- **ก่อนเริ่ม:** วาง section "เตรียม shell" · `ready` ผ่าน (ใช้ `machine_start.dirty` ตัดสิน · ไฟล์ผลถูกเขียนระหว่างรัน `machine_end` จึงเป็น dirty เสมอ)
```sh
ready
D=docs/benchmarks/2026-09-30-skill-author      # สกิลของ Claude + เกณฑ์ commit ไว้แล้ว (973ea52)
ls $D/claude/author.json $D/claude/*.md | wc -l   # ต้องได้ 11
OUT=$D/route-pi5-$(date +%F).json
$B/llama-server -m $M --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t $T --no-webui > /tmp/llama-author.log 2>&1 & P=$!
wait_up http://127.0.0.1:8080/health
thermal_on /tmp/thermal-author.log
# ตัดสินด้วยตัวเลือกสกิลของแอปจริง (route_ai_first + AI ในเครื่อง)
$PY -m aipc.spikes.skill_author route --server http://127.0.0.1:8080 --out $OUT $D/claude | tee /tmp/author-route.txt
kill $P; thermal_off /tmp/thermal-author.log | tee /tmp/author-throttle.txt
cp /tmp/thermal-author.log ${OUT%.json}-thermal.log; cp /tmp/author-route.txt /tmp/author-throttle.txt $D/
$PY -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print('dirty ตอนเริ่ม',d['machine_start']['dirty']);[print(k,v['verdict']) for k,v in d['authors'].items()]" $OUT
git add $D && git commit -m "bench(pi5): สกิลที่ Claude เขียน ผ่านตัวเลือกสกิลของแอป (AI ในเครื่อง)"
```
- **ผ่านเมื่อ:** (เกณฑ์ใน `tests/data/skill_authoring.json` ประกาศก่อนวัดแล้ว) `verdict.checks.should_hit` true (≥ 80%) · `should_not_false` true (≤ 10%) · `regression` true (เสียข้อที่เคยถูก ≤ 2) · `dirty ตอนเริ่ม False` · throttle ขณะวัด 0 บรรทัด · ใช้ตัวเลขนี้ในเล่มแทน 10/10 ของ forge · ประกอบกับตัวเลขแยกตามสกิลจาก section "เลือกสกิลแบบ AI ก่อน 3 รอบ"
- **บันทึกผล:** `docs/benchmarks/2026-09-30-skill-author/route-pi5-<วันที่>.json` + `…-thermal.log` + author-route.txt + author-throttle.txt · commit อยู่ในคำสั่งแล้ว

### V19 ตัวเลือกความเร็วหลังเลือกโมเดล: Q4_0 · flash attention · KV q8_0
- **ตอบข้อ audit:** llm-5, llm-8
- **ทำไมต้องทดสอบ:** threads ตัดสินแล้วจากระดับ 4: t3 อ่าน 16.26 tok/s สร้าง 4.633 tok/s (`2026-09-29-pi5-llm-typhoon25-4b-q4km-t3-t3.md` ใช้ได้) ส่วน t4 throttle ทุกรอบ (ใช้ไม่ได้) → ใช้ 3 · Q4_0 ที่ ADR-007 วางแผนไว้ยังไม่ได้โหลด · `-fa` / `-ctk` / `-ctv` ยังไม่เคยวัด (มีแค่ตัวเลขภายนอกที่ปรับหลายอย่างพร้อมกัน) · คอขวดคือการอ่าน prompt จึงวัดที่ 1000 token
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~70 นาที + เวลาโหลดไฟล์ · **ความเสี่ยง:** ต่ำ · ใช้ดิสก์เพิ่ม ~2.4 GB · **ย้อนกลับ:** `rm -i models/$Q40` (ไม่แตะ service)
- **ก่อนเริ่ม:** เลือกโมเดลตาม ADR-007 แล้ว (ตัวอย่างใช้ Typhoon) · ทำหลัง section "ข้อความยาว" (ใช้ไฟล์ p1000 ของ Q4_K_M เป็นฐาน) · อ่าน `bench-flags.txt` จาก section "ข้อมูลประกอบ" ว่า `-fa` รับค่าแบบ `0,1` หรือ `on,off` · วาง section "เตรียม shell" · ดิสก์ว่าง ≥ 4 GB (`df -h ~`)

ขั้น 1 ดูไฟล์และโหลด (ห้ามวัดระหว่างโหลด):
```sh
df -h ~
curl -sL https://huggingface.co/api/models/typhoon-ai/typhoon2.5-qwen3-4b-gguf/tree/main | python3 -c "import json,sys;[print(f['path']) for f in json.load(sys.stdin)]"
# ใส่ชื่อไฟล์ Q4_0 ที่เห็นข้างบน (ถ้าไม่มี Q4_0 เลย: หยุด section นี้ส่วน Q4_0 · ห้าม quantize จาก Q4_K_M เพราะเสียคุณภาพซ้ำ)
Q40=ชื่อไฟล์-Q4_0.gguf
# ฟังก์ชันเดียวกับ runbook ขั้น 6: โหลดต่อได้ + เทียบ sha256 กับค่าที่ Hugging Face ประกาศ
fetch() {
  curl -L --fail -C - -o "models/$2" "https://huggingface.co/$1/resolve/main/$2" || return 1
  want=$(curl -sL "https://huggingface.co/api/models/$1/tree/main" | python3 -c "import json,sys; print(next(f['lfs']['oid'] for f in json.load(sys.stdin) if f['path']=='$2'))")
  got=$(sha256sum "models/$2" | cut -d' ' -f1)
  if [ "$want" = "$got" ]; then echo "ตรง: $2 $got"; else echo "ไม่ตรง! $2 (ห้ามใช้)"; fi
}
fetch typhoon-ai/typhoon2.5-qwen3-4b-gguf "$Q40"
```
ขั้น 2 ประกาศเกณฑ์ แล้ววัด:
```sh
ready
D=docs/benchmarks/$(date +%F)-pi5-llm-kv; mkdir -p $D
cat > $D/README.md <<EOF
# ตัวเลือกความเร็ว (ประกาศก่อนวัด $(date +%F)) · llama.cpp $L · threads $T · $M
- Q4_0 ($Q40) น่าใช้เมื่อ pp1000 เร็วขึ้น >= 20% และ tg ช้าลงไม่เกิน 5% เทียบไฟล์ p1000-t3 ของ Q4_K_M · แล้วต้องวัดคำตอบไทย 30 ข้อ + ให้คะแนนปิดชื่อ ลดไม่เกิน 0.3 ก่อนใช้จริง
- -fa 1 น่าใช้เมื่อ pp หรือ tg เร็วขึ้น >= 10% และอีกค่าไม่ช้าลงเกิน 5%
- KV q8_0 น่าใช้เมื่อ tg ที่ depth 3000 เร็วขึ้น >= 10% · ต้องวัดคุณภาพไทยซ้ำก่อนเปิด · ห้ามใช้ q4_0
- ไม่ผ่าน = คงค่าเริ่มต้น · throttle ขณะวัด 0 บรรทัด
- ผล llama-bench ตรง ๆ (fa.md, d3000-*.md) ไม่ได้บันทึกด้วย aipc.bench = ใช้เทียบกันในรอบนี้เท่านั้น ไม่ใช่ระดับ 4
EOF
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์ Q4_0 / flash attention / KV q8_0"
# 1) Q4_0 ที่ prompt 1000 (aipc.bench · ระดับ 4 ถ้าไม่ throttle)
$PY -m aipc.spikes.llm --bench $B/llama-bench --model models/$Q40 --label typhoon25-4b-q40-p1000 \
    --size 3-4b --threads $T --prompt 1000 --meta llama_cpp=$L | tail -3
git add docs/benchmarks && git commit -q -m "bench(pi5): llm typhoon25-4b-q40 prompt 1000 threads $T"
# 2) flash attention และ KV q8_0 (ถ้า bench-flags.txt บอกว่า -fa รับ on/off ให้เปลี่ยน 0,1 เป็น off,on และ 1 เป็น on)
snap /tmp/kv-machine-before.txt; thermal_on /tmp/kv-thermal.log
$B/llama-bench -m $M -t $T -p 1000 -n 64 -fa 0,1 -r 3 -o md | tee /tmp/kv-fa.md
$B/llama-bench -m $M -t $T -p 512 -n 64 -d 3000 -fa 1 -r 2 -o md | tee /tmp/kv-d3000-f16.md
$B/llama-bench -m $M -t $T -p 512 -n 64 -d 3000 -fa 1 -ctk q8_0 -ctv q8_0 -r 2 -o md | tee /tmp/kv-d3000-q8.md
thermal_off /tmp/kv-thermal.log | tee -a /tmp/kv-throttle.txt
cp /tmp/kv-fa.md /tmp/kv-d3000-f16.md /tmp/kv-d3000-q8.md /tmp/kv-machine-before.txt /tmp/kv-thermal.log /tmp/kv-throttle.txt $D/
git add $D && git commit -m "bench(pi5): flash attention และ KV q8_0 ที่ depth 3000"
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนวัด) `fetch` ขึ้น "ตรง:" · ไฟล์ q40-p1000-t3 เขียนว่า "ใช้เป็นหลักฐานระดับ 4 ได้" · เทียบ Q4_0 กับ Q4_K_M ตามเกณฑ์ใน README · `-fa 1` และ KV q8_0 ตามเกณฑ์ใน README · throttle ขณะวัด 0 บรรทัดทุกกลุ่ม · ไม่ผ่าน = คงค่าเริ่มต้น (llm-8)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-typhoon25-4b-q40-p1000-t3.*` · `docs/benchmarks/<วันที่>-pi5-llm-kv/` (README.md · kv-fa.md · kv-d3000-*.md · kv-machine-before.txt · kv-thermal.log · kv-throttle.txt) · commit อยู่ในคำสั่งแล้ว

### V20 ตัวช่วยร่าง Qwen3-0.6B (speculative decoding)
- **ตอบข้อ audit:** llm-9
- **ทำไมต้องทดสอบ:** ADR-007 บรรทัด 42–43 วางไว้เป็นการทดลองเสริม ยังไม่มีผลวัด · ช่วยได้แค่ช่วงสร้างข้อความ ไม่ช่วยการอ่าน prompt · RAM น่าห่วง: llama-server ตอนนี้ VmHWM 5,641,872 kB (RssAnon 3,205,808 kB + RssFile 2,433,904 kB · `2026-09-30-skill-select-pi5/typhoon25-4b-q4km-server-ram.txt`) · ADR-007 ข้อ 4 (≤ 3.5 GB) ยังไม่ได้บอกว่านับค่าไหน · ทำเป็นลำดับท้าย
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~50 นาที + เวลาโหลด · **ความเสี่ยง:** ต่ำ · ใช้ดิสก์เพิ่ม ~0.7 GB · **ย้อนกลับ:** `rm -i models/Qwen3-0.6B-Q8_0.gguf`
- **ก่อนเริ่ม:** section อื่นในหมวดนี้เสร็จแล้ว · วาง section "เตรียม shell" · หมายเหตุ: ตอนนี้ cgroup memory ปิดอยู่ (MemoryMax ของ service ไม่มีผล) แต่ section นี้รัน server เองนอก service จึงไม่เกี่ยว

ขั้น 1 โหลด (ห้ามวัดระหว่างโหลด):
```sh
curl -sL https://huggingface.co/api/models/Qwen/Qwen3-0.6B-GGUF/tree/main | python3 -c "import json,sys;[print(f['path']) for f in json.load(sys.stdin)]"
# fetch() เดียวกับ section ตัวเลือกความเร็ว (วางซ้ำถ้าเปิด shell ใหม่)
fetch() {
  curl -L --fail -C - -o "models/$2" "https://huggingface.co/$1/resolve/main/$2" || return 1
  want=$(curl -sL "https://huggingface.co/api/models/$1/tree/main" | python3 -c "import json,sys; print(next(f['lfs']['oid'] for f in json.load(sys.stdin) if f['path']=='$2'))")
  got=$(sha256sum "models/$2" | cut -d' ' -f1)
  if [ "$want" = "$got" ]; then echo "ตรง: $2 $got"; else echo "ไม่ตรง! $2 (ห้ามใช้)"; fi
}
fetch Qwen/Qwen3-0.6B-GGUF Qwen3-0.6B-Q8_0.gguf
```
ขั้น 2 ประกาศเกณฑ์ แล้ววัด:
```sh
ready
D=docs/benchmarks/$(date +%F)-llm-spec-pi5; mkdir -p $D
D=$D $PY -c "import json,os;q=json.load(open('tests/data/llm_thai_questions.json',encoding='utf-8'));q['questions']=q['questions'][:10];json.dump(q,open(os.environ['D']+'/q10.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
echo "ตัวช่วยร่าง (ประกาศก่อนวัด): ผ่านเมื่อ median predicted_per_second >= 1.15 เท่าของแบบไม่มี draft · spec-log ไม่มี error เรื่อง vocab · จด VmHWM และ RssAnon ทั้ง 2 แบบ · ถ้าแบบมี draft เพิ่ม RAM จนเกินเกณฑ์ ADR-007 ข้อ 4 = ใช้ไม่ได้แม้เร็วขึ้น · throttle ขณะวัด 0 บรรทัด" > $D/README.md
git add $D && git commit -m "bench(pi5): ประกาศเกณฑ์ตัวช่วยร่าง Qwen3-0.6B"
rm -f /tmp/spec-base.json /tmp/spec-spec.json     # llm_quality ask ไม่ยอมเขียนทับไฟล์เดิม
snap /tmp/spec-machine-before.txt; thermal_on /tmp/spec-thermal.log
for v in base spec; do
  X=""; [ $v = spec ] && X="-md models/Qwen3-0.6B-Q8_0.gguf"
  $B/llama-server -m $M $X --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t $T --no-webui > /tmp/spec-$v.log 2>&1 & P=$!
  wait_up http://127.0.0.1:8080/health && \
    $PY -m aipc.spikes.llm_quality ask --label typhoon25-4b-$v --questions $D/q10.json --out /tmp/spec-$v.json
  grep -E 'VmHWM|RssAnon|RssFile' /proc/$P/status > /tmp/spec-$v-ram.txt; kill $P; wait $P 2>/dev/null
done
thermal_off /tmp/spec-thermal.log | tee /tmp/spec-throttle.txt
grep -iE 'vocab|draft|error' /tmp/spec-spec.log | head -20 > /tmp/spec-log.txt
cp /tmp/spec-base.json /tmp/spec-spec.json /tmp/spec-*-ram.txt /tmp/spec-log.txt /tmp/spec-machine-before.txt /tmp/spec-thermal.log /tmp/spec-throttle.txt $D/
$PY -c "import json,sys,statistics as s;m=lambda f:s.median(x['timings']['predicted_per_second'] for x in json.load(open(f,encoding='utf-8'))['answers']);a,b=m(sys.argv[1]),m(sys.argv[2]);print('ไม่มี draft',round(a,2),'มี draft',round(b,2),'tok/s · เท่า',round(b/a,2))" $D/spec-base.json $D/spec-spec.json | tee -a $D/README.md
git add $D && git commit -m "bench(pi5): ตัวช่วยร่าง Qwen3-0.6B เทียบไม่มี"
```
- **ผ่านเมื่อ:** (ตาม README ที่ commit ก่อนวัด) "เท่า" ≥ 1.15 · spec-log.txt ไม่มีบรรทัด error เรื่อง vocab · จด VmHWM/RssAnon ทั้ง 2 ไฟล์ ram · throttle ขณะวัด 0 บรรทัด
- **บันทึกผล:** `docs/benchmarks/<วันที่>-llm-spec-pi5/` (README · q10.json · spec-base.json · spec-spec.json · spec-*-ram.txt · spec-log.txt · spec-machine-before.txt · spec-thermal.log · spec-throttle.txt) · commit อยู่ในคำสั่งแล้ว

### V21 หน้าจอวาดด้วย GPU จริงไหม · เฟรมแรก · RAM/CPU ขณะว่าง
- **ตอบข้อ audit:** ui-0, ui-6 (RAM/CPU ขณะว่าง), ui-7 (เฟรมแรกบน GPU), ui-9 (warning ตอนวาดด้วย GPU)
- **ทำไมต้องทดสอบ:** ผลเปิดหน้าจอบน Pi 5 (`2026-09-29-pi5-ui-start-shell.json`) และเทสต์ทุกตัววาดด้วย CPU · เซสชันจริง (`aipc-shell-loop`) ไม่มี `--software` · ยังไม่มีหลักฐานว่า Qt ได้ V3D หรือหลุดไป llvmpipe · RAM/CPU ขณะว่างมีแค่ผล Pi 4 (~172–199 MB · ไม่ใช่ระดับ 4)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · หน้าต่างจะขึ้นเต็มจอบน desktop ที่ aipc2030 login ค้างไว้) · **เวลา:** ~20 นาที · **ความเสี่ยง:** ไม่มี (เปิด/ปิดหน้าต่างเท่านั้น) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section "ตัดคำไทย" · ไม่มีการวัดอื่นค้าง · อุณหภูมิ < 55°C · ไม่มีใครใช้จอ Pi · **ถ้าข้อ 1 ได้ llvmpipe/softpipe ให้หยุด ไม่ต้องทำ section fps** แล้วส่ง `qsg-info.log` กลับมา
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-ui-gpu; mkdir -p $D
pgrep -af 'llama-|measure-llm'          # ต้องไม่ขึ้นอะไร
vcgencmd measure_temp                   # ต้อง < 55°C
git log --oneline -1 > $D/commit.txt
./.venv/bin/python -m aipc.bench machine > $D/machine.json
echo "desktop Pi OS ของ aipc2030 เปิดค้าง (นับเป็นโหลด) · ไม่ใช่เซสชัน V2" > $D/notes.txt
# ต่อเข้าจอของ desktop ที่ login ค้างไว้ (ถ้าพิมพ์ใน Terminal บนจอ Pi ข้าม 3 บรรทัดนี้)
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=$(basename "$(ls -d $XDG_RUNTIME_DIR/wayland-[0-9] | head -1)")
export QT_QPA_PLATFORM=wayland
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"   # ต้องไม่ว่าง (เช่น wayland-0) ไม่งั้นหยุด
wlr-randr | tee $D/display.txt           # ความละเอียดและ Hz ของจอ
dpkg -l | awk '/mesa|libegl1 /{print $2, $3}' | tee $D/mesa.txt

# 1) GPU หรือ CPU: เปิด Shell 15 วิ แล้วปิดเอง
QSG_INFO=1 timeout 15 ./.venv/bin/python -m aipc.ui --screen shell --fullscreen 2> $D/qsg-info.log
grep -iE 'backend|renderer|vendor|llvmpipe|softpipe|software' $D/qsg-info.log | tee $D/gpu-summary.txt
grep -cE '\.qml:[0-9]+' $D/qsg-info.log | sed 's/^/QML warnings = /' | tee -a $D/gpu-summary.txt

# 2) เวลาถึงเฟรมแรกบน GPU 11 รอบ (รอบ 1 = warm-up · ค่าติดลบ = ไม่เห็นบรรทัดเฟรม ให้หยุดแล้วแจ้ง)
for i in $(seq 1 11); do
  S=$(cut -d' ' -f1 /proc/uptime)
  F=$(QT_MESSAGE_PATTERN='%{time boot} %{message}' QT_LOGGING_RULES='qt.scenegraph.time.renderloop=true' \
      timeout 8 ./.venv/bin/python -m aipc.ui --screen shell --fullscreen 2>&1 | grep -m1 -i 'frame rendered' | awk '{print $1}')
  awk -v i=$i -v s="$S" -v f="$F" 'BEGIN{printf "%d\t%.3f\n", i, f-s}'
  sleep 2
done | tee $D/first-frame-gpu.tsv
tail -n +2 $D/first-frame-gpu.tsv | cut -f2 | sort -n | awk '{a[NR]=$1} END{print "median รอบ 2-11 =", (a[5]+a[6])/2, "วิ"}' | tee -a $D/gpu-summary.txt

# 3) fd ไป GPU + RAM/CPU ขณะว่างบนหน้า Shell (ไม่มี llama-server = ป้ายโมเดลไม่พร้อม)
./.venv/bin/python -m aipc.ui --screen shell --fullscreen 2>/dev/null & UI=$!
sleep 30
ls -l /proc/$UI/fd | grep -c '/dev/dri/' | sed 's/^/fd ไป \/dev\/dri = /' | tee -a $D/gpu-summary.txt
grep -E 'VmRSS|VmHWM|RssAnon|RssFile' /proc/$UI/status | tee $D/rss-idle.txt
# CPU ของโปรเซสเอง (utime+stime) และของโปรเซสลูกที่จบแล้ว เช่น vcgencmd (cutime+cstime)
set -- $(awk '{print $14+$15, $16+$17}' /proc/$UI/stat); A0=$1; C0=$2
sleep 120
set -- $(awk '{print $14+$15, $16+$17}' /proc/$UI/stat); A1=$1; C1=$2
awk -v a=$((A1-A0)) -v c=$((C1-C0)) -v hz=$(getconf CLK_TCK) 'BEGIN{printf "idle CPU ตัวเอง = %.2f%% · รวมโปรเซสลูก = %.2f%% ของ 1 คอร์ (120 วิ)\n", a/hz/120*100, (a+c)/hz/120*100}' | tee $D/cpu-idle.txt
kill $UI
vcgencmd get_throttled | tee -a $D/notes.txt
```
- **ผ่านเมื่อ:** (1) log บอก backend OpenGL และ `GL_RENDERER` มีคำว่า `V3D` · ไม่มี `llvmpipe`/`softpipe` · `QML warnings = 0` · (2) median รอบ 2–11 ≤ 1.5 วิ และไม่มีค่าติดลบ · (3) `fd ไป /dev/dri` ≥ 1 · VmRSS ≤ 256000 kB · idle CPU ตัวเอง ≤ 1% และรวมโปรเซสลูก ≤ 2% ของ 1 คอร์ · get_throttled หลักสุดท้ายเป็น 0
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): หน้าจอวาดด้วย GPU + เฟรมแรก + RAM/CPU ขณะว่าง"` · เป็นค่าดิบพร้อม `machine.json` (ไม่ได้บันทึกด้วย `aipc.bench run` จึงยังไม่นับระดับ 4 เต็มรูป)

### V22 ต้นทุนตอนกด Enter: สร้างรายการแชทใหม่ + อ่านไฟล์ประวัติ
- **ตอบข้อ audit:** ui-2, ui-4
- **ทำไมต้องทดสอบ:** `WorkspacePage.qml` สร้าง JS array ใหม่ทั้งก้อนทุกครั้ง (บรรทัด 32, 68, 75) · `chat.history` อ่านไฟล์แชททุกไฟล์ทุกครั้งที่ `changed` ถูกส่ง (backend.py 903–908 · send() และ _on_done() ส่ง changed) · มีแค่ตัวเลขวินโดวส์ที่ไม่ได้บันทึกไฟล์ (7.4/52.5/117.9 ms · 41.7 ms) · Pi 5 ใช้ microSD จึงต้องวัดเอง · ผล ui-4 ใช้เป็นค่า "ก่อนแก้" ของ code fix
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · offscreen ไม่แตะจอ) · **เวลา:** ~15 นาที · **ความเสี่ยง:** เขียนไฟล์ชั่วคราว ~18 MB ใน home แล้วลบเอง · `drop_caches` ล้าง cache ไฟล์ทั้งเครื่องครั้งเดียว (ต้องพิมพ์รหัส sudo) ไม่เปลี่ยนค่าตั้ง · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (ถ้าค้างกลางทาง ลบโฟลเดอร์ `~/aipc-push-*` และ `~/aipc-hist-*` ที่สคริปต์นี้สร้าง)
- **ก่อนเริ่ม:** ไม่มีการวัดอื่นค้าง · อุณหภูมิ < 55°C · ใช้ shell ใหม่ (ไม่มี `QT_QPA_PLATFORM=wayland` จาก section GPU)
```sh
cd ~/aipc
unset QT_QPA_PLATFORM WAYLAND_DISPLAY AIPC_LLM_URL
D=docs/benchmarks/$(date +%F)-ui-push-history; mkdir -p $D
git log --oneline -1 > $D/commit.txt
# --- ui-2: เพิ่ม 1 ข้อความแล้ววาด เมื่อมี 2/20/60 ข้อความ (offscreen วาดด้วย CPU) ---
cat > /tmp/ui-push-cost.py <<'EOF'
import os, pathlib, shutil, statistics, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="aipc-push-", dir=str(pathlib.Path.home()))
os.environ["XDG_DATA_HOME"] = tmp  # ไม่ยุ่งกับแชท/นัดจริง
from PySide6.QtCore import QEventLoop, QObject, QTimer
from aipc.ui import app as uiapp
app, engine, warnings = uiapp.build(uiapp.Options(screen="shell", software=True, settings_path=pathlib.Path(tmp) / "ui.json"))
win = engine.rootObjects()[0]
def settle(ms):  # แบบเดียวกับ tests/test_ui_qml.py (ไม่วนกิน CPU)
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
settle(500)
page = [o for o in win.findChildren(QObject) if o.objectName() == "workspace"][0]
ai = "คำตอบภาษาไทยยาวที่ต้องตัดบรรทัดหลายบรรทัด " * 14  # ~600 ตัวอักษร
def msgs(n):
    return [{"user": True, "text": "คำถามที่ %d" % i} if i % 2 == 0 else {"ai": True, "text": ai, "note": "", "done": True, "skill": ""} for i in range(n)]
for n in (2, 20, 60):
    ts = []
    for r in range(6):
        page.setProperty("items", msgs(n)); settle(300)
        t = time.perf_counter()
        page.setProperty("items", msgs(n) + [{"user": True, "text": "ข้อความใหม่"}])
        win.grabWindow()
        ts.append((time.perf_counter() - t) * 1000)
    ts = ts[1:]  # ทิ้งรอบแรก เหลือ 5
    print("%d ข้อความ: median %.1f ms  max %.1f ms" % (n, statistics.median(ts), max(ts)))
print("QML warnings =", len(warnings))
win.close(); uiapp.shutdown(engine); shutil.rmtree(tmp, ignore_errors=True)
EOF
./.venv/bin/python /tmp/ui-push-cost.py | tee $D/push-cost.txt
cp /tmp/ui-push-cost.py $D/
# --- ui-4: ChatStore.list() กับแชท 200 ไฟล์บน microSD (/tmp เป็น tmpfs ใช้ไม่ได้) ---
cat > /tmp/hist-cost.py <<'EOF'
import pathlib, statistics, sys, tempfile, time
from aipc.chat import store as s
if sys.argv[1] == "make":
    d = pathlib.Path(tempfile.mkdtemp(prefix="aipc-hist-", dir=str(pathlib.Path.home())))
    st = s.ChatStore(d)
    for i in range(200):
        c = s.new_conversation(); c["title"] = "t%d" % i
        c["messages"] = [{"role": "user", "content": "สวัสดี " * 40}, {"role": "assistant", "content": "คำตอบภาษาไทย " * 200}] * 5
        st.save(c)
    print(d)
else:
    st = s.ChatStore(pathlib.Path(sys.argv[2])); ts = []
    for _ in range(11):
        t = time.perf_counter(); n = len(st.list()); ts.append((time.perf_counter() - t) * 1000)
    print("ไฟล์ %d · ครั้งแรก (cache ว่าง) %.1f ms · median ครั้ง 2-11 %.1f ms · max %.1f ms" % (n, ts[0], statistics.median(ts[1:]), max(ts[1:])))
EOF
H=$(./.venv/bin/python /tmp/hist-cost.py make)
echo "$H"                                  # ต้องขึ้น /home/aipc2030/aipc-hist-xxxx
du -sh "$H" | tee $D/history-cost.txt
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null   # ให้ครั้งแรกอ่านจาก microSD จริง
./.venv/bin/python /tmp/hist-cost.py time "$H" | tee -a $D/history-cost.txt
case "$H" in "$HOME"/aipc-hist-*) rm -rf "$H" ;; esac
cp /tmp/hist-cost.py $D/
```
- **ผ่านเมื่อ:** ui-2: 60 ข้อความ median ≤ 100 ms = ยังไม่ต้องเปลี่ยนเป็น ListModel · ถ้าเกิน ให้แก้เป็น ListModel แล้วรันสคริปต์เดิมบน commit ใหม่ ต้องได้ median ≤ ครึ่งหนึ่งของเดิม · `QML warnings = 0` · ui-4: median ครั้ง 2–11 ≤ 25 ms (Enter 1 ครั้งอ่าน 2 รอบ รวม ≤ 50 ms) · ค่าครั้งแรก (cache ว่าง) บันทึกไว้ ไม่มีเกณฑ์ · code fix ui-4 ทำต่อไม่ว่าผลเป็นอย่างไร แล้ววัดซ้ำหลังแก้
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): ต้นทุนเพิ่มข้อความแชท + อ่านประวัติ 200 ไฟล์"`

### V23 งานตรวจเครื่องทุก 10 วิบนเธรดหลัก ขณะ LLM ทำงาน
- **ตอบข้อ audit:** ui-5
- **ทำไมต้องทดสอบ:** `SystemStatus.refresh()` (backend.py 89–104) รันบนเธรดหลักทุก 10 วิ · เรียก `hardware.run_all()` ซึ่งมี `vcgencmd get_throttled` (timeout 10 วิ ใน bench/machine.py บรรทัด 47) · ผลวินโดวส์ (median 2.6 ms) ใช้แทน Pi ไม่ได้เพราะไม่มี vcgencmd
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~12 นาที · **ความเสี่ยง:** ไม่มี (อ่านอย่างเดียว) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ไม่มีการวัดอื่นค้าง · อุณหภูมิ < 55°C · ไม่มี llama-server ค้างจาก section อื่น (`pgrep -af 'llama-'` ว่าง)
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-ui-status-cost; mkdir -p $D
git log --oneline -1 > $D/commit.txt
cat > /tmp/status-cost.py <<'EOF'
# งานเดียวกับ SystemStatus.refresh() ใน src/aipc/ui/backend.py ที่หน้าจอทำบนเธรดหลักทุก 10 วิ
import shutil, statistics, time
from pathlib import Path
from aipc.bench import machine
from aipc.doctor import hardware
from aipc.skills import machine as skill_machine
ts = []
for _ in range(30):
    t = time.perf_counter()
    machine.cpu_temp_c(Path("/")); skill_machine.has_default_route(Path("/"))
    shutil.disk_usage(Path.home()); hardware.run_all(Path("/"))
    ts.append((time.perf_counter() - t) * 1000)
    time.sleep(1)
ts.sort()
print("n=30 median %.1f ms  p95 %.1f ms  max %.1f ms" % (statistics.median(ts), ts[28], ts[-1]))
EOF
vcgencmd get_throttled | tee $D/throttled-before.txt
# 1) เครื่องว่าง
./.venv/bin/python /tmp/status-cost.py | tee $D/idle.txt
# 2) ขณะ LLM สร้างข้อความ threads 3 (แบบที่จะใช้จริง) · ใช้เวลารวม ~4 นาที
~/llama.cpp/build/bin/llama-bench -m models/typhoon2.5-qwen3-4b-q4_k_m.gguf -p 0 -n 512 -t 3 -r 2 > /tmp/lb.log 2>&1 &
LB=$!; sleep 30   # รอโหลดโมเดลและเริ่มสร้างข้อความ
kill -0 $LB && ./.venv/bin/python /tmp/status-cost.py | tee $D/busy.txt
kill -0 $LB && echo "llama-bench ยังทำงานตอนวัดจบ = ใช้ได้" | tee -a $D/busy.txt
wait $LB; vcgencmd get_throttled | tee -a $D/busy.txt
cp /tmp/status-cost.py /tmp/lb.log $D/
```
- **ผ่านเมื่อ:** busy.txt มีบรรทัด "llama-bench ยังทำงานตอนวัดจบ" (ไม่งั้นผลขณะ LLM ใช้ไม่ได้) · ขณะ LLM ทำงาน max ≤ 16 ms (ไม่เกิน 1 เฟรมที่ 60 Hz) = ใช้แบบเดิมได้ · ถ้าเกิน = ย้ายไปทำในเธรดแยกแบบ `ChatController.refresh` (backend.py 911–922) แล้วรันสคริปต์นี้กับ section fps ซ้ำ · ค่า throttled หลักสุดท้ายต้องเป็น 0
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): เวลางานตรวจเครื่องของหน้าจอ ว่าง/ขณะ LLM ทำงาน"`

### V24 เวลาเปิดหน้าจอ Shell ที่ HEAD (ระดับ 4 ด้วย aipc.bench)
- **ตอบข้อ audit:** ui-7, evidence-5
- **ทำไมต้องทดสอบ:** ผลระดับ 4 ที่มี (`2026-09-29-pi5-ui-start-shell.json` median 1.196 วิ) วัดที่ commit e7426ce · หลังจากนั้นโค้ดหน้าจอเปลี่ยน (backend.py +152 บรรทัด) · เป็นโหมด offscreen วาดด้วย CPU รวมหน่วงถ่ายภาพ 0.6 วิ · ในเล่มต้องเขียนโหมดกำกับเสมอ ("offscreen วาดด้วย CPU")
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** git tree สะอาด (commit ผล section อื่นก่อน) · ไม่มีการวัดอื่นค้าง · อุณหภูมิ < 55°C · ใช้ shell ที่ไม่ได้ export `QT_QPA_PLATFORM` (โหมด --screenshot ต้องเป็น offscreen) · หมายเหตุ: บิต "เคยเกิด" ของ get_throttled ติดมาตั้งแต่บูต (0xe0000) เครื่องมือจึงจับได้เฉพาะบิต "ตอนนี้" · ถ้าไม่มีใครใช้จอ รีบูตก่อนได้ (`sudo reboot`) จะได้เริ่มจาก 0x0
```sh
cd ~/aipc
unset QT_QPA_PLATFORM WAYLAND_DISPLAY AIPC_LLM_URL
git status --porcelain            # ต้องว่าง ไม่งั้นผลไม่ผูกกับ commit
pgrep -af 'llama-|measure-llm'    # ต้องว่าง
vcgencmd measure_temp; vcgencmd get_throttled
O=docs/benchmarks/$(date +%F)-ui-start
./.venv/bin/python -m aipc.bench run --topic ui-start-shell --runs 20 --out $O \
  --meta screen=shell --meta mode=session-offscreen-software \
  --meta note=includes-600ms-screenshot-delay --meta desktop=pi-os-logged-in \
  -- ./.venv/bin/python -m aipc.ui --session --software --screenshot /tmp/ui-start.png
grep -H 'หลักฐานระดับ 4' $O/*-pi5-ui-start-shell.md
# หมายเหตุผู้วัด (เขียนหลังวัดจบ tree จึงสะอาดตอนวัด)
cat > $O/README.md <<'EOF'
# เวลาเปิดหน้าจอ Shell ที่ HEAD (Pi 5)
- โหมด: offscreen วาดด้วย CPU · รวมหน่วงถ่ายภาพ 0.6 วิ · ไม่ใช่เส้นทาง GPU/labwc จริง (ดูผล ui-gpu)
- เทียบ: 2026-09-29-pi5-ui-start-shell (commit e7426ce) median 1.196 วิ
- เครื่อง: อะแดปเตอร์ 27W 5A · Active Cooler · microSD SD64G (manfid 0x9f, 03/2024) · desktop Pi OS เปิดค้าง (นับเป็นโหลด)
EOF
```
- **ผ่านเมื่อ:** grep เจอ **ใช้เป็นหลักฐานระดับ 4 ได้** (ไม่ใช่ "ยังใช้ … ไม่ได้") · median ≤ 1.30 วิ (ช้ากว่าเดิมไม่เกิน ~10%)
- **บันทึกผล:** `$O/<วันที่>-pi5-ui-start-shell.{csv,json,md}` + README.md แล้ว `git add $O && git commit -m "bench(pi5): เวลาเปิดหน้าจอ Shell ที่ HEAD 20 รอบ (offscreen CPU)"`

### V25 forge (claude -p) บน Pi 5 และที่เก็บ credential
- **ตอบข้อ audit:** security-9
- **ทำไมต้องทดสอบ:** forge ผ่านแค่บนวินโดวส์ (ระดับ 3 · `docs/benchmarks/2026-09-29-skill-forge/README.md`) · ยังไม่เคยลอง Claude Code บน ARM64 · ยังไม่ได้ตรวจว่า credential อยู่ที่ที่บัญชีอื่นอ่านไม่ได้ · `/etc/aipc/llm.conf` ทุกบัญชีอ่านได้ (install-llm.sh ตั้ง 0644 · `aipc-llm-start:8` อ่านไฟล์นี้) จึงห้ามมีโทเคนอยู่ใน /etc/aipc
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · เข้าสู่ระบบ Claude ครั้งแรกต้องเปิดลิงก์ในเบราว์เซอร์ของเครื่องที่สอง) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · ใช้เน็ตและโควตา subscription (forge ตั้งเพดานไว้ต่อครั้ง) · ติดตั้ง Claude Code ลงใน home ของ aipc2030 เท่านั้น · **ย้อนกลับ:** ใน `claude` พิมพ์ `/logout` · ถ้าไม่ใช้แล้ว ถามเจ้าของก่อนลบ `~/.local/bin/claude` และ `~/.claude`
- **ก่อนเริ่ม:** ห้ามทำระหว่างวัด LLM หรือ T6 · ทำในบัญชี aipc2030 เท่านั้น ห้ามเข้าสู่ระบบ Claude ในบัญชีที่สมัครเองหรือใน _greetd · ต้องมีบัญชีทดสอบ testb แล้ว
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-forge; mkdir -p "$D"
command -v claude && claude --version || echo "ไม่มี claude"
# ถ้าไม่มี (ติดตั้งในบัญชีนี้ ไม่ต้อง sudo) แล้วรัน claude ครั้งหนึ่งเพื่อเข้าสู่ระบบ:
#   curl -fsSL https://claude.ai/install.sh | bash
#   claude
claude --version | tee "$D/version.txt"; uname -m | tee -a "$D/version.txt"
./.venv/bin/python -m aipc.skills.forge new 'อยากได้สกิลช่วยเขียนคำอวยพรวันเกิด' --out "$D/proposals" 2>&1 | tee "$D/forge.txt"
echo "forge exit=${PIPESTATUS[0]}" | tee -a "$D/forge.txt"
{
  stat -c '%a %U %n' ~ ~/.claude ~/.claude.json 2>&1
  ls -la ~/.claude | head -20
  sudo -u testb ls /home/aipc2030/.claude; echo "testb ls exit=$?"
  echo "ไฟล์ที่มีโทเคนใน /etc/aipc, unit ของผู้ใช้, /etc/environment: $(sudo grep -rIl -e 'sk-ant' -e 'CLAUDE_CODE_OAUTH_TOKEN' -e 'ANTHROPIC_API_KEY' /etc/aipc /etc/systemd/user /etc/environment 2>/dev/null | wc -l)"
} 2>&1 | tee "$D/credential.txt"
```
- **ผ่านเมื่อ:** `claude --version` ตอบได้ และ uname = aarch64 · `forge exit=0` และรายงานใน forge.txt บอก ≤ 2 รอบ · home ของ aipc2030 เป็น 700 · testb ls exit ≠ 0 (Permission denied) · ไฟล์ที่มีโทเคน = 0
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-forge/` (version.txt, forge.txt, credential.txt, proposals/, README.md) · ห้ามคัดไฟล์ใน ~/.claude มาใส่ · `git add "$D" && git commit -m "bench(pi5): forge บน Pi 5 + ที่เก็บ credential"`

### V26 เวอร์ชันไลบรารีและเทสต์ทั้งชุดบน Pi 5
- **ตอบข้อ audit:** deploy-6, data-7
- **ทำไมต้องทดสอบ:** เวอร์ชันไลบรารียืนยันแล้วบน Pi 4 เท่านั้น (`docs/benchmarks/2026-09-28-card0012-pi4/README.md`) · ยังไม่มีไฟล์ผลเทสต์ของ Pi 5 · บนวินโดวส์ `fsync_dir` ถูกข้าม (`src/aipc/fsutil.py:16`) ต้องรันบน Linux จริง
- **ต้องอยู่หน้าเครื่อง:** ไม่ (SSH ได้) · **เวลา:** ~15 นาที · **ความเสี่ยง:** ไม่มี (ใช้ CPU ระหว่างรัน) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** วัดรอบ 2 เสร็จ (ห้ามรันซ้อนการวัด) · git tree สะอาด · ไฟล์ freeze ของ `/opt/aipc-v2` ได้หลังขั้น 9 (ถ้ายังไม่มี บรรทัดนั้นข้ามเอง แล้วรันซ้ำหลังขั้น 9)
```sh
cd ~/aipc
git status --porcelain | wc -l                      # ต้องได้ 0
D=docs/benchmarks/$(date +%F)-pi5-install && mkdir -p "$D"
./.venv/bin/pip freeze --exclude-editable > "$D/pip-freeze-dev.txt"
[ -x /opt/aipc-v2/.venv/bin/pip ] && /opt/aipc-v2/.venv/bin/pip freeze > "$D/pip-freeze-opt.txt"
# pip เขียนชื่อ PySide6 เป็น PySide6_Essentials (ขีดล่าง) จึงรับทั้ง - และ _
grep -i -H -E '^(pyside6[-_]essentials|shiboken6|opencv[-_]python[-_]headless|numpy|ruff)==' "$D"/pip-freeze-*.txt
# เทสต์ที่เก็บข้อมูล (นัด ใบหน้า แชท) ก่อน แล้วทั้งชุด
{ git rev-parse HEAD; vcgencmd get_throttled; loginctl list-sessions --no-legend | wc -l
  ./.venv/bin/python -m unittest tests.test_skill_reminders tests.test_vision_store tests.test_chat 2>&1 | tail -4; } > "$D/unittest-data.txt"
{ git rev-parse HEAD; vcgencmd get_throttled
  ./.venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -4; } > "$D/unittest-all.txt"
cat "$D/unittest-data.txt" "$D/unittest-all.txt"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ทุกไฟล์ freeze มี `PySide6_Essentials==6.11.2` (หรือ `PySide6-Essentials==6.11.2`), `shiboken6==6.11.2`, `opencv-python-headless==5.0.0.93`, `numpy==2.5.3` ครบ 4 ตัว · `ruff==0.16.8` มีใน dev · ทั้งสองไฟล์ unittest มีบรรทัด `OK` (หรือ `OK (skipped=N)`) ไม่มี `FAILED` · จดจำนวน Ran และ skipped (Pi 4 เคยข้าม 0)
- **บันทึกผล:** `git add docs/benchmarks && git commit -m "bench(pi5): เวอร์ชันไลบรารี + ผลเทสต์ทั้งชุด"`

### V27 สำรองข้อมูลผู้ใช้และลองกู้ลงโฟลเดอร์ชั่วคราว
- **ตอบข้อ audit:** data-1
- **ทำไมต้องทดสอบ:** ADR-012 บอกให้คัดลอก home ด้วยมือ แต่ hash ของ PIN อยู่ที่ `/var/lib/aipc/recovery/` (`accounts/helper.py:33,116`) และค่า AI อยู่ที่ `/etc/aipc` ซึ่งไม่อยู่ใน home · ยังไม่เคยลองกู้
- **ต้องอยู่หน้าเครื่อง:** ไม่ (SSH ได้ · แต่บัญชีทดสอบต้องสมัครที่จอไว้ก่อน) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ ไม่เปลี่ยนค่าระบบ · ไฟล์สำรองมี hash ของ PIN, แม่แบบใบหน้า, คีย์ SSH ใน home → เก็บเป็นความลับ ห้ามเข้า git ห้ามขึ้น cloud · **ย้อนกลับ:** ไม่เปลี่ยนระบบ · ไฟล์ชั่วคราวลบด้วย `sudo rm -rf /var/tmp/restore-test` (ถามก่อนลบ .tgz ด้วย `rm -i`)
- **ก่อนเริ่ม:** ทำขั้น 9 ครบ · มีบัญชีทดสอบอย่างน้อย 1 บัญชี ที่มีนัดและแชท · บัญชีทดสอบออกจากระบบแล้ว (ไฟล์ไม่เปลี่ยนระหว่าง diff) · ไม่มีการวัดค้าง
```sh
loginctl list-sessions                              # ต้องไม่มีเซสชันของบัญชีทดสอบ
sudo -v
T=/var/tmp/aipc-data-$(date +%F).tgz
# ไม่เอาโมเดล venv llama.cpp cache ชุดข้อมูลใบหน้า และไฟล์ bundle (ใหญ่ และสร้างใหม่ได้)
time sudo tar --numeric-owner -czpf "$T" \
  --exclude='aipc/models' --exclude='.venv' --exclude='llama.cpp' --exclude='.cache' \
  --exclude='datasets' --exclude='*.tgz' --exclude='*.bundle' \
  /home /var/lib/aipc /etc/aipc /etc/greetd 2>/tmp/backup-err.txt; echo "exit=$?"
grep -v -e 'Removing leading' -e 'file changed as we read it' /tmp/backup-err.txt   # ต้องไม่มีบรรทัดออก
sudo ls -lh "$T"
echo "ตั้ง PIN ไว้: $(sudo ls /var/lib/aipc/recovery | wc -l) · ใน tar: $(sudo tar -tzf "$T" | grep -c '^var/lib/aipc/recovery/.')"
sudo tar -tzf "$T" | grep -x 'etc/aipc/llm.conf'
# ลองกู้ลงโฟลเดอร์ชั่วคราว แล้วเทียบกับของจริง
sudo mkdir -m 700 /var/tmp/restore-test
sudo tar -xzpf "$T" --numeric-owner -C /var/tmp/restore-test
sudo diff -r /var/lib/aipc /var/tmp/restore-test/var/lib/aipc && echo 'var/lib/aipc ตรง'
sudo diff -r /etc/aipc /var/tmp/restore-test/etc/aipc && echo 'etc/aipc ตรง'
U=ชื่อบัญชีทดสอบ                                    # แก้เป็นชื่อจริงก่อนรัน
sudo diff -r /home/$U/.local/share/aipc /var/tmp/restore-test/home/$U/.local/share/aipc && echo 'ข้อมูลผู้ใช้ตรง'
sudo rm -rf /var/tmp/restore-test
sudo chown "$USER": "$T" && chmod 600 "$T" && sha256sum "$T"
# บน PC (PowerShell):
#   $PI = "aipc2030@ใส่ไอพีของ Pi"
#   New-Item -ItemType Directory -Force D:\aipc-images
#   scp "${PI}:/var/tmp/aipc-data-*.tgz" D:\aipc-images\
#   certutil -hashfile D:\aipc-images\aipc-data-<วันที่>.tgz SHA256    # ต้องตรงกับ sha256sum บน Pi
# ตรงแล้วเท่านั้น จึงลบบน Pi (ตอบ y เอง):
rm -i "$T"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) tar exit=0 (หรือ exit=1 ที่ backup-err มีแค่ "file changed as we read it" และบรรทัด grep -v ไม่มีอะไรออก) · จำนวนไฟล์ใน tar เท่ากับจำนวน "ตั้ง PIN ไว้" · มี `etc/aipc/llm.conf` · ขึ้น "ตรง" ครบ 3 บรรทัด · sha256 บน PC = บน Pi · จดขนาดไฟล์และเวลา · ข้อจำกัด: กู้ได้เฉพาะบน image ที่มีบัญชีเหล่านี้อยู่แล้ว (UID ต้องตรง · ไม่ได้สำรอง /etc/passwd /etc/shadow)
- **บันทึกผล:** `D=docs/benchmarks/$(date +%F)-pi5-backup && mkdir -p $D` เขียน `$D/README.md` (ขนาด เวลา จำนวนไฟล์ ผล diff · ห้ามใส่เนื้อหาไฟล์หรือไฟล์ .tgz) → `git add docs/benchmarks && git commit -m "bench(pi5): สำรองข้อมูล home + /var/lib/aipc + /etc/aipc และลองกู้"`

### V28 เทสต์ทั้งชุด + รุ่นไลบรารีบน Pi 5
- **ตอบข้อ audit:** evidence-0, vision-7
- **ทำไมต้องทดสอบ:** STATUS บรรทัด 40 มีแค่ผลวินโดวส์ (457 ผ่าน ข้าม 10) และ Pi 4 (406) · ไม่มีไฟล์ใน repo ว่ารันเทสต์บน Pi 5 แล้ว · ไม่มีไฟล์ pip freeze ของ Pi 5 ยืนยันว่ารุ่นตรง `constraints.txt` (OpenCV 5.0.0.93, numpy 2.5.3, PySide6-Essentials 6.11.2, shiboken6 6.11.2) · ตอนนี้ repo มี `def test_` 475 ตัว เลข 457 จึงเก่า
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~10 นาที · **ความเสี่ยง:** ต่ำ ใช้ CPU ระหว่างรัน · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ผ่าน "เช็กเครื่องว่าง" · ไม่มีการวัด LLM ค้าง · บน PC รันเทสต์ที่ commit เดียวกัน (`.\.venv\Scripts\python.exe -m unittest discover -s tests -t .`) แล้วจดบรรทัด `Ran N tests`
```sh
cd ~/aipc
git status --porcelain | wc -l      # ต้องได้ 0
./.venv/bin/python -m aipc.vision.models check   # ต้อง 'ผ่าน' 4 บรรทัด · ไม่ผ่าน = เทสต์ SFace จะถูกข้าม → ./.venv/bin/python -m aipc.vision.models fetch
W=~/bench-out/$(date +%F)-pi5-unittest; mkdir -p $W
./.venv/bin/python -m aipc.bench machine > $W/machine.json   # commit + dirty + throttle
./.venv/bin/python -m unittest discover -s tests -t . > $W/unittest.txt 2>&1; echo exit=$? >> $W/unittest.txt
grep -E '^Ran |^OK|^FAILED' $W/unittest.txt
./.venv/bin/pip freeze > $W/pip-freeze.txt
grep -iE '^(opencv-python-headless|numpy|pyside6[-_]essentials|shiboken6)==' $W/pip-freeze.txt
```
- **ผ่านเมื่อ:** `Ran N tests` โดย N เท่ากับบน PC ที่ commit เดียวกัน · บรรทัดผลเป็น `OK` เฉย ๆ ไม่มี `(skipped=` (Pi 4 ก็ไม่ข้าม · ข้าม = ขาดไลบรารีหรือโมเดล ให้ดูว่าข้อไหน) · `exit=0` · freeze ได้ครบ 4 บรรทัด: `opencv-python-headless==5.0.0.93`, `numpy==2.5.3`, `PySide6_Essentials==6.11.2` (pip เขียนขีดล่าง), `shiboken6==6.11.2` · `machine.json` มี `"git_dirty": false`
- **บันทึกผล:**
```sh
cp -r $W docs/benchmarks/
git add docs/benchmarks/$(basename $W) && git commit -m 'bench(pi5): เทสต์ทั้งชุดบน Pi 5 + pip freeze'
```
จากนั้นแก้ STATUS บรรทัด 40 บน PC ให้ลิงก์ไฟล์นี้ (ดู code_fixes evidence-0)

### V29 ใบหน้าจากไฟล์ LFW: เวลา RAM ความแม่นยำ fp32/int8
- **ตอบข้อ audit:** vision-0, evidence-4, vision-7, vision-8
- **ทำไมต้องทดสอบ:** ตัวเลขใบหน้ามีแต่ Pi 4 (ต่อเฟรม median 88.2 / p95 113.3 ms · RAM +129 MB · int8 embed ช้ากว่า 3.2×) และ LFW 99.35% วัดบนวินโดวส์ (ระดับ 3) · `vision.bench` ไม่บันทึก commit และอ่าน throttle ครั้งเดียวตอนจบ (`src/aipc/vision/bench.py` บรรทัด 90–105) · Pi 5 มีบิต 'เคยเกิด' 0xe0000 ติดมาตั้งแต่บูต ค่าตอนจบจึงบอกไม่ได้ว่า throttle ระหว่างวัดไหม → ต้องเก็บ commit และเฝ้า throttle เองข้างผล
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~35 นาที (คัดไฟล์ 180 MB + วัด ~15 นาที) · **ความเสี่ยง:** ต่ำ · ภาพ LFW อยู่นอก repo (`~/datasets`) ห้ามเข้า git · **ย้อนกลับ:** ไม่เปลี่ยนระบบ · ลบชุดข้อมูลได้เองเมื่อเลิกใช้: `rm -r ~/datasets ~/lfw.tgz`
- **ก่อนเริ่ม:** ทำหลัง section "เทสต์ทั้งชุด" · คัดไฟล์และโหลดโมเดล int8 **ก่อน** เช็กเครื่องว่าง (ห้ามดาวน์โหลดระหว่างวัด) · ชุดภาพเท่ากับ Pi 4 (`list_people` เรียงชื่อ · 200 ภาพแรก)
```powershell
# บน PC (PowerShell) ครั้งเดียว · ใส่ที่อยู่ Pi เอง
cd D:\aipc-datasets
scp lfw.tgz pairs.txt aipc2030@<ที่อยู่ Pi>:~/
```
```sh
# บน Pi
cd ~/aipc
sha256sum ~/lfw.tgz ~/pairs.txt | cut -c1-8     # ต้องได้ 055f7d9c และ ea42330c (ตาม README ของผล LFW เดิม)
mkdir -p ~/datasets && tar -xzf ~/lfw.tgz -C ~/datasets && mv ~/pairs.txt ~/datasets/
ls ~/datasets/lfw | wc -l                        # ต้องได้ 5749 โฟลเดอร์ (ชื่อคน)
./.venv/bin/python -m aipc.vision.models check   # ต้อง 'ผ่าน' 4 บรรทัด
./.venv/bin/python -m aipc.vision.models fetch int8   # ใช้เน็ต ~10 MB · ทำก่อนวัด
# เช็กเครื่องว่าง (ท่อน 1 ของ section แรก) + รอให้เย็น
pgrep -af 'llama-|curl|wget|sha256sum|measure-llm|skill_select' || echo ไม่มีงานค้าง
until [ $(vcgencmd measure_temp | tr -dc 0-9 | cut -c1-2) -lt 55 ]; do sleep 15; done
git status --porcelain | wc -l                   # ต้องได้ 0
W=~/bench-out/$(date +%F)-pi5-face-lfw; mkdir -p $W
{ date -Is; git rev-parse HEAD; uname -r; cat /proc/loadavg; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
  ./.venv/bin/python -c 'import cv2;print("opencv",cv2.__version__,"threads",cv2.getNumThreads())'
  loginctl list-sessions --no-legend; vcgencmd get_throttled; } > $W/env.txt
./.venv/bin/python -m aipc.bench machine > $W/machine.json
# เฝ้า throttle ทุก 2 วิ · now = บิต 'ตอนนี้' (0–3) · บิต 'เคยเกิด' 0xe0000 ติดมาตั้งแต่บูตแล้ว
mon() { while :; do v=$(vcgencmd get_throttled | cut -d= -f2); echo $(date +%T) $v now=$((v & 0xF)) $(vcgencmd measure_temp) $(vcgencmd measure_clock arm) fan=$(cat /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input); sleep 2; done; }
mon > $W/thermal.txt & MON=$!
./.venv/bin/python -m aipc.vision.bench ~/datasets/lfw --limit 200 --rounds 5 --sface fp32 --out $W/bench-fp32.json > /dev/null
./.venv/bin/python -m aipc.vision.bench ~/datasets/lfw --limit 200 --rounds 5 --sface int8 --out $W/bench-int8.json > /dev/null
./.venv/bin/python -m aipc.vision.evaluate ~/datasets/lfw --pairs ~/datasets/pairs.txt --pick centre --name LFW --out $W/lfw-standard > /dev/null
kill $MON; vcgencmd get_throttled >> $W/env.txt
grep -c 'now=[1-9]' $W/thermal.txt               # ต้องได้ 0
# สรุปตัวเลข
./.venv/bin/python - $W <<'EOF' | tee $W/summary.txt
import json, sys, pathlib
W = pathlib.Path(sys.argv[1])
for v in ('fp32', 'int8'):
    d = json.loads((W / f'bench-{v}.json').read_text(encoding='utf-8'))
    t, r = d['per_frame_ms'], d['peak_rss_mb']
    print(v, 'total', t['total'], 'embed', t['embed'], 'load_ms', d['model_load_ms'],
          'rss_models_add', round(r['after_models'] - r['before_models'], 1), 'opencv', d['opencv'], 'images', d['images'])
m = json.loads((W / 'lfw-standard/metrics.json').read_text(encoding='utf-8'))
print('LFW', m['accuracy_mean'], m['accuracy_std'], 'no_face', m['no_face_images'], 'commit', m['commit'])
print(m['models_sha256'])
EOF
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) `machine.json` มี `"git_dirty": false` · `now=[1-9]` = 0 บรรทัด · opencv = 5.0.0 · images = 200 ทั้งสองไฟล์ · fp32: total median ≤ 88.2 ms และ p95 ≤ 113.3 ms (ไม่ช้ากว่า Pi 4) · RAM โมเดล (after − before) ≤ 300 MB · LFW: accuracy_mean อยู่ในช่วง 0.9925–0.9945, no_face = 0, commit ไม่มี `-dirty`, sha256 ของ YuNet/SFace ตรงกับ `docs/benchmarks/2026-09-24-face-lfw-standard/metrics.json` (8f2383e4… / 0ba9fbfa…) · int8: ใช้ fp32 ต่อ เว้นแต่ embed median ของ int8 ≤ 0.7 × ของ fp32 (ถึงเกณฑ์ก็ยังต้องชั่งกับความแม่นยำที่ลดและการลงทะเบียนใหม่) · หมายเหตุ: p95 ของ vision.bench เป็นแบบ interpolate ไม่ใช่ nearest-rank · โหมด `--pairs` ไม่สร้างรูปกราฟ (มีแค่ metrics.json + scores.csv.gz)
- **บันทึกผล:**
```sh
cp -r $W docs/benchmarks/
git status --short docs/benchmarks   # ต้องไม่มีไฟล์ภาพ .jpg
git add docs/benchmarks/$(basename $W) && git commit -m 'bench(pi5): ใบหน้าจากไฟล์ LFW เวลา RAM ความแม่นยำ fp32/int8'
```

## C · เปลี่ยนค่าระบบ (สำรองก่อน · มีคำสั่งย้อนทุกข้อ)

### V30 จำกัดขนาด journald 200 MB
- **ตอบข้อ audit:** hw-os-7, data-5 (ส่วนตั้งค่า)
- **ทำไมต้องทดสอบ:** BRIEF 5.9 ข้อ 12 ให้จำกัด journald ≤ 200 MB · วันนี้ journald ใช้ค่าเริ่มต้น (8M) · ไม่มีสคริปต์ใดใน `scripts/` ตั้งค่านี้ (grep `journald|SystemMaxUse` ไม่เจอ) · llama-server ของ service ส่ง log เข้า journal ทุกคำขอ
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้) · **เวลา:** ~5 นาที · **ความเสี่ยง:** ต่ำ · ไม่ต้องรีบูต · restart journald ไม่ลบ log เดิม · **ย้อนกลับ:** `sudo rm /etc/systemd/journald.conf.d/aipc.conf && sudo systemctl restart systemd-journald`
- **ก่อนเริ่ม:** ทำหลัง section สแนปช็อต (มีค่าก่อนเปลี่ยนแล้ว) · Pakon อนุมัติการแก้ค่าระบบ · ไม่มีการวัดค้าง · `git status --porcelain` ว่าง
```sh
# ต้องยังไม่มีไฟล์ aipc.conf (ถ้ามี ให้หยุดและดูเนื้อหาก่อน · ห้ามทับ)
ls -l /etc/systemd/journald.conf.d/ 2>&1
[ -e /etc/systemd/journald.conf.d/aipc.conf ] && echo "หยุด: มีไฟล์อยู่แล้ว"
sudo mkdir -p /etc/systemd/journald.conf.d
printf '# aipc: BRIEF 5.9 ข้อ 12 · journald <= 200 MB\n[Journal]\nSystemMaxUse=200M\n' | sudo tee /etc/systemd/journald.conf.d/aipc.conf
sudo systemctl restart systemd-journald
# ตรวจ
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-journald; mkdir -p $D
{ systemd-analyze cat-config systemd/journald.conf | grep -Ev '^\s*(#|$)'
  [ -d /var/log/journal ] && echo "เก็บลงการ์ด" || echo "เก็บใน RAM (SystemMaxUse ไม่มีผล · ใช้ RuntimeMaxUse ค่าเริ่มต้น)"
  journalctl --disk-usage
  journalctl -b -u systemd-journald --no-pager | tail -3
} | tee $D/after.txt
git add $D && git commit -m "bench(pi5): จำกัด journald SystemMaxUse=200M"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ผล cat-config มี `SystemMaxUse=200M` · ถ้าเก็บลงการ์ด: บรรทัด "System Journal ... max" ของ systemd-journald ต้อง ≤ 200.0M · ถ้าเก็บใน RAM: บรรทัด "Runtime Journal ... max" ต้อง ≤ 200.0M และจดว่าค่าที่ตั้งไม่มีผลกับการ์ด · `journalctl --disk-usage` ≤ 200 MB
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-journald/after.txt` · ภายหลังย้ายค่านี้เข้าสคริปต์ติดตั้งที่มี dry-run (ดู code_fixes)

### V31 เปิด memory cgroup ให้ MemoryMax มีผลจริง
- **ตอบข้อ audit:** hw-os-1, llm-3 (ส่วน MemoryMax)
- **ทำไมต้องทดสอบ:** วัดบน Pi 5 วันนี้: `/proc/cmdline` มี `cgroup_disable=memory` (firmware เติมให้) และ `cgroup.controllers` = `cpuset cpu io pids` ไม่มี memory · แปลว่า `MemoryMax=4G` ใน `scripts/pi/session/aipc-llm.service` ตอนนี้ไม่มีผล · ผลบน Pi 4 ที่บอกว่า "มีผล" เป็นแค่ค่าที่ตั้ง ไม่ได้พิสูจน์ว่าบังคับได้
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · SSH หลุดตอนรีบูต · เตรียมตัวอ่านการ์ดของ PC ไว้เผื่อบูตไม่ขึ้น) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ-ปานกลาง · แก้ไฟล์บูต **ต้องรีบูต** · ถ้าบรรทัดแตกเป็นสองบรรทัด เครื่องอาจบูตไม่ขึ้น · **ย้อนกลับ:** `sudo cp /boot/firmware/cmdline.txt.bak-memcg /boot/firmware/cmdline.txt && sudo reboot` · **ถ้าบูตไม่ขึ้น:** ปิดเครื่อง ถอดการ์ดเสียบ PC → เปิดไดรฟ์ `bootfs` → ลบ `cmdline.txt` → เปลี่ยนชื่อ `cmdline.txt.bak-memcg` เป็น `cmdline.txt` → เสียบคืนแล้วเปิดเครื่อง
- **ก่อนเริ่ม:** ทำหลัง section สแนปช็อต · Pakon ตัดสินแล้วว่าจะเปิด (ถ้าไม่เปิด ให้เขียนข้อจำกัดในเล่มว่าพึ่ง OOM killer ของเคอร์เนล + Restart=on-failure แล้วข้าม section นี้) · ไม่มีการวัดค้าง · ไม่มีใครใช้หน้าจอ (บันทึกงานใน desktop ของ aipc2030 ก่อน · รีบูตแล้ว desktop ปิด) · `git status --porcelain` ว่าง
```sh
# 0) ต้องได้ 0 (ถ้าได้ 1 = เคยเติมแล้ว ข้ามไป "หลังรีบูต")
grep -c cgroup_enable=memory /boot/firmware/cmdline.txt
# 1) สำรอง (ไว้ในพาร์ทิชันบูต = เปิดจาก PC วินโดวส์ได้)
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak-memcg
# 2) เติมท้ายบรรทัดเดียว (ห้ามขึ้นบรรทัดใหม่)
sudo sed -i '1 s/$/ cgroup_enable=memory/' /boot/firmware/cmdline.txt
wc -l /boot/firmware/cmdline.txt     # ต้องได้ 0 หรือ 1 ห้ามเกิน
diff /boot/firmware/cmdline.txt.bak-memcg /boot/firmware/cmdline.txt   # ต่างแค่คำท้ายบรรทัด
sync; sudo reboot

# ===== หลังรีบูต (SSH เข้าใหม่) =====
cd ~/aipc; U=$(id -u); O=~/memcg-check.txt
{ tr ' ' '\n' < /proc/cmdline | grep cgroup
  echo "top: $(cat /sys/fs/cgroup/cgroup.controllers)"
  echo "user@$U: $(cat /sys/fs/cgroup/user.slice/user-$U.slice/user@$U.service/cgroup.controllers)"
  ls /sys/fs/cgroup/user.slice/memory.swap.max 2>&1
  vcgencmd get_throttled; vcgencmd measure_temp
} | tee $O
# 3) ลองว่าเพดานบังคับได้จริง: ขอ RAM 400 MB ใต้เพดาน 200 MB ห้ามใช้ swap → ต้องถูกปิด
#    --pipe = ให้ข้อความของโปรแกรมออกจอ (ไม่งั้นไปอยู่ใน journal)
systemd-run --user --wait --pipe -p MemoryMax=200M -p MemorySwapMax=0 \
  python3 -c "b = b'x' * (400 << 20); print('ไม่ถูกปิด', len(b))" 2>&1 | tee -a $O
# 4) ความเร็วหลังเปิด memcg · เพิ่งบูต = บิต throttle สะอาด
git status --porcelain      # ต้องว่าง
L=$(git -C ~/llama.cpp rev-parse --short HEAD)
./.venv/bin/python -m aipc.spikes.llm --bench ~/llama.cpp/build/bin/llama-bench \
  --model models/typhoon2.5-qwen3-4b-q4_k_m.gguf --label typhoon25-4b-q4km-memcg --size 3-4b \
  --threads 3 --meta llama_cpp=$L --meta memcg=on | tail -4
git add docs/benchmarks && git commit -m "bench(pi5): llm typhoon25 threads 3 หลังเปิด memory cgroup"
# 5) เก็บผลตรวจ
D=docs/benchmarks/$(date +%F)-pi5-memcg; mkdir -p $D; cp $O $D/check.txt
git add $D && git commit -m "bench(pi5): เปิด memory cgroup + ทดสอบ MemoryMax บังคับได้"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) คำว่า `memory` อยู่ทั้งใน `top:` และ `user@UID:` · คำสั่งข้อ 3 ไม่พิมพ์ "ไม่ถูกปิด" และมี `oom-kill` หรือ `status=9/KILL` ในผล · รายงาน t3 ขึ้น "ใช้เป็นหลักฐานระดับ 4 ได้" และ tg median ≥ 4.40 tok/s (= 4.633 − 5% · ค่าเสนอ · ยืนยันว่า memcg ไม่ทำให้ช้าลง) · ถ้าไม่มี memory ในรายการ = ไม่ผ่าน ให้ย้อนกลับและเขียนเป็นข้อจำกัด · ถ้าข้อ 3 พิมพ์ "ไม่ถูกปิด" และไม่มีไฟล์ memory.swap.max = จดว่าเพดาน swap ใช้ไม่ได้ (ไม่ใช่ว่า MemoryMax ใช้ไม่ได้) · ถ้ารายงาน t3 ขึ้น "ใช้ไม่ได้" (throttle) ให้จดตามนั้น ห้ามรันซ้ำจนผ่าน
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-memcg/check.txt` + `<วันที่>-pi5-llm-typhoon25-4b-q4km-memcg-t3.*` · หมายเหตุ: ไฟล์ t3 ของ 2026-09-29 มี `throttled_before` = 917504 (0xE0000) ตัววัดจึงมองไม่เห็น throttle ระหว่างรอบ · ไฟล์ใหม่นี้ (บูตใหม่) ใช้แทนเป็นหลักฐาน t3

### V32 เปิดชาร์จแบต RTC
- **ตอบข้อ audit:** hw-os-6
- **ทำไมต้องทดสอบ:** BRIEF หัวข้อ 2 กำหนดแบต RTC ทางการ + `dtparam=rtc_bbat_vchg=3000000` แต่ doctor บน Pi 5 วัดได้ charging_voltage = 0 · แบตที่ไม่ได้ชาร์จจะหมดในที่สุด
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ดูรุ่นแบตด้วยตาก่อน · แก้ไฟล์บูตแล้วรีบูต) · **เวลา:** ~15 นาที · **ความเสี่ยง:** ปานกลาง · แก้ไฟล์บูต **ต้องรีบูต** · **ห้ามใช้กับถ่านที่ชาร์จไม่ได้ (เช่น CR2032)** ใช้ได้เฉพาะแบตทางการที่ชาร์จได้ (Li-Mn รุ่น ML-2020) · **ย้อนกลับ:** `sudo cp /boot/firmware/config.txt.bak-rtc /boot/firmware/config.txt && sudo reboot` · **ถ้าบูตไม่ขึ้น:** ปิดเครื่อง ถอดการ์ดเสียบ PC → ไดรฟ์ `bootfs` → ลบ `config.txt` → เปลี่ยนชื่อ `config.txt.bak-rtc` เป็น `config.txt` → เสียบคืน
- **ก่อนเริ่ม:** ทำหลัง section นาฬิกาออฟไลน์ · Pakon ยืนยันด้วยตาว่าแบตเป็นแบบชาร์จได้ และตัดสินใจเปิดเอง · ไม่มีใครใช้หน้าจอ · ไม่มีการวัดค้าง
```sh
# 0) ต้องได้ 0 (ถ้าได้ 1 = มีค่าอยู่แล้ว ห้ามเพิ่มซ้ำ)
grep -c rtc_bbat_vchg /boot/firmware/config.txt
# 1) สำรองไว้ในพาร์ทิชันบูต (เปิดจาก PC วินโดวส์ได้)
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak-rtc
tail -5 /boot/firmware/config.txt
# 2) เพิ่มใต้ [all] เพื่อไม่ให้ไปตกในหัวข้อเฉพาะรุ่น
printf '\n[all]\ndtparam=rtc_bbat_vchg=3000000\n' | sudo tee -a /boot/firmware/config.txt
diff /boot/firmware/config.txt.bak-rtc /boot/firmware/config.txt   # ต้องเพิ่มแค่ 3 บรรทัด
sync; sudo reboot
# ===== หลังรีบูต =====
cat /sys/class/rtc/rtc0/charging_voltage      # ต้องได้ 3000000
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-rtc-charge; mkdir -p $D
./.venv/bin/python -m aipc.doctor --save --out $D
git add $D && git commit -m "bench(pi5): doctor หลังเปิดชาร์จแบต RTC"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) charging_voltage = 3000000 · doctor ข้อ "นาฬิกา RTC" เป็น "ผ่าน" และขึ้น "ชาร์จแบตที่ 3.0 V" · ถ้า section นาฬิกาออฟไลน์ไม่ผ่าน ให้ทำ section นั้นซ้ำหลังชาร์จไว้อย่างน้อย 1 วัน (โฟลเดอร์ใหม่)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-rtc-charge/`

### V33 forge บน Pi 5 (Claude Code ARM64) และค่าตั้งของบัญชีผู้ดูแล
- **ตอบข้อ audit:** skills-7, gaps-0 (ส่วน "forge ทำงานบน Pi ได้ไหม")
- **ทำไมต้องทดสอบ:** forge เคยรันแค่บนวินโดวส์ (ระดับ 3 · `docs/benchmarks/2026-09-29-skill-forge/README.md` · 34/38 วิ) · `claude -p` รันด้วย `--tools ""` แต่ไม่ได้ใช้ `--bare` (`forge.py` บรรทัด 70–71) จึงยังโหลด CLAUDE.md/hook/MCP ของบัญชีผู้ดูแล · ยังไม่รู้ว่ามี `claude` บน Pi 5 หรือไม่
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · ตอน login ของ Claude Code เปิดลิงก์บนมือถือ/PC ได้) · **เวลา:** ~20 นาที · **ความเสี่ยง:** ต่ำ · ใช้เน็ตและโควตา subscription · ถ้ายังไม่มี Claude Code จะติดตั้งลงบัญชี aipc2030 และเก็บข้อมูล login ไว้ใน ~/.claude ของบัญชีนี้ · **ย้อนกลับ:** ถ้าติดตั้งใหม่ในขั้นนี้เท่านั้น: `rm -f ~/.local/bin/claude; rm -rf ~/.local/share/claude` · ถ้า ~/.claude มีอยู่ก่อน ให้คืนจากสำเนาที่ทำในข้อ 1 (ห้ามลบทิ้งเฉย ๆ)
- **ก่อนเริ่ม:** การวัด LLM จบแล้ว (ห้ามรันคู่กับการวัด) · มีเน็ต · ไม่มีดาวน์โหลดอื่นค้าง · `git status --porcelain` ว่าง
```sh
cd ~/aipc; PY=./.venv/bin/python
# 1) มี Claude Code ไหม · สำรอง ~/.claude ก่อนเปลี่ยน
export PATH="$HOME/.local/bin:$PATH"      # ตัวติดตั้งวางไว้ที่นี่ · shell ที่เปิดก่อนติดตั้งยังไม่มีใน PATH
command -v claude && claude --version
[ -d ~/.claude ] && cp -a ~/.claude ~/.claude.bak-$(date +%F)
# ถ้าไม่มี claude: ติดตั้งตัว native (Linux ARM64) แล้ว login ครั้งเดียว
#   curl -fsSL https://claude.ai/install.sh | bash
#   claude            # ทำตามขั้น login แล้วพิมพ์ /exit
# 2) ค่าตั้งที่ claude -p จะโหลด (ต้องไม่มี hooks / mcpServers) · ไฟล์ login ต้องอ่านได้เฉพาะเจ้าของ
grep -nE '"hooks"|"mcpServers"' ~/.claude/settings.json ~/.claude.json 2>/dev/null; ls -l ~/.claude/CLAUDE.md 2>/dev/null
stat -c '%a %U %n' ~/.claude ~/.claude/.credentials.json 2>/dev/null
# 3) สร้างสกิล 1 ตัวบน Pi (ยังไม่ติดตั้ง) + วัด RAM สูงสุด
command -v /usr/bin/time >/dev/null || echo "ไม่มี /usr/bin/time: sudo apt install time"
touch /tmp/forge-start
/usr/bin/time -v $PY -m aipc.skills.forge new "อยากได้สกิลเปิดยูทูบแล้วลดเสียงเหลือ 30" --out /tmp/forge-pi5 2>&1 | tee /tmp/forge-pi5.log
# 4) ต้องไม่มีไฟล์ใหม่ใน repo หรือที่เก็บข้อเสนอปกติ (ยังไม่ได้ติดตั้งอะไร)
find ~/aipc ~/.local/share/aipc -newer /tmp/forge-start -type f -not -path '*/__pycache__/*' 2>/dev/null
# 5) บันทึก
D=docs/benchmarks/$(date +%F)-skill-forge-pi5; mkdir -p $D
cp /tmp/forge-pi5/* /tmp/forge-pi5.log $D/; { claude --version; uname -m; } > $D/claude-version.txt
git add $D && git commit -m "bench(pi5): forge บน Pi 5 (Claude Code ARM64)"
```
- **ผ่านเมื่อ:** `claude --version` ทำงาน และ `uname -m` = aarch64 · grep ไม่เจอ hooks/mcpServers (ถ้าเจอ ให้จดไว้และปิดก่อนใช้ forge) · `.credentials.json` สิทธิ์ 600 เจ้าของ aipc2030 · forge จบภายใน 300 วิ และ log ขึ้น "พร้อมติดตั้ง" หรือบอกสาเหตุที่ล้มเป็นข้อ ๆ · find ไม่พบไฟล์ใหม่ · จด "Maximum resident set size" และ "Elapsed (wall clock) time" จาก /usr/bin/time
- **บันทึกผล:** `docs/benchmarks/<วันที่>-skill-forge-pi5/` (<id>.md · <id>.report.json · forge-pi5.log · claude-version.txt) · commit อยู่ในคำสั่งแล้ว

### V34 ปิด Pi Connect, linger และ rpcbind
- **ตอบข้อ audit:** hw-os-0, hw-os-5, security-1, security-4
- **ทำไมต้องทดสอบ:** วันนี้บน Pi 5 linger ของ aipc2030 = yes · rpi-connect และ rpi-connect-wayvnc enabled · rpcbind ฟังพอร์ต 111 ทั้ง TCP และ UDP · ไม่มีงานไหนของเราใช้ NFS · linger ทำให้ AI ค้างหลังออกจากระบบได้ (BRIEF 5.2 ข้อ 6) · Pi Connect ต่อออกนอกเครื่องค้างไว้ (ขัด T6)
- **ต้องอยู่หน้าเครื่อง:** ไม่ (ทาง SSH ได้ · มีคีย์บอร์ดไว้สำรอง) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · รีบูต 1 ครั้ง · ปิดแล้วเข้าผ่าน Pi Connect ไม่ได้ (SSH ผ่าน hotspot ยังใช้ได้) · **ย้อนกลับ:** `sudo systemctl unmask rpcbind.socket rpcbind.service; sudo systemctl enable --now rpcbind.socket rpcbind.service; sudo systemctl enable nfs-client.target; sudo loginctl enable-linger aipc2030; rpi-connect on || systemctl --user enable --now rpi-connect.service rpi-connect-wayvnc.service` (ค่าเดิมอยู่ใน state-before.txt)
- **ก่อนเริ่ม:** ทำหลัง section "ภาพรวมความปลอดภัยก่อนเปลี่ยน" · ไม่มีการวัดค้าง · เข้าทาง SSH ได้จริง · ไม่มีคนนั่งใช้หน้าจอ desktop (desktop ที่ aipc2030 login ค้างไว้โดยไม่มีคนนั่ง = รีบูตได้)
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-pi5-services-off; mkdir -p "$D"
# 0) สำรองสถานะเดิม (ใช้ตอนย้อน)
{ date -Is; ls /var/lib/systemd/linger
  systemctl --user list-unit-files --no-legend 'rpi-connect*'
  systemctl is-enabled rpcbind.socket rpcbind.service nfs-client.target; } 2>&1 | tee "$D/state-before.txt"
systemctl --failed --no-legend | wc -l | tee "$D/failed-before.txt"
# 1) Pi Connect ของ aipc2030 (รันในชื่อ aipc2030 ไม่ต้อง sudo)
#    สั่งทั้งสองแบบ: ไม่แน่ใจว่า off ถอด enable ให้ด้วยไหม · สั่งซ้ำไม่เสียหาย
rpi-connect off; systemctl --user disable --now rpi-connect.service rpi-connect-wayvnc.service
systemctl --user list-unit-files --no-legend 'rpi-connect*'   # ต้องไม่มีตัวไหน enabled
# 2) linger · ไม่แน่ใจว่า rpi-connect off ปิดให้ไหม จึงสั่งเอง
sudo loginctl disable-linger aipc2030
# 3) rpcbind + NFS client (disable เฉย ๆ ไม่ถอนแพ็กเกจ)
sudo systemctl disable --now rpcbind.socket rpcbind.service
sudo systemctl disable nfs-client.target
# 4) ดูว่าไม่มีใครนั่งใช้หน้าจอ แล้วรีบูต (SSH หลุด ~2 นาที)
loginctl list-sessions
sudo reboot
```
หลังรีบูต SSH เข้าใหม่:
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-services-off   # ถ้าข้ามเที่ยงคืน ใส่วันที่เดิมเอง
{
  date -Is
  echo "linger: $(ls /var/lib/systemd/linger | wc -l)"
  systemctl --user list-unit-files --no-legend 'rpi-connect*'
  systemctl --user is-active rpi-connect.service rpi-connect-wayvnc.service
  echo "โปรเซส Pi Connect: $(pgrep -c -f 'rpi-connect|wayvnc')"
  systemctl is-active rpcbind.socket rpcbind.service
  echo "พอร์ต 111: $(sudo ss -tulnH | grep -c ':111\b')"
  sudo ss -tulnpH
  echo "unit ที่ล้ม: $(systemctl --failed --no-legend | wc -l)"; systemctl --failed --no-legend
} 2>&1 | tee "$D/after.txt"
# ถ้าพอร์ต 111 ยังไม่เป็น 0 (มีตัวอื่นดึง rpcbind กลับมา) ให้ mask แล้วรีบูตอีกครั้ง:
#   sudo systemctl mask rpcbind.socket rpcbind.service
sudo ./.venv/bin/python -m aipc.doctor --audit --save --out "$D"
sudo chown -R "$USER": "$D"
```
- **ผ่านเมื่อ:** linger = 0 · rpi-connect ทุกตัวไม่ enabled และ inactive · โปรเซส Pi Connect = 0 · พอร์ต 111 = 0 (TCP และ UDP) · unit ที่ล้มหลังรีบูต ≤ ค่าใน failed-before.txt · SSH เข้าได้ · ไฟล์ audit: ข้อ remote เหลือ `ssh.service (enabled)` ตัวเดียว · ข้อ ports เหลือ `22/tcp, 22/tcp6` · ข้อ logout ยังเตือน `KillUserProcesses=no` ได้ (ปกติ หายหลังติดตั้งหน้า Login) แต่ต้องไม่มีคำว่า linger · พอร์ต UDP ที่เหลือทุกพอร์ตมีชื่อโปรเซสใน after.txt และเขียนใน README ว่าเป็นของอะไร
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-services-off/` (state-before.txt, failed-before.txt, after.txt, audit, README.md สั้น ๆ: ทำอะไร ย้อนยังไง พอร์ต UDP ที่เหลือเป็นของใคร) · `git add "$D" && git commit -m "bench(pi5): ปิด Pi Connect, linger และ rpcbind"`

### V35 จำกัด SSH + กล้อง/ไมค์ข้ามบัญชี
- **ตอบข้อ audit:** security-0, vision-6
- **ทำไมต้องทดสอบ:** สมัครเสรี + SSH เปิดรับทุกเครือข่าย (audit Pi 5 ระดับ 4) + ตัวช่วยใส่กลุ่ม video/audio ให้ทุกบัญชีใหม่ (`helper.py:32`, `173–176`) = คนที่สมัครที่หน้าเครื่องอาจเข้าทาง SSH แล้วเปิดกล้อง/ไมค์ขณะคนอื่นใช้เครื่อง · ยังไม่มีหลักฐานเลย · การ์ด 0012 (บรรทัด 154) เขียนแค่ว่าผู้ติดตั้งควรจำกัดผู้ใช้ SSH → **ขั้น ข) ต้องให้เจ้าของโปรเจกต์ตัดสินก่อนใช้ถาวร**
- **ต้องอยู่หน้าเครื่อง:** ใช่ (บัญชีทดสอบต้อง login ที่หน้าจอ) + เครื่องที่สอง (โน้ตบุ๊ก/มือถือ) ไว้ SSH · **เวลา:** ~40 นาที · **ความเสี่ยง:** กลาง · แก้ sshd ผิดอาจเข้า SSH ไม่ได้ → เปิด SSH ของ aipc2030 ค้างไว้ 1 หน้าต่าง · รัน `sshd -t` ก่อน reload · มีคีย์บอร์ด + Ctrl+Alt+F2 สำรอง · **ย้อนกลับ:** `sudo rm -f /etc/ssh/sshd_config.d/aipc.conf && sudo sshd -t && sudo systemctl reload ssh` · `sudo gpasswd -a testb video; sudo gpasswd -a testb audio`
- **ก่อนเริ่ม:** ทำหลัง section "สมัคร 5 บัญชี …" · ไม่มีการวัดค้าง · เสียบกล้อง USB (และไมค์ถ้ามี) แล้ว · ขอความยินยอมคนที่นั่งหน้าจอ (ขั้น ก อัดเสียง 2 วิแล้วลบทันที) · `/etc/ssh/sshd_config.d/aipc.conf` ต้องยังไม่มี (ไม่มีของเดิมให้สำรอง)
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-ssh-camera; mkdir -p "$D"
hostname -I; ls /etc/ssh/sshd_config.d/aipc.conf 2>&1
id testb | tee "$D/testb-before.txt"
CAM=$(readlink -f "$(ls /dev/v4l/by-id/*video-index0 | head -1)"); echo "กล้อง: $CAM"; ls -l "$CAM"
# ก) ยืนยันรู: testa นั่งอยู่หน้าจอ V2 (ไม่ได้เปิดกล้องอยู่) · จากเครื่องที่สอง: ssh testb@<IP> แล้วรันใน SSH ของ testb:
id
cd /tmp && /opt/aipc-v2/.venv/bin/python -m aipc.vision.camera test --seconds 2; echo "camera exit=$?"
arecord -l; arecord -q -d 2 -f S16_LE -r 16000 /tmp/m.wav; echo "arecord exit=$?"; ls -l /tmp/m.wav; rm -f /tmp/m.wav
exit
# ข) ปิด SSH ของบัญชีที่ไม่ใช่ผู้ดูแล (SSH ของ aipc2030 ต้องเปิดค้างไว้อีกหน้าต่าง)
printf '%s\n' '# aipc: SSH ได้เฉพาะผู้ดูแล (กลุ่ม sudo)' 'AllowGroups sudo' | sudo tee /etc/ssh/sshd_config.d/aipc.conf
sudo sshd -t && sudo systemctl reload ssh || { sudo rm -f /etc/ssh/sshd_config.d/aipc.conf; echo "sshd -t ไม่ผ่าน · เอาไฟล์ออกแล้ว"; }
sudo sshd -T | grep -i '^allowgroups' | tee "$D/sshd.txt"
# จากเครื่องที่สอง ทำอย่างละ 3 ครั้ง แล้วจด exit: ssh aipc2030@<IP> true; echo $?   และ   ssh testb@<IP> true; echo $?
# ค) จำลองว่าตัวช่วยไม่ใส่กลุ่ม video/audio แล้ว (testb ต้องไม่ได้ login อยู่)
sudo gpasswd -d testb video; sudo gpasswd -d testb audio; id testb | tee -a "$D/sshd.txt"
# ค1) testb login ที่หน้าจอ → ตั้งค่า → ลงทะเบียนใบหน้า/ทดลองสแกน · ระหว่างนั้นใน SSH ของ aipc2030:
{ echo "labwc ของ testb: $(pgrep -c -u testb -x labwc)"; ls -l "$CAM"; getfacl -p "$CAM" 2>/dev/null | grep testb; } | tee "$D/acl.txt"
# ค2) testb ออก · testa login ที่หน้าจอ · ใน SSH ของ aipc2030:
sudo -u testb sh -c 'cd /tmp && /opt/aipc-v2/.venv/bin/python -m aipc.vision.camera test --seconds 2'; echo "camera exit=$?" | tee "$D/cross.txt"
sudo -u testb arecord -l 2>&1 | head -3 | tee -a "$D/cross.txt"
sudo chown -R "$USER": "$D"
# ถ้าเจ้าของโปรเจกต์ยังไม่อนุมัติ AllowGroups ถาวร: รันคำสั่งย้อนกลับของ sshd ตอนจบ section นี้
```
- **ผ่านเมื่อ:** ก) ยืนยันรู (ไม่มีผ่าน/ตก): camera exit = 0 หรือ m.wav ใหญ่กว่า 44 ไบต์ = มีรูจริง · จดลง README · ข) `allowgroups sudo` ขึ้นใน sshd -T · aipc2030 เข้าได้ 3/3 (exit 0) · testb เข้าไม่ได้ 3/3 (Permission denied · exit 255) · ค1) testb ที่ไม่มีกลุ่ม video/audio: `labwc ของ testb` ≥ 1 · ลงทะเบียน/สแกนใบหน้าที่หน้าจอสำเร็จ ≥ 1 ครั้ง · `ls -l` ของกล้องมี + ท้ายสิทธิ์ · ค2) camera exit ≠ 0 และ arecord -l ไม่เห็นการ์ดเสียง · **ค1 และ ค2 ผ่านทั้งคู่** จึงเอา video/audio ออกจาก GROUPS ได้ (ดู code_fixes) · ไม่ผ่าน = คืนกลุ่มให้ testb และเขียนเป็นข้อจำกัดในเล่ม
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-ssh-camera/` (testb-before.txt, sshd.txt, acl.txt, cross.txt, README.md: ผลขั้น ก, ผล ssh 3+3 ครั้ง, การตัดสินของเจ้าของโปรเจกต์เรื่อง AllowGroups, คงไว้หรือย้อนแล้ว) · `git add "$D" && git commit -m "bench(pi5): จำกัด SSH + กล้อง/ไมค์ข้ามบัญชี"`

### V36 ขั้น 9 + อัปเดตครั้งแรกและ rollback ไป-กลับบน Pi 5
- **ตอบข้อ audit:** deploy-2
- **ทำไมต้องทดสอบ:** โฟลเดอร์ต่อรุ่น + symlink ผ่านบน Pi 4 แล้ว (`docs/benchmarks/2026-09-28-card0012-pi4/README.md`, `2026-09-28-card0013-pi4/README.md`) แต่ไม่ใช่ระดับ 4 · Pi 5 ยังไม่ได้ทำขั้น 9 · `install-greeter.sh` แค่ enable greetd ไม่ได้เปิดให้ (`:184-194`) จึงต้องรีบูตก่อน ถึงจะตรวจ "greetd active" ได้
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ต้องออกจาก desktop ที่ login ค้างที่ tty1 ก่อนรีบูต และดูหน้า Login ที่จอ) · **เวลา:** ~60 นาที (รวมขั้น 9) · **ความเสี่ยง:** ขั้นนี้เปลี่ยนหน้า Login ของเครื่อง · **ย้อนกลับ:** รุ่นแอป: `sudo ./scripts/pi/update-app.sh --rollback` · ถอดหน้า Login ทั้งหมด: Ctrl+Alt+F2 → login → `cd ~/aipc && sudo ./scripts/pi/install-greeter.sh --rollback` → `sudo reboot` (ตอนไม่มีคนใช้จอ)
- **ก่อนเริ่ม:** วัด LLM เสร็จ · ทำ section "ตรวจล็อก" ส่วนแรกแล้ว · มีเน็ต (apply ครั้งแรกโหลด wheel ~130 MB) · ลองกด Ctrl+Alt+F2 แล้ว login ได้ และ SSH ได้
```sh
# 1) ขั้น 9 ตาม docs/runbooks/pi5-setup.md (install-greeter --apply --session v2, install-accounts, install-llm)
# 2) ออกจาก desktop ที่จอ แล้วทาง SSH:
loginctl list-sessions                              # ต้องเหลือแค่เซสชัน SSH
sudo reboot
# 3) หลังบูต (SSH) · ที่จอต้องเห็นหน้า Login ของ V2
systemctl is-active greetd; pgrep -u _greetd -af aipc.ui | head -2
cd ~/aipc && git status --porcelain | wc -l          # ต้องได้ 0
loginctl list-sessions > /tmp/sessions.txt          # จดโหลดที่มีตอนวัดเวลา
sudo -v                                            # พิมพ์รหัสก่อน ไม่นับเวลาพิมพ์
# apply ครั้งแรก: ย้าย /opt/aipc-v2 เดิมเป็น legacy-* (install-greeter ไม่เขียน .installed-commit) แล้วสร้างรุ่น HEAD
time sudo ./scripts/pi/update-app.sh --apply 2>&1 | tee /tmp/apply-1.log
A=$(readlink -f /opt/aipc-v2); echo "ตอนนี้: $A"; cat /opt/aipc-releases/previous
time sudo ./scripts/pi/update-app.sh --rollback; readlink -f /opt/aipc-v2   # ต้องเป็น .../legacy-*
time sudo ./scripts/pi/update-app.sh --rollback; readlink -f /opt/aipc-v2   # ต้องเท่ากับ $A
sudo du -sh /opt/aipc-releases/*; systemctl is-active greetd
# 4) sudo reboot ตอนไม่มีคนใช้จอ · หลังบูต (SSH):
systemctl is-active greetd; pgrep -u _greetd -af aipc.ui | head -2; readlink -f /opt/aipc-v2
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) หลังรีบูตครั้งแรก greetd `active` และมีโปรเซส aipc.ui ของ _greetd · apply จบด้วย "เสร็จ · ใช้รุ่น …" และ log มีทั้ง "ลองเปิดหน้า Login ด้วยผู้ใช้ _greetd" และ "ลองเปิดหน้าจอเซสชัน" · apply ≤ 10 นาที (real) · rollback แต่ละครั้ง ≤ 5 วิ (real) และสลับถูก 2/2 · greetd `active` ตลอด · หลังรีบูตครั้งที่ 2: greetd active, มี aipc.ui ของ _greetd, readlink = `$A`
- **บันทึกผล:** `D=docs/benchmarks/$(date +%F)-pi5-update && mkdir -p $D && cp /tmp/apply-1.log /tmp/sessions.txt $D/` แล้วเขียน `$D/README.md` (เวลา apply/rollback, ขนาดแต่ละรุ่นจาก du, เซสชันที่เปิดอยู่ตอนวัด) → `git add docs/benchmarks && git commit -m "bench(pi5): update-app apply + rollback ไป-กลับ"`

### V37 T14 รุ่นที่พังต้องไม่ถูกสลับ
- **ตอบข้อ audit:** deploy-1, deploy-4
- **ทำไมต้องทดสอบ:** ด่านก่อนสลับ (`scripts/pi/update-app.sh:110-135`) ยังไม่เคยเห็นทำงานกับรุ่นที่พังจริง · Pi 4 เขียนว่า "ยังไม่ได้ทดสอบ" · เทสต์บนวินโดวส์ตรวจแค่ข้อความในสคริปต์
- **ต้องอยู่หน้าเครื่อง:** ไม่ (SSH ได้) · **เวลา:** ~30 นาที (สร้าง venv รอบละ ~5–10 นาที) · **ความเสี่ยง:** ต่ำถ้าสคริปต์ทำงานถูก · ถ้าสลับไปรุ่นพัง: ห้ามรีบูต · กด `--rollback` ครั้งเดียว (previous = รุ่นดี $B) · ห้ามกดซ้ำ เพราะครั้งที่ 2 จะกลับไปรุ่นพัง · **ย้อนกลับ:** `sudo ./scripts/pi/update-app.sh --rollback` แล้ว `git switch master && git branch -D <ชื่อ branch>`
- **ก่อนเริ่ม:** ทำ section "ขั้น 9 + อัปเดตครั้งแรก" แล้ว · วัด LLM เสร็จ · ไม่มีคนใช้หน้าจอ · กรณี ข. ทำหลังแก้โค้ด deploy-4 และเอาขึ้น Pi แล้วเท่านั้น
```sh
cd ~/aipc && git status --porcelain | wc -l          # ต้องได้ 0
sudo -v
B=$(readlink -f /opt/aipc-v2); P=$(cat /opt/aipc-releases/previous); echo "ก่อน: $B · previous $P"

# กรณี ก. (T14) หน้าจอ V2 เปิดไม่ขึ้น
git switch -c t14-broken
sed -i 's/^def main(argv/raise SystemExit("T14 ตั้งใจให้พัง")\n\ndef main(argv/' src/aipc/ui/__main__.py
grep -c 'T14 ตั้งใจให้พัง' src/aipc/ui/__main__.py    # ต้องได้ 1
git commit -qam 'test: T14 รุ่นที่เปิดไม่ขึ้น (ห้าม merge)'
sudo ./scripts/pi/update-app.sh --apply 2>&1 | tee /tmp/t14-a.log; echo "exit=${PIPESTATUS[0]}"
[ "$(readlink -f /opt/aipc-v2)" = "$B" ] && echo 'ไม่สลับ = ผ่าน' || echo 'สลับไปแล้ว = ไม่ผ่าน → sudo ./scripts/pi/update-app.sh --rollback ครั้งเดียว'
[ "$(cat /opt/aipc-releases/previous)" = "$P" ] && echo 'previous ไม่เปลี่ยน'
ls -a /opt/aipc-releases | grep -c '^\.building-'   # ต้องได้ 0
systemctl is-active greetd
git switch master && git branch -D t14-broken

# กรณี ข. (หลังแก้ deploy-4 เท่านั้น) ตัวเริ่ม AI พัง แต่หน้า Login ยังเปิดได้
git switch -c t14-llm
sed -i '2i if then' scripts/pi/session/aipc-llm-start
sh -n scripts/pi/session/aipc-llm-start || echo 'พังตามที่ตั้งใจ'
git commit -qam 'test: ตัวเริ่ม AI พัง (ห้าม merge)'
sudo ./scripts/pi/update-app.sh --apply 2>&1 | tee /tmp/t14-b.log; echo "exit=${PIPESTATUS[0]}"
[ "$(readlink -f /opt/aipc-v2)" = "$B" ] && echo 'ไม่สลับ = ผ่าน' || { echo 'สลับไปแล้ว = ไม่ผ่าน'; sudo ./scripts/pi/update-app.sh --rollback; }
git switch master && git branch -D t14-llm

# ท้ายสุด: sudo reboot ตอนไม่มีคนใช้จอ แล้วตรวจทาง SSH
systemctl is-active greetd; pgrep -u _greetd -af aipc.ui | head -2; readlink -f /opt/aipc-v2
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) กรณี ก.: exit ≠ 0 · log มี "หยุด: รุ่น … เปิดหน้า Login ไม่ขึ้น" · readlink = $B · previous ไม่เปลี่ยน · `.building-*` = 0 · greetd active · กรณี ข. (หลังแก้): exit ≠ 0 และ readlink = $B · ก่อนแก้ไม่ต้องรัน ข. (คาดว่าจะสลับ) · หลังรีบูต: greetd active, มี aipc.ui ของ _greetd, readlink = $B
- **บันทึกผล:** `D=docs/benchmarks/$(date +%F)-pi5-t14 && mkdir -p $D && cp /tmp/t14-*.log $D/` + `$D/README.md` (ผลแต่ละกรณี) → `git add docs/benchmarks && git commit -m "bench(pi5): T14 รุ่นที่พังไม่ถูกสลับ"`

## D · ต้องอยู่หน้าเครื่อง (จอ คีย์บอร์ด ถอดปลั๊ก กล้อง)

### V38 นาฬิกาหลังปิดเครื่องแบบออฟไลน์
- **ตอบข้อ audit:** data-6, hw-os-6 (ส่วนทดสอบ)
- **ทำไมต้องทดสอบ:** doctor บน Pi 5 (`docs/benchmarks/2026-09-29-pi5-hardware.md`) เตือน "ไม่ได้ชาร์จแบต RTC (charging_voltage = 0)" · `reminders.py` เตือนเฉพาะตอนเวลาถอยต่ำกว่า last_seen − 1 นาที · ถ้าแบตไม่เก็บเวลา นาฬิกาอาจช้าไปเท่าเวลาที่ปิดเครื่องโดยไม่มีคำเตือน (อนุมานจากโค้ด ยังไม่ได้วัด) · T5 และการสาธิตเป็นแบบออฟไลน์
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ปิด Wi-Fi ถอดปลั๊ก ดูแบตด้วยตา · SSH ผ่าน hotspot จะหลุด) · **เวลา:** ~45 นาที (รอ 30 นาที) · **ความเสี่ยง:** ไม่มี (สั่ง poweroff ก่อนถอดปลั๊ก ไม่ใช่การทดสอบไฟดับ) · **ย้อนกลับ:** `nmcli radio wifi on`
- **ก่อนเริ่ม:** ทำหลัง section soak (poweroff ล้างบิต throttle) · ไม่มีการวัดค้าง · มีมือถือที่เวลาตรง (ต่อเน็ต) ไว้เทียบ · ถอดสาย LAN ถ้ามี · ใช้ terminal ของ desktop (ถ้ายังไม่ทำขั้น 9) หรือกด Ctrl+Alt+F2 แล้ว login aipc2030 (ถ้าทำขั้น 9 แล้ว)
```sh
# 1) ดูสถานะ RTC และแบต (ดูรุ่นแบตที่ขั้ว BAT ด้วยตา แล้วจดไว้)
ls /sys/class/rtc/rtc0/
for f in charging_voltage charging_voltage_min charging_voltage_max date time; do echo "$f $(cat /sys/class/rtc/rtc0/$f 2>&1)"; done
timedatectl
# 2) ตัดเน็ตไม่ให้ NTP แก้เวลา (ค่านี้ค้างข้ามการรีบูต)
nmcli radio wifi off
date '+%F %T'        # เทียบกับมือถือทันที จดส่วนต่างเป็น "ก่อนปิด"
sudo poweroff        # รอไฟเขียวดับ แล้วถอดปลั๊ก · จดเวลาจากมือถือ · รอ 30 นาที
# 3) เสียบปลั๊ก (ยังไม่ต่อเน็ต) · เข้า terminal ที่ตัวเครื่องแบบเดิม
date '+%F %T'        # กดพร้อมดูมือถือ จดส่วนต่างเป็น "หลังเปิด"
timedatectl | grep -E 'Local time|RTC time|synchronized'   # synchronized ต้องเป็น no
nmcli radio wifi on
# 4) บันทึกผล (พิมพ์ค่าที่จดไว้แทนคำในวงเล็บเหลี่ยม)
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-rtc-offline; mkdir -p $D
printf 'แบต: [รุ่นที่เห็น/ไม่มี]\ncharging_voltage: [ค่า]\nปิดเครื่อง: [เวลา] ถอดปลั๊ก [นาที] นาที\nส่วนต่างก่อนปิด: [วิ]\nส่วนต่างหลังเปิด: [วิ]\nsynchronized ตอนเปิด: no\n' > $D/README.md
nano $D/README.md    # แทนค่าในวงเล็บเหลี่ยม
git add $D && git commit -m "bench(pi5): นาฬิกาหลังปิดเครื่อง 30 นาทีแบบออฟไลน์"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) หลังเปิดเครื่อง `System clock synchronized: no` (ยืนยันว่าไม่มีเน็ตช่วย) และเวลาต่างจากมือถือ ≤ 60 วิ (= CLOCK_SLACK ของ reminders.py) · ถ้าช้าไปราว 30 นาที = แบตไม่เก็บเวลา → ไป section เปิดชาร์จแบต (เฉพาะแบตแบบชาร์จได้) หรือเขียนข้อจำกัดในเล่ม · ถ้า synchronized เป็น yes = ผลใช้ไม่ได้ ให้ทำใหม่
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-rtc-offline/README.md`

### V39 ใช้งานจริง 60 นาที: RAM ทั้งระบบ การเขียนการ์ด และ log
- **ตอบข้อ audit:** hw-os-2 (ส่วน ข ใช้พร้อมกันทุกส่วน), hw-os-7 และ data-9 (การเขียนการ์ด), data-5 (log ต่อคำตอบ)
- **ทำไมต้องทดสอบ:** RAM ทั้งระบบมีแค่ค่าประมาณใน BRIEF 6.1 และค่าบน Pi 4 (หน้าจอ ~172 MB · ใบหน้า VmHWM 217.3 MB) · การเขียนของแอปคำนวณแล้วว่าน้อย (reminders.py SEEN_EVERY 10 นาที · เทสต์บนวินโดวส์) แต่ยังไม่เคยวัดการเขียนของทั้งระบบบน Pi 5
- **ต้องอยู่หน้าเครื่อง:** ใช่ (มีคนใช้หน้าจอ V2 จริง · สั่งตัวบันทึกทาง SSH ได้) · **เวลา:** ~75 นาที · **ความเสี่ยง:** ต่ำ · ถ้า RAM ไม่พอ เคอร์เนลอาจปิด llama-server (service เปิดใหม่เอง) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (หยุดตัวบันทึกด้วย `systemctl --user stop aipc-ramlog`)
- **ก่อนเริ่ม:** ทำหลังขั้น 9 ของ `docs/runbooks/pi5-setup.md` (หน้า Login V2 + install-llm + รีบูต) และหลัง section journald · มีบัญชีทดสอบที่สมัครแล้ว · ไม่มีการวัดอื่นหรือดาวน์โหลด · คำถามแชท 20 ข้อ = 20 ข้อแรกของ `tests/data/llm_thai_questions.json` (ประกาศไว้ก่อน) · หลังขั้น 9 KillUserProcesses=yes = โปรเซสที่เปิดจาก SSH ตายเมื่อ SSH หลุด จึงเปิดตัวบันทึกผ่าน `systemd-run --user` (aipc2030 มี linger)
```sh
# ===== ทาง SSH (aipc2030) ก่อนเริ่มใช้งาน =====
findmnt -no OPTIONS /          # จดว่ามี noatime ไหม
cat > ~/ram.sh <<'EOF'
#!/bin/sh
# ทุก 5 วิ: MemAvailable SwapFree (kB) · zram ที่ใช้ (MB) · PSI memory · RSS ของ llama-server (kB)
printf 'time\tmem_avail_kb\tswap_free_kb\tzram_mb\tpsi_some10\tpsi_full10\tllama_rss_kb\n'
while :; do
  a=$(awk '/^MemAvailable/{print $2}' /proc/meminfo); s=$(awk '/^SwapFree/{print $2}' /proc/meminfo)
  z=$(awk '{printf "%d", $1/1048576}' /sys/block/zram0/mm_stat 2>/dev/null)
  ps=$(awk '/^some/{split($2,x,"="); print x[2]}' /proc/pressure/memory 2>/dev/null)
  pf=$(awk '/^full/{split($2,x,"="); print x[2]}' /proc/pressure/memory 2>/dev/null)
  p=$(pgrep -f 'aipc-llm/bin/llama-server' | head -1); r=-; [ -n "$p" ] && r=$(awk '/^VmRSS/{print $2}' /proc/$p/status)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date +%T)" "$a" "$s" "${z:--}" "${ps:--}" "${pf:--}" "$r"
  sleep 5
done
EOF
systemd-run --user --unit=aipc-ramlog sh -c 'sh "$HOME/ram.sh" > "$HOME/use-ram.tsv" 2>&1'
S0=$(awk '{print $7}' /sys/block/mmcblk0/stat); START=$(date '+%F %T'); echo "$S0|$START" > ~/use-start.txt
# ===== ที่หน้าจอ 60 นาที (จดเวลาแต่ละขั้น) =====
# ถามแชท 3 ข้อ → ลงทะเบียนใบหน้าในหน้าตั้งค่า → สั่งเปิดเว็บเบราว์เซอร์แล้วเปิด 3 แท็บ (เปิดค้างไว้จนวัดเสร็จ) →
# ถามแชทอีก 17 ข้อ (รวม 20) → เพิ่มนัด 5 รายการ → ที่เหลือเปิดหน้าจอทิ้งไว้ · จดถ้าหน้าจอค้างเกิน 5 วิ
# ===== ทาง SSH หลังครบ 60 นาที =====
S0=$(cut -d'|' -f1 ~/use-start.txt); START=$(cut -d'|' -f2 ~/use-start.txt)
S1=$(awk '{print $7}' /sys/block/mmcblk0/stat); systemctl --user stop aipc-ramlog
TU="ใส่ชื่อบัญชีทดสอบ"; id "$TU"      # แก้ให้ตรง · ต้องไม่ error
sudo -v                               # พิมพ์รหัสเอง ก่อนคำสั่งที่ใช้ sudo ด้านล่าง
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-real-use-60min; mkdir -p $D; cp ~/use-ram.tsv $D/
{ echo "เริ่ม $START · เขียนการ์ดทั้งระบบ $(( (S1 - S0) / 2048 )) MB"
  awk -F'\t' 'NR>1 && $2!=""{if(m==""||$2+0<m)m=$2+0} END{print "MemAvailable ต่ำสุด", m, "kB"}' $D/use-ram.tsv
  awk -F'\t' 'NR>1 && $5!="-"{if($5+0>p)p=$5+0} END{print "PSI some avg10 สูงสุด", p+0}' $D/use-ram.tsv
  for pat in 'aipc[.]ui' 'aipc-llm/bin/llama-server' 'systemd-journald' 'chromium'; do
    s=0; for p in $(pgrep -f "$pat"); do b=$(sudo awk '/^write_bytes/{print $2}' /proc/$p/io 2>/dev/null); s=$((s + ${b:-0})); done
    echo "$pat write_bytes $s"; done
  echo "log ของ aipc-llm: $(sudo journalctl _SYSTEMD_USER_UNIT=aipc-llm.service --since "$START" -o cat | wc -c) ไบต์ / 20 คำตอบ"
  journalctl --disk-usage
  sudo systemctl --user -M "$TU@" show aipc-llm -p NRestarts
  sudo journalctl -k --since "$START" --no-pager | grep -iE 'out of memory|oom-kill' || echo "ไม่มี OOM"
  /usr/sbin/zramctl
} | tee $D/summary.txt
nano $D/README.md     # โน้ตผู้ทดสอบ: เวลาแต่ละขั้น หน้าจอค้างไหม แชทตอบได้ไหมหลังเปิดเบราว์เซอร์
git add $D && git commit -m "bench(pi5): ใช้งานจริง 60 นาที RAM ทั้งระบบ การเขียนการ์ด log"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน · ตัวเลขเป็นค่าเสนอ แก้ได้ก่อนเริ่มเท่านั้น) MemAvailable ต่ำสุด ≥ 1,048,576 kB · ไม่มี OOM · NRestarts=0 · PSI some avg10 สูงสุด ≤ 10 (ถ้าคอลัมน์ PSI เป็น `-` ทั้งหมด ให้จดว่าวัดไม่ได้) · หน้าจอไม่ค้างเกิน 5 วิ และแชทยังตอบได้หลังเปิดเบราว์เซอร์ · เขียนการ์ดทั้งระบบ ≤ 100 MB ใน 60 นาที · write_bytes ของ aipc.ui ≤ 5 MB · root mount มี noatime · `journalctl --disk-usage` ≤ 200 MB · ขนาด log ต่อคำตอบจดไว้ใส่เล่ม (ไม่มีเกณฑ์) · หมายเหตุ: write_bytes นับเฉพาะโปรเซสที่ยังเปิดอยู่ และของ journald นับตั้งแต่บูต
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-real-use-60min/` (use-ram.tsv, summary.txt, README.md)

### V40 สั่งเครื่องจริงบนเดสก์ท็อป Pi 5 (แอป · เว็บ · เสียง) + สกิล 4 ที่ HEAD
- **ตอบข้อ audit:** skills-5, evidence-6, skills-8 (ยืนยันตัวรันคำสั่งจริง)
- **ทำไมต้องทดสอบ:** ยังไม่เคยรัน `gtk-launch` / `xdg-open` / `wpctl` จริงบน Pi (STATUS บรรทัด 55) · ชื่อไฟล์ `chromium.desktop` `lxterminal.desktop` `pcmanfm.desktop` ในตาราง APPS (`actions.py` บรรทัด 53–58) ยังไม่ได้ตรวจกับ trixie · ตัวเลขสกิล 4 ในเล่ม (93.0% / 1.1%) มาจาก 2026-09-24 และผลรันซ้ำยังไม่ได้บันทึก · บน PC ยืนยันแล้วว่าแอปที่มีไฟล์ .desktop ใหม่ถูกหาเจอ
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ต้องมีคนดูว่าหน้าต่างเปิดจริง · สั่งทาง SSH ได้ถ้ามีคนดูจอ) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · เปิดหน้าต่างแอป · ปรับเสียงชั่วคราว · **ย้อนกลับ:** คืนเสียงและสถานะปิดเสียงเดิม (อยู่ในคำสั่งท้าย) · `rm ~/.local/share/applications/aipc-test.desktop` · ปิดหน้าต่างที่เปิด
- **ก่อนเริ่ม:** aipc2030 login เดสก์ท็อปค้างที่จอ (สถานะตอนนี้) · ไม่มีการวัด LLM ค้าง · `git status --porcelain` ว่าง · ถ้าสั่งทาง SSH ต้อง export 3 บรรทัดแรก
```sh
# ถ้าสั่งทาง SSH: ชี้ไปที่เดสก์ท็อปที่ login ค้าง (ถ้าพิมพ์ใน terminal บนเดสก์ท็อปเอง ข้ามได้)
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=$(ls $XDG_RUNTIME_DIR | grep -m1 -E '^wayland-[0-9]+$'); echo "จอ: $WAYLAND_DISPLAY"
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/aipc; PY=./.venv/bin/python
D=docs/benchmarks/$(date +%F)-pi5-actions; mkdir -p $D
# 1) สกิล 4 ชุดสำรองที่ HEAD บนเครื่องจริง (มีไฟล์ .desktop จริง) · --save ห้ามมีโฟลเดอร์อยู่ก่อน
$PY -m aipc.skills.evaluate --commands tests/data/command_sentences_heldout.json --save $D/skill4-heldout | head -30
# 2) คำสั่งและไฟล์ .desktop ที่ตาราง APPS ใช้ มีจริงไหม
{ git rev-parse HEAD; command -v gtk-launch xdg-open wpctl; ls -l /usr/share/applications/chromium.desktop /usr/share/applications/lxterminal.desktop /usr/share/applications/pcmanfm.desktop; ls /usr/share/applications | grep -iE 'chrom|term|pcman|file'; } > $D/apps-check.txt 2>&1; cat $D/apps-check.txt
S0=$(wpctl get-volume @DEFAULT_AUDIO_SINK@); V0=$(echo "$S0" | awk '{print $2}'); echo "เสียงก่อนทดสอบ: $S0" | tee -a $D/apps-check.txt
# 3) สั่งจริงผ่าน Executor ตัวเดียวกับแอป (หน้าต่างจะเปิดบนจอ · ให้คนที่จอจดว่าขึ้นจริงไหม)
$PY - <<'EOF' | tee $D/executor.txt
import subprocess, time
from aipc.skills import actions as a
e = a.Executor(dry_run=False)
vol = lambda: subprocess.run(['wpctl', 'get-volume', a.SINK], capture_output=True, text=True).stdout.strip()
plans = [a.Plan('open_app', {'app': k}, k) for k in a.APPS] + [
    a.Plan('open_url', {'site': 'youtube'}, 'youtube'), a.Plan('change_volume', {'step': -10}, 'vol-10'),
    a.Plan('change_volume', {'step': 10}, 'vol+10'), a.Plan('mute', {}, 'mute'), a.Plan('unmute', {}, 'unmute')]
for p in plans:
    s = time.monotonic(); o = e.execute(p)
    print(p.action, p.params, 'ok' if o.ok else 'ล้ม', o.message, round(time.monotonic() - s, 2), 'วิ', '|', vol())
EOF
# 4) แอปที่เพิ่งเพิ่ม โดยไม่ต้องติดตั้งแพ็กเกจ: ไฟล์ .desktop ทดสอบของผู้ใช้
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/aipc-test.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=ทดสอบเอไอพีซี
Exec=lxterminal
EOF
$PY -c "from aipc.skills import actions as a, command; c = command.parse('เปิดทดสอบเอไอพีซี'); print(c and c.plan); print(c and a.Executor(dry_run=False).execute(c.plan))" | tee -a $D/apps-check.txt
rm ~/.local/share/applications/aipc-test.desktop                  # ย้อน
wpctl set-volume @DEFAULT_AUDIO_SINK@ $V0                            # คืนระดับเสียงเดิม
case "$S0" in *MUTED*) wpctl set-mute @DEFAULT_AUDIO_SINK@ 1 ;; *) wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 ;; esac
wpctl get-volume @DEFAULT_AUDIO_SINK@ | tee -a $D/apps-check.txt
${EDITOR:-nano} $D/apps-check.txt      # จดท้ายไฟล์: หน้าต่างที่เห็นบนจอ (browser/terminal/filemanager/youtube/ทดสอบ: ขึ้น/ไม่ขึ้น)
git add $D && git commit -m "bench(pi5): สั่งเครื่องจริงบนเดสก์ท็อป (แอป/เว็บ/เสียง) + สกิล 4 ที่ HEAD"
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) สกิล 4: ตีความถูก ≥ 53/57 และทำโดยไม่ได้ตั้งใจ 0/87 (ถ้าต่างจาก PC ให้จดประโยคที่ต่าง) · ไฟล์ .desktop ทั้ง 3 และคำสั่งทั้ง 3 มีอยู่ (ถ้าชื่อไม่ตรง ให้จดชื่อจริงเพื่อแก้ตาราง APPS บน PC) · open_app 3 ตัว + open_url ได้ `ok` และ ≤ 2.0 วิ ต่อครั้ง · คนที่จอจด "ขึ้น" 4/4 · หลัง vol-10 ค่าเสียงลด 0.10 และหลัง vol+10 กลับเท่าเดิม · หลัง mute มี `[MUTED]` และหลัง unmute หาย · แอปทดสอบได้ Plan ที่มี `desk:aipc-test.desktop` และคนที่จอเห็น lxterminal ขึ้น · บรรทัดสุดท้ายของ apps-check.txt เท่ากับ "เสียงก่อนทดสอบ"
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-actions/` (skill4-heldout/ · apps-check.txt · executor.txt) · commit อยู่ในคำสั่งแล้ว

### V41 ครบเส้นบนหน้าจอ V2: Claude สร้างสกิล → ติดตั้ง → AI ในเครื่องเลือกใช้
- **ตอบข้อ audit:** gaps-0, skills-9 (สกิลแบบขั้นตอนทำงานจริงบน Pi)
- **ทำไมต้องทดสอบ:** ความต้องการอาจารย์ข้อ 3 ยังไม่เคยทำครบบน Pi · แอปโหลดสกิลจาก `builtin` ในแพ็กเกจที่เดียว (`manifest.py` บรรทัด 154) และโหลดครั้งเดียวตอนเปิดหน้าจอ (`backend.py` บรรทัด 484) · รุ่นบน Pi สร้างจาก `git archive HEAD` (`update-app.sh` บรรทัด 91) สกิลที่ไม่ commit จึงหายเมื่ออัปเดต · เส้นทางเดียวที่อยู่รอด: ติดตั้งลง repo → commit → `update-app.sh --apply` → เข้าระบบใหม่
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ออกจากระบบ/เข้าใหม่ และพิมพ์ที่หน้าจอ V2) · **เวลา:** ~45 นาที · **ความเสี่ยง:** กลาง · `update-app.sh --apply` สลับรุ่นของหน้า Login (ลองเปิดก่อนสลับ) · ต้องเปิด SSH หรือ tty2 ค้างไว้สำรอง · **ย้อนกลับ:** `sudo ./scripts/pi/update-app.sh --rollback` แล้วออกจากระบบ-เข้าใหม่ · branch สาธิตเก็บไว้เป็นหลักฐาน (ลบได้ด้วย `git branch -D pi5-forge-demo` เมื่อไม่ใช้แล้ว)
- **ก่อนเริ่ม:** ขั้น 9 ของ `docs/runbooks/pi5-setup.md` เสร็จแล้ว (install-greeter · install-accounts · install-llm `--threads 3` · reboot เฉพาะตอนไม่มีคนใช้จอ) · ตอนนี้ยังไม่ได้ทำ (greetd inactive) · มีผู้ใช้ทดสอบ 1 บัญชี · section "forge บน Pi 5" ผ่านแล้ว · ไม่มีการวัดค้าง · ไม่มีคนอื่นใช้หน้าจอ · `git status --porcelain` ว่าง
```sh
# ทาง SSH (บัญชีผู้ดูแล)
cd ~/aipc; PY=./.venv/bin/python; export PATH="$HOME/.local/bin:$PATH"
BR0=$(git branch --show-current); echo "branch เดิม: $BR0"
git switch -c pi5-forge-demo                     # แยก branch ให้ย้อนง่าย
rm -rf /tmp/forge-demo
/usr/bin/time -f 'forge %e วิ' $PY -m aipc.skills.forge new "อยากได้สกิลเปิดยูทูบแล้วลดเสียงเหลือ 30" --out /tmp/forge-demo
ls /tmp/forge-demo; cat /tmp/forge-demo/*.md    # อ่านทุกบรรทัดก่อนติดตั้ง (H8)
SK=$(ls /tmp/forge-demo/*.md | head -1); echo "จะติดตั้ง: $SK"
$PY -m aipc.skills.forge install "$SK" --dest src/aipc/skills/builtin
$PY -m unittest discover -s tests -t . 2>&1 | tail -3
git add src/aipc/skills/builtin && git commit -m "skill(pi5): สกิลสาธิตจาก Claude บน Pi 5"
./scripts/pi/update-app.sh                        # ดูก่อนว่าจะทำอะไร (ไม่เปลี่ยนอะไร)
sudo ./scripts/pi/update-app.sh --apply           # พิมพ์รหัสเอง
# ที่หน้าจอ: ออกจากระบบ → เข้าใหม่ด้วยผู้ใช้ทดสอบ → รอ AI พร้อม
# พิมพ์ตัวอย่าง 4 ประโยคจากไฟล์สกิล และ 2 ประโยคที่ไม่ควรเรียก: "ยูทูบเบอร์คนไหนดังที่สุดในไทย" · "เสียงดังจากห้องข้าง ๆ ทำไงดี"
# จดต่อประโยค: ขึ้นการ์ดสกิลใหม่ไหม · กดยืนยันแล้ว YouTube เปิดไหม · ข้อความแรกรอกี่วินาที
# ตรวจเสียงทาง SSH ในนามผู้ใช้ทดสอบ (แก้ชื่อในบรรทัดแรก):
U=ชื่อผู้ใช้ทดสอบ
sudo -u "$U" XDG_RUNTIME_DIR=/run/user/$(id -u "$U") wpctl get-volume @DEFAULT_AUDIO_SINK@
# กลับ branch เดิมแล้วบันทึกผล
git switch "$BR0"
D=docs/benchmarks/$(date +%F)-skill-forge-e2e-pi5; mkdir -p $D; cp /tmp/forge-demo/* $D/
git rev-parse pi5-forge-demo > $D/demo-commit.txt
${EDITOR:-nano} $D/README.md                      # ตารางผล 6 ประโยค + เวลา forge + ผล wpctl
git add $D && git commit -m "bench(pi5): ครบเส้น Claude สร้างสกิล → AI ในเครื่องเลือกใช้บนหน้าจอ V2"
# ย้อนแอปกลับรุ่นก่อน (ถ้าไม่เก็บสกิลสาธิต) แล้วออกจากระบบ-เข้าใหม่ที่จอ
sudo ./scripts/pi/update-app.sh --rollback
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) forge ≤ 300 วิ และ log ขึ้น "พร้อมติดตั้ง" · install ขึ้น "ติดตั้งแล้ว" · เทสต์ขึ้น `OK` (fail = 0) · `update-app.sh --apply` ขึ้น "เสร็จ · ใช้รุ่น …" · ตัวอย่าง 4/4 ขึ้นการ์ดสกิลใหม่ก่อนทำ · ยืนยันแล้ว YouTube เปิดและ wpctl แสดง `Volume: 0.30` · ประโยคที่ไม่ควรเรียก 0/2 ขึ้นการ์ดสกิลใหม่ · หลัง `--rollback` เข้าระบบที่หน้า Login ได้
- **บันทึกผล:** `docs/benchmarks/<วันที่>-skill-forge-e2e-pi5/` (<id>.md · <id>.report.json · demo-commit.txt · README.md ตารางผล) บน branch เดิม · commit อยู่ในคำสั่งแล้ว

### V42 fps ขณะ AI ตอบ และหน้าจอทำให้ LLM ช้าลงเท่าไร
- **ตอบข้อ audit:** ui-1, ui-8 (ยืนยันว่าไม่มีแอนิเมชันวนกิน CPU), ui-0 (ไอคอนตอนเลื่อนบน GPU), ui-3 (การตัดบรรทัดไทยในแชทจริง)
- **ทำไมต้องทดสอบ:** BRIEF บรรทัด 374 ตั้งเกณฑ์ ≥ 50 fps ขณะ LLM ตอบ แต่ไม่มีไฟล์ผลวัดเลย · ตัวเลข "Pi 4 ช้าลงราวครึ่งหนึ่ง" ใน scope-cut ไม่มีไฟล์รองรับ ห้ามอ้างในเล่มจนกว่าจะได้ผลนี้ · ใช้ threads 3 เพราะวันนี้ threads 4 throttle ทุกรอบ
- **ต้องอยู่หน้าเครื่อง:** ใช่ (พิมพ์ เลื่อนแชท ที่จอ) · **เวลา:** ~50 นาที · **ความเสี่ยง:** ไม่มี (llama-server ชั่วคราวบน 127.0.0.1 แบบ `measure-llm.sh` · ประวัติแชทเขียนลงโฟลเดอร์ชั่วคราว ไม่ปนของจริง) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (`kill` llama-server เมื่อจบ)
- **ก่อนเริ่ม:** section "GPU" ผ่านแล้วเท่านั้น · ไม่มีการวัด/ดาวน์โหลดอื่นค้าง · อุณหภูมิ < 55°C · พิมพ์ทุกคำสั่งใน Terminal บนจอ Pi 5 · desktop Pi OS เปิดอยู่ทั้ง (ก) และ (ข) จึงเทียบกันได้ · พิมพ์คำถามภาษาอังกฤษ (desktop Pi OS อาจยังไม่มีแป้นไทย) · (ก) และ (ข) ส่ง system prompt + รายการสกิลชุดเดียวกับแอป จึงเทียบ tok/s ได้ตรง
```sh
cd ~/aipc
D=docs/benchmarks/$(date +%F)-ui-fps-llm; mkdir -p $D
B=~/llama.cpp/build/bin
M=models/typhoon2.5-qwen3-4b-q4_k_m.gguf
TPL=scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja
git log --oneline -1 > $D/commit.txt
./.venv/bin/python -m aipc.bench machine > $D/machine-before.json
wlr-randr | tee $D/display.txt      # ต้องเป็น 60 Hz · ถ้าต่ำกว่า 50 Hz เกณฑ์ 50 fps ใช้ไม่ได้ ให้หยุดแล้วแจ้ง
echo "desktop Pi OS เปิดค้าง · threads 3 · ctx 4096 · ไม่ใช่เซสชัน V2" > $D/notes.txt
# อุณหภูมิ/throttle/พัดลมทุก 5 วิ ตลอดการวัด
( while :; do echo "$(date +%T) $(vcgencmd measure_temp) $(vcgencmd get_throttled) fan=$(cat /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input)"; sleep 5; done ) > $D/thermal.log &
MON=$!
# llama-server ชั่วคราว แบบเดียวกับ measure-llm.sh แต่ threads 3
$B/llama-server -m $M --chat-template-file $TPL --host 127.0.0.1 --port 8080 -c 4096 -t 3 --no-webui > $D/llama-server.log 2>&1 &
LLM=$!
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8080/health >/dev/null && break; sleep 2; done
curl -sf http://127.0.0.1:8080/health && echo " พร้อม"    # ไม่ขึ้น = หยุด ดู $D/llama-server.log
Q='Write a 300-word essay in Thai about saving electricity at home'
# (ก) ไม่มีหน้าจอ: ส่ง 5 รอบด้วยโค้ดเดียวกับแอป (client.Stream · system + รายการสกิล · max_tokens 512)
cat > /tmp/llm-noui.py <<'EOF'
import sys
from aipc.chat import client
from aipc.skills import catalog, manifest
q = sys.argv[1]
tools = catalog.tools(manifest.load_builtin(), {"llm"})  # เท่ากับ SkillsController.tool_catalog() ตอนโมเดลพร้อม
target = client.Target(url="http://127.0.0.1:8080")
for i in range(1, 6):
    msgs, _ = client.fit_context(catalog.SYSTEM + catalog.TOOLS_HINT, [{"role": "user", "content": q}])
    r = client.Stream(target, msgs, tools=tools).run(lambda tok: None)
    t = r.timings
    print("%d\t%s\t%s\t%s" % (i, t.get("predicted_n", 0), t.get("predicted_per_second", 0), r.tool_call or r.reason or "-"), flush=True)
EOF
./.venv/bin/python /tmp/llm-noui.py "$Q" | tee $D/gen-noui.tsv     # รอบแรกอ่าน prompt ~60 วิ
cp /tmp/llm-noui.py $D/
N0=$(wc -l < $D/llama-server.log)
# (ข) เปิดหน้าจอพร้อม log เวลาวาดเฟรม · ทำตามขั้นข้างล่าง 5 รอบ แล้วปิดด้วย Ctrl+Alt+Q
T=$(mktemp -d)
XDG_DATA_HOME=$T AIPC_LLM_URL=http://127.0.0.1:8080 QT_MESSAGE_PATTERN='%{time boot} %{message}' \
  QT_LOGGING_RULES='qt.scenegraph.time.renderloop=true' \
  ./.venv/bin/python -m aipc.ui --screen shell --fullscreen 2> $D/ui-frames.log
#   ต่อรอบ: รอป้าย "โมเดล: พร้อม" → พิมพ์คำถามเดียวกับ $Q กด Enter
#   ระหว่าง AI ตอบ: หมุนลูกกลิ้งเมาส์ขึ้นลงบนแชทต่อเนื่อง ~5 วิ · พิมพ์ในช่องพิมพ์ (ไม่ส่ง) · ถ่ายรูปจอด้วยมือถือ 1 รูปตอนเลื่อน
#   ตอบจบ → กด "แชทใหม่" · ถ้า AI เลือกสกิลแทนการตอบ ทำเพิ่ม 1 รอบ (รอบนั้นถูกกรองออกเองเพราะ < 200 token)
rm -rf "$T"
kill $LLM $MON
./.venv/bin/python -m aipc.bench machine > $D/machine-after.json
# ความเร็วสร้างข้อความของ (ข) = บรรทัด eval time ใน log ที่เกิดหลัง (ก)
tail -n +$((N0+1)) $D/llama-server.log | grep ' eval time' | grep -v 'prompt eval' \
  | sed -E 's/.*\/ *([0-9]+) tokens .* ([0-9.]+) tokens per second.*/\1\t\2/' | awk '{print NR"\t"$0}' | tee $D/gen-ui.tsv
med() { sort -n | awk '{a[NR]=$1} END{m=(NR%2)?a[(NR+1)/2]:(a[NR/2]+a[NR/2+1])/2; print "median tok/s =", m, "n =", NR}'; }
awk -F'\t' '$2>=200 {print $3}' $D/gen-noui.tsv | med | sed 's/^/(ก) /' | tee $D/summary.txt
awk -F'\t' '$2>=200 {print $3}' $D/gen-ui.tsv | med | sed 's/^/(ข) /' | tee -a $D/summary.txt
# เวลาวาดเฟรม + fps ช่วงวาดต่อเนื่อง (ห่างกัน < 0.1 วิ = ตอนเลื่อน)
grep -i 'frame rendered' $D/ui-frames.log > $D/frames.txt
wc -l < $D/frames.txt | sed 's/^/frames = /' | tee -a $D/summary.txt     # 0 = ไม่เจอบรรทัดเฟรม ให้ส่ง ui-frames.log กลับมา
sed -E 's/.*rendered.* in ([0-9]+) ?ms.*/\1/' $D/frames.txt | sort -n | awk '{a[NR]=$1} END{i=int(NR*0.95+0.999); print "p95 =", a[i], "ms  max =", a[NR], "ms"}' | tee -a $D/summary.txt
awk '{t=$1+0; if (n++ && t-p < 0.1) {s+=t-p; g++} p=t} END{if (s>0) printf "fps ช่วงวาดต่อเนื่อง = %.1f (%d เฟรม)\n", g/s, g}' $D/frames.txt | tee -a $D/summary.txt
grep -cE '\.qml:[0-9]+' $D/ui-frames.log | sed 's/^/QML warnings = /' | tee -a $D/summary.txt
awk '{print $3}' $D/thermal.log | sort | uniq -c | tee -a $D/summary.txt   # ค่า throttled ที่เห็นระหว่างวัด
# จดลง notes.txt: ไอคอนหลุดกรอบตอนเลื่อนไหม · ข้อความไทยตัดกลางคำไหม (แนบรูปจากมือถือใน $D)
```
- **ผ่านเมื่อ:** (ข) median tok/s ≥ 90% ของ (ก) (นับเฉพาะรอบ ≥ 200 token · ต้องได้อย่างน้อย 3 รอบต่อฝั่ง) · fps ช่วงวาดต่อเนื่อง ≥ 50 · เวลาวาดเฟรม p95 ≤ 20 ms (รวมรอ vsync ~16.7 ms) · `QML warnings = 0` · ค่า throttled ทุกบรรทัดใน thermal.log หลักสุดท้ายเป็น 0 (`0xe0000` ผ่าน · `0xe0004`/`0xe0008` ไม่ผ่าน ต้องวัดใหม่)
- **บันทึกไว้ ไม่ใช่เกณฑ์:** ไอคอนหลุดกรอบไหม และไทยตัดกลางคำไหม (ดูจากรูป) · การตัดคำไทยวัดเป็นตัวเลขแล้วใน section "ตัดคำไทย" · การพิมพ์ไม่หน่วงใช้ p95/max ของเวลาวาดเฟรมแทน
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): fps ขณะ AI ตอบ + tok/s มี/ไม่มีหน้าจอ (threads 3)"` · เป็นค่าดิบพร้อม machine-before/after (ยังไม่นับระดับ 4 เต็มรูปจนกว่าจะมีเครื่องมือตาม code_fixes ui-1)

### V43 เวลาเปิดเครื่องถึงหน้า Login และ login ถึง Shell
- **ตอบข้อ audit:** gaps-5, ui-7 (ตัวชี้วัด "ยืนยันแล้ว → เห็น Shell" ในเซสชันจริง)
- **ทำไมต้องทดสอบ:** BRIEF บรรทัด 373 ตั้งเป้า ≤ 45 วิ แต่ยังไม่เคยวัดบนเครื่องไหน (ไม่มี systemd-analyze ใน docs/benchmarks และ scripts) · BRIEF บรรทัด 144 ให้วัดเวลา login → Shell ก่อนแล้วค่อยตั้งเป้า
- **ต้องอยู่หน้าเครื่อง:** ใช่ (กดปุ่มเปิดเครื่อง + นาฬิกาจับเวลา + login) · **เวลา:** ~35 นาที (รอบอุ่นเครื่อง 1 + วัด 5) · **ความเสี่ยง:** ต่ำ · ถ้าหน้า Login ไม่ขึ้น เข้าทาง SSH หรือ Ctrl+Alt+F2 · **ย้อนกลับ:** ขั้นนี้ไม่เปลี่ยนระบบ · ถ้าหน้า Login V2 พัง: `sudo ./scripts/pi/install-greeter.sh --rollback` แล้ว `sudo reboot` (กลับไป lightdm)
- **ก่อนเริ่ม:** ขั้น 9 ของ `docs/runbooks/pi5-setup.md` (install-greeter, install-accounts, install-llm, reboot) เสร็จ และมีบัญชีทดสอบแล้ว · ค่าบูตสุดท้ายที่จะใช้วันสอบตัดสินแล้ว (เช่น จะเติม `cgroup_enable=memory` ไหม) เพราะเปลี่ยนทีหลังต้องวัดใหม่ · ไม่มีการวัดอื่นค้าง · ไม่มีใครใช้จอ · microSD เดิม · อะแดปเตอร์ 27W
```sh
# ต่อรอบ (N = 0 อุ่นเครื่อง ไม่นับ · แล้ว 1..5):
#  1) ทาง SSH: sudo poweroff   แล้วรอไฟเขียวบนบอร์ดดับ
#  2) กดปุ่ม power บนบอร์ด พร้อมเริ่มนาฬิกาจับเวลา
#  3) หยุดนาฬิกาเมื่อช่องชื่อผู้ใช้ของหน้า Login V2 ขึ้น → จดเป็น boot_s
#  4) ยังไม่ login · SSH เข้าแล้วเก็บค่า (greeter ปิดตัวหลัง login จึงต้องเก็บตอนนี้):
cd ~/aipc
D=docs/benchmarks/$(date +%F)-boot-to-login; mkdir -p $D
N=1   # เปลี่ยนเป็นเลขรอบ 0..5 ทุกครั้ง
{ echo "== รอบ $N"; systemd-analyze; systemd-analyze critical-chain greetd.service --no-pager
  P=$(pgrep -f '^[^ ]*python[0-9.]* -m aipc[.]ui --fullscreen --greeter' | head -1)
  if [ -n "$P" ]; then
    awk -v hz=$(getconf CLK_TCK) '{printf "greeter (python) เริ่มที่ %.1f วิหลัง kernel เริ่ม\n", $22/hz}' /proc/$P/stat
  else echo "ไม่เจอโปรเซส greeter"; fi
  vcgencmd get_throttled; vcgencmd measure_temp; } > $D/round-$N.txt
systemd-analyze blame --no-pager | head -15 > $D/blame-$N.txt
cat $D/round-$N.txt
#  5) ที่จอ: login ด้วยบัญชีทดสอบ · เริ่มนาฬิกาตอนกดยืนยัน · หยุดเมื่อเห็นหน้า Shell → จดเป็น login_s
#  6) กด "ออก" ในหน้าจอ V2 แล้วเริ่มรอบถัดไป
# หลังครบ: กรอกค่าจากนาฬิกา (วินาที ทศนิยม 1 ตำแหน่ง)
printf 'round\tboot_s\tlogin_s\n0\t\t\n1\t\t\n2\t\t\n3\t\t\n4\t\t\n5\t\t\n' > $D/stopwatch.tsv
nano $D/stopwatch.tsv
awk -F'\t' 'NR>2 {print $2}' $D/stopwatch.tsv | sort -n | awk '{a[NR]=$1} END{print "median boot_s รอบ 1-5 =", a[3], "n =", NR}' | tee $D/summary.txt
awk -F'\t' 'NR>2 {print $3}' $D/stopwatch.tsv | sort -n | awk '{a[NR]=$1} END{print "median login_s รอบ 1-5 =", a[3], "n =", NR}' | tee -a $D/summary.txt
```
- **ผ่านเมื่อ:** median boot_s รอบ 1–5 ≤ 45 วิ (BRIEF 5.7) · round-1..5.txt ไม่มีบรรทัด "ไม่เจอโปรเซส greeter" (ขึ้นหน้า Login V2 ครบ 5/5) · login_s มีครบ 5 รอบ (รอบนี้ไม่มีเกณฑ์ ใช้ตั้งเป้าตาม BRIEF บรรทัด 144 · ประกาศไว้ก่อนวัด) · ทุกค่าวัดบน microSD เท่านั้น
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): เวลาเปิดเครื่องถึงหน้า Login 5 รอบ + login ถึง Shell"`

### V44 RAM ของหน้าจอและ labwc ในเซสชัน V2 จริง
- **ตอบข้อ audit:** ui-6, evidence-5, ui-9 (stderr ของหน้าจอไปที่ไหน)
- **ทำไมต้องทดสอบ:** RAM ของหน้าจอในเซสชันจริงมีแค่ Pi 4 วัดครั้งเดียว (~172 MB · การ์ด 0006 ได้ 199/385/~290 MB ก่อนแก้ malloc_trim) · ยังไม่เคยวัดหลังแก้ malloc_trim และไม่มีค่าบน Pi 5 · ต้องใช้เขียนงบ RAM ในบทที่ 4
- **ต้องอยู่หน้าเครื่อง:** ใช่ (login + แชท 10 รอบที่จอ · เก็บค่าทาง SSH) · **เวลา:** ~30 นาที · **ความเสี่ยง:** ไม่มี (อ่าน /proc อย่างเดียว) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ขั้น 9 ของ pi5-setup.md เสร็จ และหลัง section "เวลาเปิดเครื่อง" · login ด้วยบัญชีทดสอบที่จอแล้ว ป้าย "โมเดล: พร้อม" · ไม่มีการวัดอื่นค้าง · หมายเหตุ: `scripts/pi/sample-session.sh` ใช้ `pgrep -u "$USER"` จึงหาโปรเซสของบัญชีทดสอบไม่เจอเมื่อสั่งจาก aipc2030 ใช้คำสั่งข้างล่างแทน
```sh
cd ~/aipc
U=ชื่อบัญชีทดสอบ          # แก้เป็นชื่อบัญชีที่ login ที่จอ
D=docs/benchmarks/$(date +%F)-ui-session-ram; mkdir -p $D
git log --oneline -1 > $D/commit.txt
pids() { P=$(pgrep -u "$U" -f '^[^ ]*python[0-9.]* -m aipc[.]ui --session' | head -1); L=$(pgrep -u "$U" -x labwc | head -1); S=$(pgrep -u "$U" -x llama-server | head -1); }
rss() { awk '/^VmRSS/{print $2}' /proc/$1/status 2>/dev/null; }
pids; echo "ui=$P labwc=$L llama=$S" | tee $D/pids.txt      # ต้องได้เลขครบ 3 ตัว
sudo ls -l /proc/$P/fd/1 /proc/$P/fd/2 | tee $D/ui-stdio.txt   # ui-9: stderr ไป journal (socket) หรือ /dev/null
# RSS (kB) ของหน้าจอ V2 และ labwc ทุก 5 วิ (/proc/<pid>/status อ่านได้ทุกผู้ใช้)
( while :; do pids; printf '%s\t%s\t%s\t%s\n' "$(date +%T)" "${P:--}" "$(rss $P)" "$(rss $L)"; sleep 5; done ) > $D/rss.tsv &
MON=$!
mark() { pids; printf '%s\t%s\tui_kb=%s\tlabwc_kb=%s\n' "$(date +%T)" "$1" "$(rss $P)" "$(rss $L)" | tee -a $D/marks.tsv; }
sleep 60; mark idle          # ว่างบน Shell 60 วิ
echo "ที่จอ: แชท 10 รอบ (กด แชทใหม่ ได้) เสร็จแล้วกด Enter ที่นี่"; read -r _
mark after-chat
echo "ถ้าต่อกล้อง: ลงทะเบียน/สแกนหน้า 1 ครั้ง แล้วกด Enter · ไม่มีกล้องกด Enter เลย"; read -r _
mark camera-done
sleep 120; mark after-camera-120s
kill $MON
pids
for p in $P $L $S; do echo "== $p $(cat /proc/$p/comm)"; grep -E 'VmRSS|VmHWM' /proc/$p/status; done | tee $D/final.txt
free -m | tee -a $D/final.txt
```
- **ผ่านเมื่อ:** (ประกาศก่อนวัด · H9 · ค่าจาก marks.tsv) `idle` ui_kb ≤ 256000 · `after-chat` ui_kb ≤ 1.10 × `idle` · labwc_kb ≤ 153600 ทุกบรรทัด (Pi 4 ~95 MB) · ถ้าใช้กล้อง: `after-camera-120s` ui_kb ≤ `after-chat` + 30720 (ตรวจว่า malloc_trim ได้ผล) · เลข PID ของ ui ใน rss.tsv ไม่เปลี่ยนตลอดการวัด (หน้าจอไม่ล่ม)
- **บันทึกผล:** `git add $D && git commit -m "bench(pi5): RAM ของหน้าจอและ labwc ในเซสชัน V2"`

### V45 ติดตั้งหน้า Login V2 + T1–T3
- **ตอบข้อ audit:** security-2, llm-7
- **ทำไมต้องทดสอบ:** หน้า Login คือทางเข้าเครื่องทางเดียวในวันสอบ · ผลที่มีเป็นของ Pi 4 (`docs/benchmarks/2026-09-28-card0012-pi4/README.md` · ไม่ใช่ระดับ 4) · aipc-greeter (แป้นไทย) และ PIN เปลี่ยนหลังผล Pi 4 · Pi 5 ยังไม่ได้ติดตั้งเลย (greetd inactive)
- **ต้องอยู่หน้าเครื่อง:** ใช่ · **เวลา:** ~75 นาที (รีบูต 11 ครั้ง) · **ความเสี่ยง:** กลาง · เปลี่ยนหน้า login ของเครื่อง · หลังรีบูต KillUserProcesses=yes มีผล: งานที่สั่งผ่าน SSH ด้วย nohup/tmux จะถูกปิดเมื่อ SSH หลุด · **ย้อนกลับ:** จาก SSH หรือ Ctrl+Alt+F2: `cd ~/aipc; sudo ./scripts/pi/install-llm.sh --rollback; sudo ./scripts/pi/install-accounts.sh --rollback; sudo ./scripts/pi/install-greeter.sh --rollback` แล้วรีบูต (กลับเป็น lightdm · สคริปต์สำรอง config.toml เดิมไว้เอง)
- **ก่อนเริ่ม:** ทำหลัง section "ปิด Pi Connect, linger และ rpcbind" · **การวัด LLM ทุกตัวต้องจบแล้ว** (หลังขั้นนี้ งานยาวต้องสั่งด้วย `sudo systemd-run --uid=aipc2030 ...` ไม่ใช่ nohup) · git tree สะอาด · เน็ตต่ออยู่ (apt ติดตั้ง greetd/cage และ pip ของ update-app) · ลอง Ctrl+Alt+F2 แล้ว login ด้วย aipc2030 ที่หน้าจอตัวหนังสือได้ (Ctrl+Alt+F7 หรือ F1 กลับ)
```sh
cd ~/aipc
git status --porcelain | wc -l      # ต้องเป็น 0 · ไม่ใช่ = commit ผลวัดก่อน (install-greeter.sh หยุดเองถ้ามีไฟล์ค้าง)
ls -l models/typhoon2.5-qwen3-4b-q4_k_m.gguf scripts/pi/chat-templates/typhoon2.5-qwen3-4b-q4_k_m.jinja
# ดูก่อน (ยังไม่เปลี่ยนอะไร) · threads 3 เพราะ threads 4 throttle ทุกรอบ · เปลี่ยนโมเดลถ้าผลรอบ 2 เลือกตัวอื่น
./scripts/pi/install-greeter.sh --session v2
./scripts/pi/install-llm.sh --model models/typhoon2.5-qwen3-4b-q4_k_m.gguf --threads 3   # ต้องเห็นบรรทัด chat template: .../typhoon2.5-qwen3-4b-q4_k_m.jinja
# ทำจริง (ลำดับเดียวกับ runbook ขั้น 9)
sudo ./scripts/pi/install-greeter.sh --apply --session v2     # พิมพ์ YES
sudo ./scripts/pi/update-app.sh --apply
./scripts/pi/install-accounts.sh                              # ดูก่อน
sudo ./scripts/pi/install-accounts.sh --apply
sudo -l -U _greetd                                            # ต้องเห็นคำสั่งเดียว
sudo ./scripts/pi/install-llm.sh --apply --model models/typhoon2.5-qwen3-4b-q4_k_m.gguf --threads 3
grep -E '^(MODEL|THREADS|TEMPLATE)=' /etc/aipc/llm.conf         # TEMPLATE ต้องไม่ว่าง
grep -n '^vt' /etc/greetd/config.toml                         # คาดว่า vt = 7 · จดไว้
D=docs/benchmarks/$(date +%F)-pi5-login; mkdir -p "$D"
loginctl list-sessions; sudo reboot
```
T1–T3 (ที่หน้าจอ · จดผลลงกระดาษแล้วค่อยพิมพ์ลง README):
```sh
# T1: ทำ 10 รอบ · ทุกรอบ: ดูว่าขึ้นหน้า Login ของ V2 ไหม → จด → SSH เข้าแล้วรัน 2 บรรทัดนี้ (จดทีละรอบ ไม่พึ่ง journal เก่า)
cd ~/aipc; D=docs/benchmarks/<วันที่ตอนติดตั้ง>-pi5-login
printf '%s boot=%s greetd=%s err=%s\n' "$(date +%T)" "$(cat /proc/sys/kernel/random/boot_id | cut -c1-8)" "$(systemctl is-active greetd)" "$(journalctl -b -u greetd -p err -q --no-pager | wc -l)" | tee -a "$D/boots.txt"
sudo reboot                        # รอบที่ 10 ไม่ต้องรีบูต
# หลังครบ: ต้องมี 10 บรรทัด boot id ไม่ซ้ำกัน
wc -l < "$D/boots.txt"; cut -d' ' -f2 "$D/boots.txt" | sort -u | wc -l
# T2: ที่หน้า Login กด Ctrl+Alt+Q · แล้วกด Ctrl+Alt+F1 (กลับด้วย Ctrl+Alt+F<vt ที่จดไว้>)
# T3: login ด้วย aipc2030 รหัสผิด 3 ครั้ง แล้วรหัสถูก 1 ครั้ง → จับเวลาจนป้าย "โมเดล" เป็นสีเขียว
#     (ข้อความแรกหลังเปิด server อ่าน prompt ~60 วิ เป็นเรื่องปกติ ไม่เกี่ยวกับป้าย)
```
- **ผ่านเมื่อ:** T1 ขึ้นหน้า Login ของ V2 10/10 · boots.txt มี 10 บรรทัด boot id ไม่ซ้ำ 10 ตัว ทุกบรรทัด `greetd=active err=0` · T2 หน้า Login ไม่ปิด และ F1 ได้แค่หน้าถามชื่อ (ไม่ได้ shell ที่ login ค้างไว้) · T3 รหัสผิด 3/3 ขึ้นข้อความผิดรหัส และรหัสถูก 1/1 เข้าหน้าจอ V2 · `sudo -l -U _greetd` เห็นคำสั่งเดียว `/usr/local/sbin/aipc-accounts ""` · ป้ายโมเดลเป็นสีเขียวภายใน 60 วิหลัง login (จดวินาทีจริงลง README · ไม่ผ่านก็จดค่า ห้ามแก้เกณฑ์)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-login/` (boots.txt + README.md: วันที่, commit, ตาราง T1–T3, ผล sudo -l, วินาทีจนป้ายเขียว) · `git add "$D" && git commit -m "bench(pi5): หน้า Login V2 T1–T3"`

### V46 สมัคร 5 บัญชี ตัวช่วย root PIN และ home
- **ตอบข้อ audit:** security-2, security-5, security-7, security-8
- **ทำไมต้องทดสอบ:** เกณฑ์การ์ด 0012 ข้อ 8 (5 บัญชี · median ≤ 5 วิ) ยังไม่เคยทำบน Pi 5 · ผล Pi 4 ยังเป็นรุ่นรหัสสุ่ม · เวลา scrypt ยังเป็นค่าประมาณ 0.1–0.5 วิ (`helper.py:37`) · ชื่อที่ชนชื่อกลุ่ม (เช่น render) น่าจะได้ข้อความ "พื้นที่อาจเต็ม" ซึ่งผิดสาเหตุ (`helper.py:177–179`) · ยังไม่รู้ว่าบัญชีที่ผู้ดูแลสร้างทาง terminal ได้ home สิทธิ์อะไร
- **ต้องอยู่หน้าเครื่อง:** ใช่ · **เวลา:** ~50 นาที · **ความเสี่ยง:** ต่ำ · ใช้บัญชีทดสอบเท่านั้น · **ย้อนกลับ:** ถามเจ้าของก่อนทุกครั้ง แล้ว `for u in testa testb testc testd teste; do sudo userdel -r "$u"; sudo rm -f "/var/lib/aipc/recovery/$u.json"; done` (ลบก่อนวันสาธิต · ตอนนี้เก็บไว้ใช้ section ถัดไป)
- **ก่อนเริ่ม:** ทำหลัง section "ติดตั้งหน้า Login V2 + T1–T3" · ไม่มีงานหนักค้าง · อุณหภูมิ < 55°C (สำหรับวัด scrypt) · รหัสผ่านและ PIN ของบัญชีทดสอบให้ตั้งเองและจดแยก **ห้ามพิมพ์ลงไฟล์ผล**

ที่หน้า Login สมัคร 5 บัญชี `testa testb testc testd teste` · ชื่อที่แสดงพิมพ์เป็นภาษาไทย (ปุ่ม ~ สลับ) · จับเวลาด้วยมือถือตั้งแต่กด "สร้างบัญชี" ถึงเห็นหน้าพร้อมใช้ · แล้วลองสมัครชื่อ `render` 1 ครั้ง จดข้อความที่ขึ้น
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-signup; mkdir -p "$D"
sudo -l -U _greetd | tee "$D/sudo-greetd.txt"
# สิทธิ์และกลุ่มของ 5 บัญชี + ชื่อไทยใน passwd
for u in testa testb testc testd teste; do
  id "$u"; getent passwd "$u" | cut -d: -f5
  sudo stat -c '%a %U %n' "/home/$u" "/var/lib/aipc/recovery/$u.json"
done 2>&1 | tee "$D/accounts.txt"
# ชื่อ render: ต้องไม่มีบัญชีครึ่ง ๆ ค้าง
{ getent passwd render || echo "ไม่มีบัญชี render"; echo "pending: $(sudo ls -A /var/lib/aipc/pending | wc -l)"; } | tee "$D/render.txt"
# ผู้ดูแลเรียกตัวช่วยเอง ต้องถูกปฏิเสธ (คำขอไม่มีข้อมูลจริง)
printf '{"op":"create"}' | sudo /usr/local/sbin/aipc-accounts | tee "$D/admin-call.txt"
# journal ต้องไม่มี PIN/รหัสผ่าน · -o cat = เฉพาะข้อความ (ตัดเวลาและ PID ที่อาจบังเอิญตรงกับ PIN)
# พิมพ์เองแบบไม่แสดงบนจอ ไม่เก็บลงไฟล์
read -rs -p 'PIN ของ testa: ' P; echo; sudo journalctl -t aipc-accounts -o cat --since today | grep -c -F -- "$P"; unset P
read -rs -p 'รหัสผ่านของ testa: ' P; echo; sudo journalctl -t aipc-accounts -o cat --since today | grep -c -F -- "$P"; unset P
sudo journalctl -t aipc-accounts -o short-precise --since today | tee "$D/journal.txt"
# บัญชีที่อยู่ sudo ต้องไม่มีไฟล์ PIN (ไม่งั้น PIN 6 หลักเป็นทางเดาเพื่อได้ root)
for f in $(sudo ls /var/lib/aipc/recovery); do u=${f%.json}; id -nG "$u" | grep -qw sudo && echo "มี PIN แต่อยู่ sudo: $u"; done | tee "$D/sudo-with-pin.txt"
# เวลา scrypt ด้วยค่าจริงของตัวช่วย (ข้อความทดสอบ ไม่ใช่ PIN จริง)
vcgencmd measure_temp | tee "$D/scrypt.txt"
/opt/aipc-v2/.venv/bin/python -I -c "import hashlib,os,time; from aipc.accounts import helper; s=os.urandom(16); t=time.perf_counter(); [hashlib.scrypt(b'000000', salt=s, maxmem=64*1024*1024, **helper.SCRYPT) for _ in range(20)]; print('scrypt ต่อครั้ง', round((time.perf_counter()-t)/20, 3), 'วิ')" | tee -a "$D/scrypt.txt"
# home ของบัญชีที่ผู้ดูแลสร้างทาง terminal (ไม่ผ่าน chmod 0700 ของตัวช่วย) · สร้างแล้วลบทันที
{ grep -E '^\s*HOME_MODE' /etc/login.defs; grep -E '^\s*DIR_MODE' /etc/adduser.conf
  sudo useradd -m admtest1; stat -c '%a %n' /home/admtest1; sudo userdel -r admtest1
  sudo adduser --disabled-password --comment '' admtest2 >/dev/null; stat -c '%a %n' /home/admtest2; sudo userdel -r admtest2; } 2>&1 | tee "$D/home-mode.txt"
```
PIN (ที่หน้า Login · ใช้ testc): ลืมรหัสผ่าน → PIN ผิด 5 ครั้ง → ครั้งที่ 6 ใส่ PIN ถูก → จดข้อความ
```sh
r() { sudo python3 -c "import json; d=json.load(open('/var/lib/aipc/recovery/testc.json')); print('failed', d['failed'], 'wait_until', int(d['wait_until']))"; }
r | tee "$D/pin.txt"                   # หลังครั้งที่ 6
# รอ 70 วิ → PIN ถูกอีกครั้ง → ตั้งรหัสใหม่ → login ด้วยรหัสใหม่ได้ไหม
r | tee -a "$D/pin.txt"
# testa: login → แชท 1 ข้อ + ลงทะเบียนใบหน้า → ออก · แล้วหาไฟล์ที่ทิ้งไว้ในที่ใช้ร่วมกัน
sudo find /tmp /var/tmp /dev/shm -user testa 2>/dev/null | tee "$D/tmp-leftovers.txt"
sudo find /tmp /var/tmp /dev/shm -user testa -perm -o+r 2>/dev/null | wc -l | tee -a "$D/tmp-leftovers.txt"
sudo chown -R "$USER": "$D"
```
- **ผ่านเมื่อ:** สมัครแล้ว login ได้ 5/5 · ชื่อไทยใน passwd 5/5 · median เวลาสมัคร ≤ 5 วิ · ไม่มีกลุ่ม sudo 5/5 · home = 700 และไฟล์ PIN = 600 root 5/5 · sudo -l เห็น 1 คำสั่ง · admin-call.txt มี "เรียกได้จากหน้า Login เท่านั้น" · grep PIN = 0 และรหัสผ่าน = 0 · sudo-with-pin.txt ว่าง · scrypt ≤ 0.5 วิ · ครั้งที่ 6 ขึ้น "ลองใหม่ได้ในอีก 1 นาที" และ failed=5 · หลังรอ PIN ถูก → login ด้วยรหัสใหม่ได้ และ failed=0 · render: ไม่มีบัญชี render และ pending = 0 (ข้อความที่คาดไว้ก่อนรันคือ "พื้นที่อาจเต็ม" = ยืนยันว่าต้องแก้โค้ด) · tmp-leftovers ที่คนอื่นอ่านได้ = 0 · home-mode.txt: ถ้า useradd/adduser ไม่ได้ 700 ไม่นับว่าตก แต่ต้องเขียนเป็นขั้นในคู่มือ (`chmod 700`)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-signup/` (ไฟล์ .txt ทั้งหมด + README.md: เวลาสมัคร 5 ค่า, median, ข้อความของ render, อุณหภูมิ) · `git add "$D" && git commit -m "bench(pi5): สมัคร 5 บัญชี + PIN + scrypt"`
- **(ไม่บังคับ · การ์ดสำรองเท่านั้น)** ดึงปลั๊กทันทีหลังกด "สร้างบัญชี" 5 ครั้ง · หลังบูตทุกครั้ง: `sudo ls -A /var/lib/aipc/pending; getent passwd <ชื่อที่สมัครค้าง>` · ผ่านเมื่อ 5/5 ไม่มีบัญชีครึ่ง ๆ และสมัครชื่อเดิมใหม่ได้ · ทำรวมกับ T10

### V47 ออกจากระบบแล้ว AI ต้องหาย (T4)
- **ตอบข้อ audit:** hw-os-0, security-1, security-2
- **ทำไมต้องทดสอบ:** ผลที่มีเป็นของ Pi 4 ทดสอบแค่ `nohup sleep 4242` ทาง SSH (`docs/benchmarks/2026-09-28-card0013-pi4/README.md`) · ยังไม่เคยลองกับ llama-server ที่เป็น user service · `aipc-session` บรรทัด 25 ใช้ `exec labwc` ไม่ได้สั่งหยุด AI เอง พึ่งให้ user manager ปิด · ถ้า AI ค้าง RAM 2.5+ GB จะค้างไปถึงคนถัดไป
- **ต้องอยู่หน้าเครื่อง:** ใช่ · **เวลา:** ~30 นาที · **ความเสี่ยง:** ต่ำ · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (ตัวเฝ้าเป็น unit ชั่วคราว หยุดเองตาม RuntimeMaxSec)
- **ก่อนเริ่ม:** ทำหลัง section "ปิด Pi Connect, linger และ rpcbind" และ "สมัคร 5 บัญชี …" · รีบูตหลัง install-accounts แล้ว · ไม่มีการวัดอื่นค้าง

**ข้อควรรู้:** user manager ของคนหนึ่งอยู่ต่อตราบที่คนนั้นยังมีเซสชันเปิดอยู่ รวมถึง SSH · จึงทดสอบ 3 รอบด้วย testa (SSH ในชื่อ aipc2030 เฝ้าได้) และรอบที่ 4 ด้วย aipc2030 ต้อง **ออกจาก SSH ก่อน** ให้ตัวเฝ้าที่รันเป็น root จดแทน · สคริปต์และผลเก็บใน `$D` (home ของ aipc2030 · 0700) ไม่ใช้ /var/tmp เพราะบัญชีทดสอบเขียน /var/tmp ได้ แล้ว root จะรันไฟล์ของคนอื่น
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-logout; mkdir -p "$D"; A="$PWD/$D"
{ echo "linger: $(ls /var/lib/systemd/linger | wc -l)"; grep -rs KillUserProcesses /etc/systemd/logind.conf.d/; } | tee "$D/setup.txt"
# ตัวเฝ้า: ทุก 2 วิ จด เวลา · จำนวน llama-server · จำนวนโปรเซสของผู้ใช้ · MemAvailable (MB) · ผู้ใช้ที่ logind ยังเห็น
cat > "$D/logout-watch.sh" <<'EOF'
#!/bin/sh
U="$1"
while :; do
  printf '%s llama=%s procs=%s availMB=%s users=%s\n' "$(date +%T)" \
    "$(pgrep -c -x llama-server)" "$(pgrep -c -u "$U")" \
    "$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)" \
    "$(loginctl list-users --no-legend | awk '{print $2}' | tr '\n' ,)"
  sleep 2
done
EOF
# รันเป็น unit ของระบบ = ไม่ตายตอน SSH หลุด (KillUserProcesses=yes)
sudo systemd-run --unit=aipc-logout-watch -p RuntimeMaxSec=1800 -p StandardOutput=append:"$A/logout-testa.txt" /bin/sh "$A/logout-watch.sh" testa
# รอบ 1–3 (ที่หน้าจอ): testa login → รอป้ายโมเดลเขียว → ถาม AI 1 ข้อ รอจนตอบจบ → จดเวลาในนาฬิกา → กด "ออกจากระบบ" → จดเวลา → รอ 60 วิ
tail -45 "$D/logout-testa.txt"
ps -u testa --no-headers | wc -l          # T4 ต้องเป็น 0
sudo systemctl stop aipc-logout-watch; sudo systemctl reset-failed aipc-logout-watch 2>/dev/null
# รอบ 4: aipc2030 · เริ่มตัวเฝ้าแล้วออกจาก SSH ทันที
sudo systemd-run --unit=aipc-logout-watch2 -p RuntimeMaxSec=900 -p StandardOutput=append:"$A/logout-aipc2030.txt" /bin/sh "$A/logout-watch.sh" aipc2030
exit
# ที่หน้าจอ: aipc2030 login → ป้ายเขียว → ถาม AI 1 ข้อ → จดเวลา → ออก → รอ 60 วิ → ค่อย SSH กลับเข้ามา
cd ~/aipc; D=docs/benchmarks/<วันที่เดิม>-pi5-logout
sudo systemctl stop aipc-logout-watch2; sudo systemctl reset-failed aipc-logout-watch2 2>/dev/null
sudo chown -R "$USER": "$D"      # ดูบรรทัดก่อน SSH กลับเข้ามา
```
- **ผ่านเมื่อ:** ครบ 4/4 รอบ (testa 3 + aipc2030 1): ภายใน 20 วิหลังเวลาที่จดตอนกดออก `llama=0` และ `procs=0` และไม่มีชื่อผู้ใช้นั้นใน `users=` · หน้าจอกลับหน้า Login · availMB หลังออก 60 วิ ต่างจากค่าก่อน login ไม่เกิน 300 MB · `ps -u testa` = 0 · ถ้ารอบ aipc2030 ไม่ผ่านทั้งที่ linger = 0 → แก้ `aipc-session` (ดู code_fixes) แล้วทำ section นี้ซ้ำ
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-logout/` (setup.txt, logout-watch.sh, logout-testa.txt, logout-aipc2030.txt, README.md: เวลากดออกแต่ละรอบ + วินาทีจนถึง llama=0) · `git add "$D" && git commit -m "bench(pi5): ออกจากระบบแล้วไม่เหลือ llama-server (T4)"`

### V48 socket ของ AI: T7 กับ T12
- **ตอบข้อ audit:** llm-7, security-6
- **ทำไมต้องทดสอบ:** Pi 4 ผ่านแล้วกับโมเดล 0.5B และ llama.cpp 6c7a87f (socket 0700 · kill -9 กลับมาใน 6 วิ · `docs/benchmarks/2026-09-28-card0013-pi4/README.md`) = ไม่ใช่ระดับ 4 · T12 (บัญชีที่สองต่อ socket) ยังไม่เคยทำ · Pi 5 ใช้ build 86ea01d และโมเดล 4B ที่โหลดนานกว่า
- **ต้องอยู่หน้าเครื่อง:** ใช่ (testa ต้อง login ที่หน้าจอ) · **เวลา:** ~20 นาที · **ความเสี่ยง:** ต่ำ · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section "สมัคร 5 บัญชี …" · testa login ที่หน้าจอ ป้ายโมเดลเขียว และถามไปแล้ว 1 ข้อ · SSH ในชื่อ aipc2030
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-llm-socket; mkdir -p "$D"
A=$(id -u testa); S=/run/user/$A/aipc/llm.sock
{
  sudo ls -ld /run/user/$A /run/user/$A/aipc; sudo ls -l "$S"
  echo "พอร์ต TCP ของ llama-server: $(sudo ss -ltnpH | grep -c llama-server)"
  echo "unix socket llm.sock: $(sudo ss -lxpH | grep -c llm.sock)"
  sudo systemctl --user -M testa@.host show aipc-llm -p ActiveState -p NRestarts -p MemoryMax
  echo "== T12: testb ลองต่อ socket และเปิดของ testa"
  sudo -u testb curl -s -m 5 --unix-socket "$S" http://x/health; echo "curl exit=$?"
  sudo -u testb ls /run/user/$A; echo "ls run exit=$?"
  sudo -u testb ls /home/testa; echo "ls home exit=$?"
} 2>&1 | tee "$D/t12.txt"
# T7: ให้ testa ถามคำถามที่ตอบยาว (เช่น "เล่านิทานยาว ๆ") · ระหว่างข้อความกำลังขึ้น:
s=$(date +%s); sudo kill -9 $(pgrep -u testa -x llama-server)
# รอสูงสุด 180 วิ (health ตอบ 503 ระหว่างโหลดโมเดล = ยังไม่พร้อม)
for i in $(seq 180); do sudo -u testa curl -sf -m 2 --unix-socket "$S" http://x/health >/dev/null && break; sleep 1; done
echo "T7 กลับมาพร้อมใน $(( $(date +%s) - s )) วิ" | tee "$D/t7.txt"
sudo systemctl --user -M testa@.host show aipc-llm -p NRestarts -p ActiveState | tee -a "$D/t7.txt"
sudo chown -R "$USER": "$D"
```
- **ผ่านเมื่อ:** `/run/user/$A` และ `aipc` เป็น `drwx------` ของ testa · พอร์ต TCP ของ llama-server = 0 · llm.sock ≥ 1 · T12: curl ของ testb exit ≠ 0 และ ls ทั้งสองได้ Permission denied (exit ≠ 0) · T7: พร้อมอีกครั้ง ≤ 60 วิ · NRestarts เพิ่มจากค่าใน t12.txt 1 ครั้ง · ActiveState=active · หน้าจอของ testa ขึ้น "AI กำลังเริ่มใหม่" แล้วถามต่อได้และได้คำตอบ (จดใช่/ไม่ใช่) · MemoryMax แสดง 4294967296 เป็นแค่ค่าตั้ง ตอนนี้ไม่มีผลเพราะ kernel ปิด memory cgroup (อยู่ในหมวด OS/หน่วยความจำ ไม่ใช่ section นี้)
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-llm-socket/` (t12.txt, t7.txt, README.md) · `git add "$D" && git commit -m "bench(pi5): T7 และ T12 socket ของ llama-server"`

### V49 T6 นับการเชื่อมต่อขาออก 30 นาที
- **ตอบข้อ audit:** hw-os-5
- **ทำไมต้องทดสอบ:** ข้ออ้างที่ 1 ของเล่มคือไม่มีข้อมูลออกนอกเครื่อง · Pi Connect เคยต่อออกค้างไว้ (audit Pi 5 ระดับ 4) · ยังไม่เคยนับการเชื่อมต่อขาออกระหว่างใช้งานจริง · ยังไม่มีสคริปต์นับใน repo จึงเขียนเป็น shell ตรง ๆ
- **ต้องอยู่หน้าเครื่อง:** ใช่ (มีคนใช้ V2 30 นาที) · **เวลา:** ~40 นาที · **ความเสี่ยง:** ไม่มี · **ย้อนกลับ:** ไม่เปลี่ยนระบบ (unit ชั่วคราว หยุดเองใน 30 นาที)
- **ก่อนเริ่ม:** ทำหลัง section "ปิด Pi Connect, linger และ rpcbind" และ "ติดตั้งหน้า Login V2 + T1–T3" · เน็ตต่ออยู่ (hotspot) เพื่อดูว่ามีอะไรพยายามออกไหม · ไม่มีการดาวน์โหลดค้าง · ไม่มีการรัน forge/claude
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-t6-outbound; mkdir -p "$D"; A="$PWD/$D"
# เช็กรูปแบบคอลัมน์ก่อน: เมื่อระบุ state ss ไม่พิมพ์คอลัมน์ State → $4 = ฝั่งเครื่อง · $5 = ปลายทาง
sudo ss -tunpH state established | head -3
# ทุก 10 วิ จดการเชื่อมต่อ TCP/UDP ที่ต่ออยู่ · ไม่นับ loopback และ SSH ขาเข้า (ฝั่งเครื่องเป็นพอร์ต 22)
# สคริปต์อยู่ใน $D (home 0700) ไม่ใช่ /var/tmp เพราะ root จะรันไฟล์นี้
cat > "$D/t6.sh" <<'EOF'
#!/bin/sh
while :; do
  ss -tunpH state established | awk -v t="$(date +%T)" '$5 !~ /^(127\.|\[::1\]|\[::ffff:127\.)/ && $4 !~ /:22$/ {print t, $0}'
  sleep 10
done
EOF
sudo systemd-run --unit=aipc-t6 -p RuntimeMaxSec=1800 -p StandardOutput=append:"$A/t6-outbound.txt" /bin/sh "$A/t6.sh"
date +%T | tee "$D/start.txt"
# 30 นาทีที่หน้าจอ: แชทกับ AI หลายข้อ · ใช้สกิล (เช่น ตั้งนัด/เตือน) · สแกนใบหน้า · เปิดหน้าตั้งค่า · ออกแล้วเข้าใหม่ 1 ครั้ง
# หลังครบ 30 นาที (หยุดเองเพราะ RuntimeMaxSec · systemd จะแสดงเป็น failed/timeout = ปกติ):
systemctl is-active aipc-t6          # ต้องไม่ใช่ active
sudo systemctl reset-failed aipc-t6 2>/dev/null   # ไม่ให้นับเป็น unit ที่ล้มใน section อื่น
sudo chown -R "$USER": "$D"
wc -l < "$D/t6-outbound.txt"
grep -c -E 'llama-server|python|aipc|rpi-connect|wayvnc|claude' "$D/t6-outbound.txt"
grep -o 'users:(("[^"]*"' "$D/t6-outbound.txt" | sort | uniq -c | tee "$D/by-process.txt"
```
- **ผ่านเมื่อ:** start.txt มีเวลาเริ่ม และบรรทัดสุดท้ายของ `journalctl -u aipc-t6` บอกว่าหยุดหลัง ~1800 วิ · การเชื่อมต่อจากโปรแกรมของเราและ Pi Connect (`llama-server|python|aipc|rpi-connect|wayvnc|claude`) = 0 บรรทัด · โปรเซสอื่นใน by-process.txt (เช่น ตัวตั้งเวลา NTP) ต้องระบุชื่อและอธิบายได้ทุกตัวใน README · ข้อจำกัดที่ต้องเขียน: จดทุก 10 วิ การเชื่อมต่อที่สั้นกว่านั้นอาจหลุดการนับ
- **บันทึกผล:** `docs/benchmarks/<วันที่>-pi5-t6-outbound/` (t6.sh, start.txt, t6-outbound.txt, by-process.txt, README.md: ทำอะไรบ้างใน 30 นาที) · `git add "$D" && git commit -m "bench(pi5): T6 การเชื่อมต่อขาออก 30 นาที"`

### V50 Image การ์ด + การ์ดสำรองบูตได้ + ลายนิ้วมือตรงกัน
- **ตอบข้อ audit:** deploy-0, data-1, deploy-7
- **ทำไมต้องทดสอบ:** image + การ์ดสำรองเป็นทางกู้ทางเดียวในวันสอบที่ไม่ต้องใช้เน็ต (ติดตั้งใหม่ต้อง pip ออนไลน์ `install-greeter.sh:142` + build llama.cpp + โหลดโมเดล) · ยังไม่มีขั้นตอนและไม่เคยทำ · T10/T13/ไฟดับหลังสลับรุ่น ต้องใช้การ์ดสำรองนี้
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ถอด/ใส่การ์ด · PC ที่มีเครื่องอ่านการ์ด + Win32DiskImager) · **เวลา:** ~120 นาที · **ความเสี่ยง:** กด Write ผิดการ์ด = การ์ดหลักหาย → ติดป้าย "หลัก"/"สำรอง" ก่อน · การ์ดหลักกด Read เท่านั้น · Windows ขอ format ให้กด Cancel ทุกครั้ง · ไฟล์ .img มีข้อมูลบัญชีและคีย์ SSH ห้ามเข้า git ห้ามขึ้น cloud · **ย้อนกลับ:** ไม่เปลี่ยนการ์ดหลัก (ใส่การ์ดหลักคืนก็กลับสภาพเดิม)
- **ก่อนเริ่ม:** ขั้น 9 ครบ · ทำ section "ขั้น 9 + อัปเดตครั้งแรก" และ "T14" แล้ว · วัดทุกอย่างเสร็จและ commit แล้ว · D: ว่าง > 64 GB · ไม่มีใครใช้หน้าจอ
```sh
# 1) บน Pi 5 การ์ดหลัก (SSH) · สคริปต์ลายนิ้วมืออยู่ใน home (นอก repo · อ่านอย่างเดียว)
loginctl list-sessions                              # ต้องเหลือแค่ SSH และหน้า Login
cd ~/aipc && git status --porcelain | wc -l         # ต้องได้ 0
cat > ~/fp.sh <<'EOF'
cat /opt/aipc-v2/.installed-commit; readlink -f /opt/aipc-v2
git -C ~/aipc rev-parse HEAD; git -C ~/llama.cpp rev-parse --short HEAD
sha256sum /opt/aipc-models/*
LD_LIBRARY_PATH=/opt/aipc-llm/lib /opt/aipc-llm/bin/llama-server --version 2>&1 | head -2
cat /etc/aipc/llm.conf
sha256sum /opt/aipc-v2/.venv/lib/python3*/site-packages/aipc/skills/builtin/* 2>&1 | sha256sum
/opt/aipc-v2/.venv/bin/pip freeze | sha256sum
EOF
sh ~/fp.sh > ~/fingerprint-main.txt 2>&1; cat ~/fingerprint-main.txt
./.venv/bin/python -m aipc.doctor > ~/doctor-main.txt 2>&1; grep -E 'ไม่ผ่าน' ~/doctor-main.txt
sudo poweroff                                       # รอไฟเขียวหยุดกะพริบ แล้วถอดการ์ดหลัก

# 2) บน PC (PowerShell) · ใส่การ์ดหลัก · Windows ถาม format → Cancel
#   Get-PSDrive D                                     # Free ต้อง > 64 GB
#   Get-Disk | Format-Table Number, FriendlyName, Size   # จดขนาดการ์ดหลัก (ไบต์)
#   Win32DiskImager: Image File = D:\aipc-images\aipc-pi5-<วันที่>.img · Device = การ์ดหลัก · กด Read (ห้าม Write) · จดเวลา
#   certutil -hashfile D:\aipc-images\aipc-pi5-<วันที่>.img SHA256
#   ถอดการ์ดหลัก เก็บไว้ · ใส่การ์ดสำรอง
#   Get-Disk | Format-Table Number, FriendlyName, Size   # ขนาดการ์ดสำรองต้อง ≥ การ์ดหลัก (ไบต์)
#   Win32DiskImager: .img เดิม · Device = การ์ดสำรอง · Write · เสร็จแล้วกด Verify Only · จดเวลา

# 3) ใส่การ์ดสำรองใน Pi 5 · บูต · ดูที่จอว่าขึ้นหน้า Login ของ V2 · แล้วทาง SSH:
sh ~/fp.sh > ~/fingerprint-spare.txt 2>&1
diff ~/fingerprint-main.txt ~/fingerprint-spare.txt && echo 'ลายนิ้วมือตรงกัน'
vcgencmd get_throttled
cd ~/aipc && ./.venv/bin/python -m aipc.doctor > ~/doctor-spare.txt 2>&1   # ไม่ใส่ --save
diff <(grep 'ไม่ผ่าน' ~/doctor-main.txt) <(grep 'ไม่ผ่าน' ~/doctor-spare.txt) && echo 'doctor ไม่มีข้อไม่ผ่านใหม่'
#   ที่จอ: เข้าบัญชีทดสอบ · นัดและแชทเดิมอยู่ครบ · ถาม AI ได้คำตอบ 1 ครั้ง · ออกจากระบบ
sudo reboot                                         # ทำให้ครบ 3 ครั้ง (ตอนไม่มีคนใช้จอ)
#   บน PC: $PI = "aipc2030@ใส่ไอพี" ; scp "${PI}:fingerprint-spare.txt" "${PI}:doctor-spare.txt" D:\aipc-images\
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ขนาดการ์ดสำรอง ≥ การ์ดหลัก (เล็กกว่า = ไม่ผ่าน · ห้ามกด continue ตอน Win32DiskImager เตือน) · Verify Only ผ่าน · การ์ดสำรองบูตขึ้นหน้า Login ของ V2 3/3 · ขึ้น "ลายนิ้วมือตรงกัน" · เข้าบัญชีทดสอบได้ จำนวนนัด/แชทเท่ากับก่อนทำ image · AI ตอบ ≥ 1 ครั้ง · ขึ้น "doctor ไม่มีข้อไม่ผ่านใหม่" · get_throttled ไม่มีบิตไฟตก (0x1 และ 0x10000 เป็น 0) · จดเวลาอ่าน/เขียน/บูต
- **บันทึกผล:** ใส่การ์ดหลักคืน บูต · บน PC `scp D:\aipc-images\fingerprint-spare.txt D:\aipc-images\doctor-spare.txt "${PI}:"` · บน Pi: `D=docs/benchmarks/$(date +%F)-pi5-image && mkdir -p $D && cp ~/fingerprint-main.txt ~/fingerprint-spare.txt $D/` + `$D/README.md` (sha256 ของ .img, ขนาดการ์ดทั้งสองใบ, เวลา, ผลบูต 3 ครั้ง) → `git add docs/benchmarks && git commit -m "bench(pi5): image การ์ด + การ์ดสำรองบูตได้ 3/3 ลายนิ้วมือตรง"` · หลังทำ T10/T13/ไฟดับหลังสลับรุ่นบนการ์ดสำรอง ต้องเขียน image ลงการ์ดสำรองใหม่และตรวจลายนิ้วมืออีกครั้ง · อัปเดตรุ่นสุดท้ายก่อนสอบเมื่อไร ให้ทำ image ใหม่ทุกครั้ง

### V51 อัปเดตตอนไม่มีเน็ตจาก wheel ที่เก็บไว้
- **ตอบข้อ audit:** deploy-8
- **ทำไมต้องทดสอบ:** `update-app.sh:96-101` บอกว่าออฟไลน์ใช้ wheel ใน `/opt/aipc-releases/wheels` ได้ · Pi 4 ทดสอบแค่เน็ตหลุดระหว่างดาวน์โหลด · ยังไม่เคยลองตอนไม่มีเน็ตเลย · สำคัญน้อยกว่าข้ออื่น เพราะวันสอบไม่ควรอัปเดต
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ปิดเน็ตแล้ว SSH หลุด · ใช้ Ctrl+Alt+F2) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · เน็ตไม่กลับ → `sudo nmcli networking on` ที่ tty2 · **ย้อนกลับ:** `sudo nmcli networking on` · `sudo ./scripts/pi/update-app.sh --rollback` · `git switch master && git branch -D offline-test`
- **ก่อนเริ่ม:** ทำ section "ขั้น 9 + อัปเดตครั้งแรก" แล้ว (มี wheel เก็บไว้) · ไม่มีการวัดค้าง · ไม่มีคนใช้หน้าจอ V2
```sh
# ที่ตัวเครื่อง: Ctrl+Alt+F2 แล้วเข้าด้วย aipc2030
cd ~/aipc && git status --porcelain | wc -l          # ต้องได้ 0
ls /opt/aipc-releases/wheels | wc -l                # ต้อง > 0
nmcli -t -f RUNNING general                         # ต้องได้ running
B=$(readlink -f /opt/aipc-v2)
git switch -c offline-test && git commit --allow-empty -qm 'test: อัปเดตออฟไลน์ (ห้าม merge)'
NEW=$(git rev-parse --short=8 HEAD)
sudo -v
sudo nmcli networking off
ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 || echo 'ออฟไลน์แล้ว'
time sudo ./scripts/pi/update-app.sh --apply 2>&1 | tee /tmp/offline-apply.log
[ "$(readlink -f /opt/aipc-v2)" = "/opt/aipc-releases/$NEW" ] && echo 'ใช้รุ่นใหม่แล้ว'
sudo nmcli networking on
# ย้อน
sudo ./scripts/pi/update-app.sh --rollback
[ "$(readlink -f /opt/aipc-v2)" = "$B" ] && echo 'ย้อนกลับแล้ว'
git switch master && git branch -D offline-test
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ขึ้น "ออฟไลน์แล้ว" · log มี "ดาวน์โหลดไม่ได้ (ออฟไลน์?)" และจบด้วย "เสร็จ · ใช้รุ่น …" · ขึ้น "ใช้รุ่นใหม่แล้ว" · ใช้เวลา ≤ 10 นาที (real · รวมเวลาที่ pip ลองซ้ำ) · ขึ้น "ย้อนกลับแล้ว" · หมายเหตุ: หลังย้อน previous จะเป็นรุ่นทดสอบ (โค้ดเหมือน master) ไม่เป็นไร
- **บันทึกผล:** SSH กลับมาแล้ว: `D=docs/benchmarks/$(date +%F)-pi5-offline-update && mkdir -p $D && cp /tmp/offline-apply.log $D/` + `$D/README.md` (เวลา) → `git add docs/benchmarks && git commit -m "bench(pi5): อัปเดตแอปตอนไม่มีเน็ต"`

### V52 T10 ดึงปลั๊กระหว่างบันทึกข้อมูล
- **ตอบข้อ audit:** data-0, evidence-7, data-4
- **ทำไมต้องทดสอบ:** ข้ออ้าง "ไฟดับไม่เสียข้อมูล" มีแค่เทสต์ mock บนวินโดวส์ (ระดับ 3) และบนวินโดวส์ `fsync_dir` ถูกข้าม (`src/aipc/fsutil.py:16`) · ext4 + ตัวควบคุมของ microSD ทดสอบได้บนเครื่องจริงเท่านั้น · ยังไม่มีผล T10 บนเครื่องไหนเลย
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ดึงปลั๊ก) · **เวลา:** ~90 นาที · **ความเสี่ยง:** ระบบไฟล์ของการ์ดอาจเสีย → ใช้การ์ดสำรองเท่านั้น เก็บการ์ดหลักไว้นอกเครื่อง · **ย้อนกลับ:** เขียน image ลงการ์ดสำรองใหม่ (section Image) · ไฟล์ทดสอบอยู่ใน `~/t10*` บนการ์ดสำรองเท่านั้น
- **ก่อนเริ่ม:** ทำ section Image แล้ว · ในเครื่องมีแค่การ์ดสำรอง · ไม่มีงานอื่นค้าง · โน้ตบุ๊กต่อ SSH ผ่าน hotspot วางข้างเครื่อง (ใช้ Git Bash บนโน้ตบุ๊ก เพราะไฟล์ออกมาเป็น UTF-8 และไม่มีปัญหาเครื่องหมายคำพูดของ PowerShell) · ถ้าแก้โค้ด data-4 แล้ว ทำ section นี้ซ้ำอีกชุด
```sh
# 0) บน Pi (การ์ดสำรอง · SSH) สร้างสคริปต์ใน home (นอก repo)
cat > ~/t10-writer.py <<'EOF'
from datetime import datetime, timedelta
from aipc.skills import reminders as r
from aipc.chat import store as s
st, cs, c, i = r.ReminderStore(), s.ChatStore(), s.new_conversation(), 0
while True:
    i += 1
    st.add(r.Reminder("t10-%d" % i, datetime.now().astimezone() + timedelta(days=1)))
    c["messages"].append({"role": "user", "content": "t %d" % i})
    cs.save(c)
    print(i, flush=True)   # พิมพ์หลัง fsync แล้ว = เลขที่เห็นต้องไม่หาย
EOF
cat > ~/t10-check.py <<'EOF'
import os, pathlib
from aipc.skills import reminders as r
from aipc.chat import store as s
st, cs = r.ReminderStore(), s.ChatStore()
convs = cs.list()
msgs = [len(cs.load(x["id"])["messages"]) for x in convs]
last = max((int(x.what.split("-")[1]) for x in st.items), default=0)
base = pathlib.Path(os.environ["XDG_DATA_HOME"]) / "aipc"
tmp = [p.name for p in base.rglob("*.tmp")]
print(f"broken={st.broken} bak={st.recovered_from_backup} n={len(st.items)} last={last} chats={len(convs)} msgs={msgs} tmp={tmp}")
EOF
printf '%s\n' 'rm -rf ~/t10 && cd ~/aipc && XDG_DATA_HOME=$HOME/t10 exec ./.venv/bin/python -u ~/t10-writer.py' > ~/t10-run.sh
cat > ~/t10-after.sh <<'EOF'
cd ~/aipc && XDG_DATA_HOME=$HOME/t10 ./.venv/bin/python ~/t10-check.py
journalctl -b --no-pager | grep -iE 'EXT4-fs|fsck|mmc0' | tail -20
vcgencmd get_throttled
EOF

# 1) แต่ละรอบ บน โน้ตบุ๊ก (Git Bash) · N=1..10
PI=aipc2030@ใส่ไอพีของ Pi
N=1
ssh -o ServerAliveInterval=2 -o ServerAliveCountMax=3 "$PI" 'sh ~/t10-run.sh' | tee "t10-round-$N.txt"
#   ปล่อย 20–60 วิ (สลับเวลาแต่ละรอบ) แล้วดึงปลั๊ก Pi · ssh หลุดเองใน ~6 วิ · เสียบคืน รอบูต ~1 นาที
{ echo "round $N seen $(tail -1 "t10-round-$N.txt")"; ssh "$PI" 'sh ~/t10-after.sh'; } | tee -a t10-check.txt

# 2) รอบหน้าจอจริง 3 รอบ (ที่จอ · บัญชีทดสอบ): เพิ่มนัดจนขึ้นการ์ด "บันทึกแล้ว: …" / ส่งแชทให้ AI ตอบจนจบ / เปลี่ยนธีม → ดึงปลั๊กทันที
#   หลังบูต ดูว่าขึ้นหน้า Login · แล้วทาง SSH บน Pi:
U=ชื่อบัญชีทดสอบ                                    # แก้เป็นชื่อจริงก่อนรัน
sudo find /home/$U/.local/share/aipc /home/$U/.config/aipc -name '*.json' -exec python3 -c 'import json,sys; [json.load(open(p,encoding="utf-8")) for p in sys.argv[1:]]; print("ok", len(sys.argv)-1)' {} +
sudo find /home/$U/.local/share/aipc /home/$U/.config/aipc -name '*.tmp' | wc -l
sudo cat /home/$U/.config/aipc/ui.json; echo
#   เข้าบัญชีที่จอ: นัดที่ขึ้น "บันทึกแล้ว" ต้องอยู่ · คำตอบ AI ที่ตอบจบแล้วต้องอยู่ในประวัติ
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) รอบสคริปต์: บูตขึ้น 10/10 · `broken=False` 10/10 · `bak=False` 10/10 · `chats=1` 10/10 · `last` ≥ เลข seen และ `msgs[0]` ≥ เลข seen ทุกรอบ · ไม่มีบรรทัด `EXT4-fs error` (บรรทัด recovery/fsck ให้จดไว้ ไม่นับตก) · ไฟล์ .tmp ค้างได้ แต่จดไว้ · รอบหน้าจอ: ขึ้นหน้า Login 3/3 · พิมพ์ `ok N` ทุกรอบ · นัดที่ขึ้น "บันทึกแล้ว" อยู่ 3/3 · คำตอบ AI ที่ตอบจบแล้วอยู่ 3/3 (คำถามที่ยังตอบไม่จบหายได้ตามที่ออกแบบ) · ธีม: จดตามจริงอย่างเดียว (`ui/settings.py` ยังไม่ fsync โฟลเดอร์ จึงอาจย้อนเป็นค่าเดิมได้จนกว่าแก้ data-4)
- **บันทึกผล:** ใส่การ์ดหลักคืนแล้วบูต · บน Pi: `mkdir -p ~/aipc/docs/benchmarks/$(date +%F)-pi5-t10` · บนโน้ตบุ๊ก: `scp t10-round-*.txt t10-check.txt "$PI:aipc/docs/benchmarks/<วันที่>-pi5-t10/"` · บน Pi เขียน `README.md` (ตาราง 10+3 รอบ: seen, last, msgs, broken, bak, บรรทัด EXT4/fsck) → `git add docs/benchmarks && git commit -m "bench(pi5): T10 ดึงปลั๊ก 10+3 รอบบนการ์ดสำรอง"` · เสร็จแล้วเขียน image ลงการ์ดสำรองใหม่

### V53 ดึงปลั๊กทันทีหลังสลับรุ่นแอป
- **ตอบข้อ audit:** data-2
- **ทำไมต้องทดสอบ:** `update-app.sh` ไม่มีคำสั่ง `sync` เลย (บรรทัด 139-143: mv → switch_to → printf > previous) · ext4 อาจยังไม่เขียนไฟล์รุ่นใหม่ลงการ์ดตอน symlink เปลี่ยนแล้ว · T14 ไม่ครอบคลุมไฟดับ
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ดึงปลั๊ก + ดูหน้า Login ที่จอ) · **เวลา:** ~90 นาที (3 รอบก่อนแก้ + 3 รอบหลังแก้ · apply รอบละ ~5–10 นาที + บูต) · **ความเสี่ยง:** หน้า Login อาจหาย / ระบบไฟล์เสีย → การ์ดสำรองเท่านั้น · **ย้อนกลับ:** หน้า Login ไม่ขึ้น → SSH หรือ Ctrl+Alt+F2 แล้ว `cd ~/aipc && sudo ./scripts/pi/update-app.sh --rollback` · จบแล้วเขียน image ลงการ์ดสำรองใหม่
- **ก่อนเริ่ม:** ทำ section Image แล้ว · ในเครื่องมีแค่การ์ดสำรอง · มี `/opt/aipc-releases/previous` · มีเน็ต (apply โหลด wheel ได้) · ชุด ข. ทำหลังแก้โค้ด data-2 และเอาขึ้นการ์ดสำรองแล้ว
```sh
# ต่อรอบ (SSH จากโน้ตบุ๊กข้างเครื่อง)
cd ~/aipc && git status --porcelain | wc -l          # ต้องได้ 0
sudo -v
sudo ./scripts/pi/update-app.sh --rollback && sudo ./scripts/pi/update-app.sh --apply
# เห็นบรรทัด "+ สลับ /opt/aipc-v2 → ..." แล้วดึงปลั๊กภายใน 5 วิ · เสียบคืน · ดูที่จอว่าขึ้นหน้า Login ของ V2
# หลังบูต (SSH):
R=$(readlink -f /opt/aipc-v2); echo "$R"; cat /opt/aipc-releases/previous
# เทียบไฟล์ในรุ่นกับ git (ไม่มีบรรทัดออก = ครบ · ถ้า R เป็น legacy-* ให้ข้ามบรรทัดนี้)
git -C ~/aipc archive "$(basename "$R")" | sudo tar -d -f - -C "$R" 2>&1 | grep -v -E 'Mode differs|Mod time differs|Uid differs|Gid differs' | head
sudo find "$R/.venv" -type f -size 0 -name '*.so*' | head                  # ต้องไม่มี
( cd / && sudo -u _greetd "$R/.venv/bin/python" -I -c "import PySide6.QtQml, cv2, numpy, aipc.ui.app; print('ok')" )
systemctl is-active greetd; pgrep -u _greetd -af aipc.ui | head -2
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ชุด ข. (หลังแก้): ขึ้นหน้า Login ของ V2 3/3 · tar -d ไม่มีบรรทัดออก 3/3 · ไม่มีไฟล์ .so ขนาด 0 · import พิมพ์ `ok` 3/3 · previous ไม่ว่าง 3/3 · greetd active 3/3 · ชุด ก. (สคริปต์ตอนนี้): บันทึกผลตามจริงอย่างเดียว ผ่าน 3/3 ก็ยังไม่พิสูจน์ว่าปลอดภัย และไม่ใช่เหตุผลให้ไม่แก้
- **บันทึกผล:** จดผลแต่ละรอบลงไฟล์บนโน้ตบุ๊ก · ใส่การ์ดหลักคืน แล้วบน Pi: `D=docs/benchmarks/$(date +%F)-pi5-update-powerloss && mkdir -p $D` เขียน `$D/README.md` (รอบ, commit ของสคริปต์, ผลแต่ละข้อ) → `git add docs/benchmarks && git commit -m "bench(pi5): ดึงปลั๊กหลังสลับรุ่นแอป 3+3 รอบ"`

### V54 T13 ดิสก์เต็ม
- **ตอบข้อ audit:** data-3
- **ทำไมต้องทดสอบ:** โค้ดรับมือดิสก์เต็มมีแค่เทสต์ mock ENOSPC (`tests/test_skill_reminders.py`) · ทางแชท `_save_error` (`ui/backend.py:988-994`) ไม่มีเทสต์เลย · ต้องเห็นกับเครื่องจริงว่าหน้าจอไม่ล่มและเข้าใช้ใหม่ได้ · `shutil.copy2` ไป `.bak` (`reminders.py:136-137`) ตัดไฟล์ก่อนเขียน อาจได้ .bak เสียตอนดิสก์เต็ม
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ส่วนหน้าจอ · ส่วนสคริปต์ทำทาง SSH ได้) · **เวลา:** ~45 นาที · **ความเสี่ยง:** ลืมลบไฟล์ถม = เครื่องเต็มค้าง → การ์ดสำรองเท่านั้น · SSH หลุดกลางทาง → เข้าใหม่แล้วรันบรรทัดล้างทันที · **ย้อนกลับ:** `rm -f ~/t13/pad; sudo rm -f /var/tmp/fill; df -h /`
- **ก่อนเริ่ม:** ทำ section Image แล้ว · ในเครื่องมีแค่การ์ดสำรอง · เปิด SSH ค้างไว้อีกหน้าต่าง · บัญชีทดสอบเข้าใช้ได้และ AI ตอบได้
```sh
U=ชื่อบัญชีทดสอบ                                    # แก้เป็นชื่อจริงก่อนรัน
sudo tune2fs -l "$(findmnt -no SOURCE /)" | grep -E '^(Reserved block count|Block size)'   # จดพื้นที่ที่กันไว้ให้ root
cd ~/aipc && rm -rf ~/t13 && export XDG_DATA_HOME=$HOME/t13
# เตรียมนัด 3 + แชท 1
./.venv/bin/python - <<'EOF'
from datetime import datetime, timedelta
from aipc.skills import reminders as r
from aipc.chat import store as s
st = r.ReminderStore()
for i in range(3):
    st.add(r.Reminder("before %d" % i, datetime.now().astimezone() + timedelta(days=1)))
c = s.new_conversation(); c["messages"].append({"role": "user", "content": "before"}); s.ChatStore().save(c)
print("เตรียมแล้ว นัด", len(st.items))
EOF
cat > ~/t13-full.py <<'EOF'
import json, os, pathlib
from datetime import datetime, timedelta
from aipc.skills import reminders as r
from aipc.chat import store as s
st = r.ReminderStore()
try:
    st.add(r.Reminder("full", datetime.now().astimezone() + timedelta(days=1))); print("add บันทึกได้ (ดิสก์ยังไม่เต็ม?)")
except OSError as e:
    print("add errno", e.errno)
cs = s.ChatStore(); cid = cs.list()[0]["id"]; c = cs.load(cid)
c["messages"].append({"role": "user", "content": "x" * 100000})
try:
    cs.save(c); print("chat บันทึกได้ (ดิสก์ยังไม่เต็ม?)")
except OSError as e:
    print("chat errno", e.errno)
base = pathlib.Path(os.environ["XDG_DATA_HOME"]) / "aipc"
try:
    json.loads((base / "reminders.json.bak").read_text(encoding="utf-8")); bak = True
except (OSError, ValueError):
    bak = False
st2 = r.ReminderStore()
print("n", len(st2.items), "broken", st2.broken, "from_bak", st2.recovered_from_backup, "bak_readable", bak, "chat_msgs", len(cs.load(cid)["messages"]))
EOF
# ถมดิสก์: root ถมจนผู้ใช้ทั่วไปเหลือ 16 MB แล้วผู้ใช้ถมส่วนที่เหลือ (df ของผู้ใช้ไม่นับพื้นที่ที่กันไว้ให้ root)
sudo fallocate -l $(( $(df --output=avail -B1 / | tail -1) - 16*1024*1024 )) /var/tmp/fill
dd if=/dev/zero of=$HOME/t13/pad bs=64k 2>/dev/null; df -h /     # Avail ต้องเป็น 0
./.venv/bin/python ~/t13-full.py | tee /tmp/t13.txt
# ที่จอ (ขณะดิสก์ยังเต็ม): เข้าบัญชีทดสอบ · เพิ่มนัด 1 อัน · ถาม AI 1 ข้อ · ดูข้อความ · ออกจากระบบแล้วเข้าใหม่
pgrep -u "$U" -af aipc.ui | head -2                 # หลังเข้าใหม่ต้องเจอ
# ล้าง (ห้ามข้าม)
rm -f $HOME/t13/pad; sudo rm -f /var/tmp/fill; df -h /
./.venv/bin/python -c 'from datetime import datetime,timedelta; from aipc.skills import reminders as r; st=r.ReminderStore(); st.add(r.Reminder("after", datetime.now().astimezone()+timedelta(days=1))); print("after n", len(st.items))' | tee -a /tmp/t13.txt
unset XDG_DATA_HOME; rm -rf ~/t13 ~/t13-full.py
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) df แสดง Avail 0 · `add errno 28` และ `chat errno 28` · `n 3` · `broken False` · `chat_msgs 1` (ไฟล์เดิมไม่เสีย) · `bak_readable True` (อาจไม่ผ่านกับโค้ดตอนนี้ ให้บันทึกตามจริง) · หลังล้าง `after n 4` · ที่จอ: เพิ่มนัดแล้วขึ้นการ์ด "บันทึกไม่สำเร็จ: …" (ไม่ใช่ "บันทึกแล้ว") · ถาม AI แล้วมีข้อความ "บันทึกประวัติไม่สำเร็จ (…)" และคำตอบยังแสดงอยู่ · หน้าจอไม่ล่ม และออกแล้วเข้าใหม่ได้ 1/1 (pgrep เจอโปรเซส)
- **บันทึกผล:** บนโน้ตบุ๊ก `scp "$PI:/tmp/t13.txt" .` · ใส่การ์ดหลักคืน · บน Pi: `D=docs/benchmarks/$(date +%F)-pi5-t13 && mkdir -p $D` + คัด t13.txt ขึ้นมา + `$D/README.md` (ค่า tune2fs, ผลหน้าจอ) → `git add docs/benchmarks && git commit -m "bench(pi5): T13 ดิสก์เต็มบนการ์ดสำรอง"` · เสร็จแล้วเขียน image ลงการ์ดสำรองใหม่

### V55 กล้อง USB + ลงทะเบียน + สแกนจริง 20 ครั้ง
- **ตอบข้อ audit:** vision-2, vision-1
- **ทำไมต้องทดสอบ:** ผลกล้องบน Pi 5 มีครั้งเดียว (30.1 ภาพ/วิ) รันด้วย OpenCV 4.10 จาก /tmp ไม่มีไฟล์ (STATUS บรรทัด 61 "ยังไม่ใช่ระดับ 4") · doctor 2026-09-29 ขึ้น "ไม่พบกล้อง" · `camera test` พิมพ์ทางจออย่างเดียว ไม่เขียนไฟล์ · เวลาสแกนจริงมีแต่ Pi 4 (0.75–1.22 วิ) · `total_ms` ไม่รวมเวลาโหลดโมเดลและเปิดกล้อง (`src/aipc/vision/pipeline.py` บรรทัด 164)
- **ต้องอยู่หน้าเครื่อง:** ใช่ (เสียบกล้อง + นั่งหน้ากล้อง · สั่งทาง SSH ได้) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · แม่แบบใบหน้าจริงของเจ้าของ (ตัวเลข 128 ค่า ไม่มีภาพ) จะอยู่ใน `~/.local/share/aipc` ของ aipc2030 · log ไม่มีภาพ · **ย้อนกลับ:** `./.venv/bin/python -m aipc.vision.camera delete` (ลบแม่แบบ · ทำหลัง section PAD)
- **ก่อนเริ่ม:** เสียบกล้อง USB · ไม่มีโปรแกรมอื่นใช้กล้อง · ผ่าน "เช็กเครื่องว่าง" · ทำหลัง section LFW · แสงห้องปกติ
```sh
cd ~/aipc
ls /dev/video* && cat /sys/class/video4linux/video*/name | sort | uniq -c   # ต้องมีชื่อกล้อง USB นอกจากโหนดของชิป
W=~/bench-out/$(date +%F)-pi5-camera-face-live; mkdir -p $W/state
{ date -Is; git rev-parse HEAD; ./.venv/bin/python -c 'import cv2;print("opencv",cv2.__version__)'; cat /sys/class/video4linux/video*/name; } > $W/env.txt 2>&1
./.venv/bin/python -m aipc.bench machine > $W/machine.json
# 1) กล้องอย่างเดียว 10 วิ (ไม่มี --snap = ไม่บันทึกภาพ)
./.venv/bin/python -m aipc.vision.camera test --seconds 10 | tee $W/camera-test.txt
# 2) doctor เขียนลงโฟลเดอร์ผล (ไม่ชนไฟล์ doctor เดิมใน docs/benchmarks)
./.venv/bin/python -m aipc.doctor --save --out $W
# 3) ลงทะเบียน: พิมพ์ ยินยอม แล้วทำ 5 ท่าใน 40 วิ · log แยกไว้ในโฟลเดอร์ผล
export XDG_STATE_HOME=$W/state
./.venv/bin/python -m aipc.vision.camera enroll
# 4) สแกน 20 ครั้ง นั่งตามปกติ
read -r -p 'นั่งหน้ากล้องแล้วกด Enter ' _
./.venv/bin/python -m aipc.vision.camera scan --times 20 --who $USER | tee $W/scan-20.txt
./.venv/bin/python -m aipc.vision.report $W/state/aipc/face-scans.log --out $W/report.json > /dev/null
# 5) เวลาแบบเริ่มจากศูนย์ 5 ครั้ง (รวมเปิด Python + โหลดโมเดล + เปิดกล้อง = ขอบบนของเวลาที่ผู้ใช้รอ)
TIMEFORMAT='wall %R s'; { for i in 1 2 3 4 5; do time ./.venv/bin/python -m aipc.vision.camera scan --times 1 --who $USER; done; } 2>&1 | tee $W/cold-scan-5.txt
unset XDG_STATE_HOME
mv $W/state/aipc/*.log $W/ && rm -r $W/state
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) `camera-test.txt` ขึ้น `ภาพ 1280×720 · MJPG` · ≥ 15 ภาพ/วิ (เกณฑ์การ์ด 0011) · ความสว่างเฉลี่ย 50–205 · `env.txt` ขึ้น opencv 5.0.0 · ไฟล์ doctor .json ใน $W ข้อ `camera` = `ผ่าน` · enroll ขึ้น `ลงทะเบียนแล้ว` · `report.json`: `time_ms.median` ≤ 1500 และ `time_ms.p95` ≤ 3000 · `per_subject.<ชื่อ>.correct` ≥ 19 จาก 20 · `wrong_person` = 0 · `cold-scan-5.txt` รายงานเฉย ๆ ไม่ใช้ตัดสิน (รวมเวลาเปิด Python ที่หน้าจอจริงไม่มี)
- **บันทึกผล:**
```sh
cp -r $W docs/benchmarks/
git add docs/benchmarks/$(basename $W) && git commit -m 'bench(pi5): กล้อง USB OpenCV 5.0.0.93 + สแกนใบหน้าจริง 20 ครั้ง'
```

### V56 ใบหน้าพร้อม LLM (แย่ง CPU)
- **ตอบข้อ audit:** vision-3
- **ทำไมต้องทดสอบ:** ระบบใบหน้าไม่ตั้ง `cv2.setNumThreads` (grep ใน src/ ไม่เจอ) จึงใช้ทุกคอร์ · LLM บน Pi 5 ใช้ threads 3 (threads 4 throttle ทุกรอบ) · ยังไม่มีผลวัดตอนใช้พร้อมกันทั้ง Pi 4 และ Pi 5 · ภาพสดบน Pi 4 ตอนไม่มี LLM ต่ำสุด 5.0 ภาพ/วิ ชิดเกณฑ์แล้ว
- **ต้องอยู่หน้าเครื่อง:** ใช่ (นั่งหน้ากล้องตลอด · สั่งทาง SSH) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ · เครื่องร้อน (throttle = ผลไม่ใช่ระดับ 4 แต่ยังบอกสภาพใช้งานจริงได้) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง section "กล้อง USB + สแกนจริง" (ต้องมีแม่แบบแล้ว) · ไม่มี llama-server หรือ measure-llm ค้าง · อุณหภูมิ < 55°C
```sh
cd ~/aipc
M=models/typhoon2.5-qwen3-4b-q4_k_m.gguf; B=~/llama.cpp/build/bin/llama-bench
ls -l $M $B                                      # ต้องมีทั้งสองไฟล์
pgrep -af 'llama-|curl|measure-llm' || echo ไม่มีงานค้าง
until [ $(vcgencmd measure_temp | tr -dc 0-9 | cut -c1-2) -lt 55 ]; do sleep 15; done
W=~/bench-out/$(date +%F)-pi5-face-llm-contention; mkdir -p $W/state
{ date -Is; git rev-parse HEAD; cat /proc/loadavg; ./.venv/bin/python -c 'import cv2;print("cv2 threads",cv2.getNumThreads())'; } > $W/env.txt
./.venv/bin/python -m aipc.bench machine > $W/machine.json
mon() { while :; do v=$(vcgencmd get_throttled | cut -d= -f2); echo $(date +%T) $v now=$((v & 0xF)) $(vcgencmd measure_temp) $(vcgencmd measure_clock arm) fan=$(cat /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input); sleep 2; done; }
mon > $W/thermal.txt & MON=$!
# ก) LLM อย่างเดียว (สร้าง 256 token × 3 รอบ · threads 3)
$B -m $M -t 3 -p 0 -n 256 -r 3 -o json > $W/llm-alone.json
# ข) ใบหน้าอย่างเดียว 20 วิ (นั่งหน้ากล้อง)
read -r -p 'นั่งหน้ากล้องแล้วกด Enter ' _
./.venv/bin/python -m aipc.vision.camera check --seconds 20 | tee $W/face-alone.txt
# ค) พร้อมกัน: LLM เบื้องหลัง + check 20 วิ วนจน LLM จบ
$B -m $M -t 3 -p 0 -n 256 -r 3 -o json > $W/llm-with-face.json & P=$!
sleep 20
while kill -0 $P 2>/dev/null; do ./.venv/bin/python -m aipc.vision.camera check --seconds 20 >> $W/face-with-llm.txt; done
# ง) สแกน 10 ครั้งระหว่าง LLM สร้างข้อความ
$B -m $M -t 3 -p 0 -n 512 -r 1 -o json > /dev/null & P=$!; sleep 20
XDG_STATE_HOME=$W/state ./.venv/bin/python -m aipc.vision.camera scan --times 10 --who $USER | tee $W/scan-with-llm.txt
wait $P; kill $MON
mv $W/state/aipc/face-scans.log $W/scan-with-llm.log && rm -r $W/state
grep -c 'now=[1-9]' $W/thermal.txt
./.venv/bin/python - $W <<'EOF' | tee $W/summary.txt
import json, re, statistics, sys
W = sys.argv[1]
tg = lambda f: json.load(open(f'{W}/{f}'))[0]['avg_ts']
a, b = tg('llm-alone.json'), tg('llm-with-face.json')
print('tg alone %.3f · with face %.3f · %.0f%%' % (a, b, 100 * b / a))
fr = lambda f: [int(x) for x in re.findall(r'อ่าน (\d+) เฟรม', open(f'{W}/{f}', encoding='utf-8').read())]
print('frames/20s alone', fr('face-alone.txt'), '· with llm (ไม่นับตัวสุดท้าย)', fr('face-with-llm.txt')[:-1])
ms = [float(x) for x in re.findall(r'เวลาจริง (\d+) ms', open(f'{W}/scan-with-llm.txt', encoding='utf-8').read())]
print('scan with llm median %.0f ms n=%d' % (statistics.median(ms), len(ms)))
EOF
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) ทุกค่าใน `with llm` ≥ 100 เฟรมต่อ 20 วิ (≥ 5 ภาพ/วิ ตามเกณฑ์การ์ด 0010) · สแกนระหว่าง LLM median ≤ 1500 ms (n = 10) · tg ตอนมีใบหน้า ≥ 85% ของ tg ตอน LLM อย่างเดียว (เกณฑ์ 15% ของข้อ 7.3) · จดจำนวนบรรทัด `now=[1-9]` ไว้ในผล · ไม่ผ่าน = แก้ทีละอย่างแล้ววัดใหม่ในโฟลเดอร์ใหม่ (เช่น `cv2.setNumThreads(2)` ต้องแก้โค้ดก่อน)
- **บันทึกผล:**
```sh
cp -r $W docs/benchmarks/
git add docs/benchmarks/$(basename $W) && git commit -m 'bench(pi5): ใบหน้าพร้อม LLM threads 3'
```

### V57 PAD spot test: รูปพิมพ์และรูปบนจอมือถือ
- **ตอบข้อ audit:** vision-4
- **ทำไมต้องทดสอบ:** 99.35% เป็นผลการจดจำบนวินโดวส์ ไม่ได้ผ่าน PAD · PAD ยังไม่มีตัวเลขเลย (หลักฐานเดียวคือภาพ LFW ที่ป้อนตรง ไม่ผ่านกล้อง) · เกณฑ์ APCER ใน face-protocol ยังไม่กำหนด (เสนอ ≤ 10% ต่อประเภท) · **ข้อสังเกตจากโค้ด:** `camera scan --who X` ในโหมด 1:1 ตั้งชื่อแม่แบบเป็น X (`src/aipc/vision/camera.py` บรรทัด 262–263) การปลอมที่ผ่านจึงถูก `report` นับเป็น `correct` ไม่ใช่ `wrong_person` · ใช้ `--who $USER` ทุกประเภท แยกประเภทด้วยโฟลเดอร์ log · สำหรับการปลอม `correct` = จำนวนที่ถูกรับ (APCER)
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ถือรูป/มือถือหน้ากล้อง) · **เวลา:** ~40 นาที · **ความเสี่ยง:** ใช้รูปของเจ้าของเองที่ยินยอมเท่านั้น · ลบรูปทั้งไฟล์และกระดาษภายในวันเดียวกัน (face-protocol ข้อ 3) · **ย้อนกลับ:** `./.venv/bin/python -m aipc.vision.camera delete` เมื่อเสร็จ section นี้
- **ก่อนเริ่ม:** มีแม่แบบจาก section "กล้อง USB" · เตรียมรูปหน้าตัวเองพิมพ์ A4 1 แผ่น และรูปเดียวกันบนมือถือ (ความสว่างสูงสุด) · ไม่มีการวัดอื่นค้าง · **commit เกณฑ์ก่อนวัด (H9)** · วิดีโอบนจอไม่อยู่ในรอบนี้
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-face-pad-spot; mkdir -p $D
cat > $D/criteria.md <<'EOF'
# PAD spot test · ประกาศก่อนวัด (H9)
- ผู้ทดสอบ 1 คน (เจ้าของ · ยินยอม) · แม่แบบจาก camera enroll · กล้อง USB · แสงห้องปกติ
- ประเภทละ 20 ครั้ง: คนจริง / รูปพิมพ์ A4 / รูปบนจอมือถือ · ทุกครั้งใช้ --who เจ้าของ
- ผ่าน: คนจริง frr ≤ 0.05 และ bpcer ≤ 0.05 · การปลอมแต่ละประเภทถูกรับเป็นเจ้าของ ≤ 2/20 (APCER ≤ 10% ค่าเสนอใน face-protocol)
- n = 20 = ผลเบื้องต้น (แผนเต็ม ≥ 60 ต่อประเภท) · ไม่ใช่ด่านความปลอดภัย (รุ่นนี้ไม่ใช้ใบหน้าที่หน้า Login)
EOF
git add $D && git commit -m 'bench(pi5): ประกาศเกณฑ์ PAD spot test ก่อนวัด'
W=~/bench-out/$(date +%F)-pi5-face-pad-spot; for t in real print screen; do mkdir -p $W/$t; done
git rev-parse HEAD > $W/env.txt
read -r -p 'คนจริง: นั่งหน้ากล้องแล้วกด Enter ' _
XDG_STATE_HOME=$W/real   ./.venv/bin/python -m aipc.vision.camera scan --times 20 --who $USER | tee $W/real.txt
read -r -p 'รูปพิมพ์: ถือกระดาษ A4 ระยะเท่าหน้าจริง แล้วกด Enter ' _
XDG_STATE_HOME=$W/print  ./.venv/bin/python -m aipc.vision.camera scan --times 20 --who $USER | tee $W/print.txt
read -r -p 'จอมือถือ: ถือมือถือแสดงรูปหน้าตัวเอง แล้วกด Enter ' _
XDG_STATE_HOME=$W/screen ./.venv/bin/python -m aipc.vision.camera scan --times 20 --who $USER | tee $W/screen.txt
for t in real print screen; do ./.venv/bin/python -m aipc.vision.report $W/$t/aipc/face-scans.log --out $W/$t.json > /dev/null; mv $W/$t/aipc/face-scans.log $W/$t-face-scans.log; rm -r $W/$t; done
./.venv/bin/python - $W <<'EOF' | tee $W/summary.txt
import json, sys
W = sys.argv[1]
for t in ('real', 'print', 'screen'):
    d = json.load(open(f'{W}/{t}.json', encoding='utf-8'))
    c = next(iter(d['per_subject'].values()), {})
    print(t, 'ครั้ง', d['attempts'], '· รับเป็นเจ้าของ', c.get('correct', 0),
          '· ปัดว่าปลอม', c.get('spoof_rejected', 0), '· ปฏิเสธเหตุอื่น', c.get('rejected', 0) - c.get('spoof_rejected', 0),
          '· frr', d['frr'], '· bpcer', d['bpcer'])
EOF
```
- **ผ่านเมื่อ:** ตาม `criteria.md` ที่ commit ไว้ก่อน · ทุกประเภท `ครั้ง` = 20 · real: frr ≤ 0.05 และ bpcer ≤ 0.05 · print และ screen: "รับเป็นเจ้าของ" ≤ 2 ต่อประเภท (= APCER) · รายงาน "ปัดว่าปลอม" กับ "ปฏิเสธเหตุอื่น" แยกกัน เพื่อบอกว่ากันได้เพราะ PAD หรือเพราะ quality gate
- **บันทึกผล:**
```sh
cp $W/* $D/
git add $D && git commit -m 'bench(pi5): PAD spot test 20 ครั้งต่อประเภท (ผลเบื้องต้น)'
./.venv/bin/python -m aipc.vision.camera delete   # ลบแม่แบบของ aipc2030
# ลบรูปในมือถือ และทำลายกระดาษวันนี้
```

### V58 หน้าจอ V2: RAM หลังใช้กล้อง + ลงทะเบียน 5 ท่า
- **ตอบข้อ audit:** vision-9, vision-1
- **ทำไมต้องทดสอบ:** `release_memory` (malloc_trim) ได้ผลบน Pi 4 (115/139 → 96/96 MB ใน ramtest) แต่หน้าจอจริงหลังแก้อ่าน RSS ได้ครั้งเดียว · เกณฑ์การ์ด 0010 "ครบ 5 ท่า ≤ 45 วิ ในครั้งแรก" ไม่ผ่านบน Pi 4 (2/6 · ขาดท่าก้ม) · ยังไม่เคยวัดบน Pi 5 · สแกนจากหน้าจอเขียน log ไม่มี subject (`src/aipc/ui/face.py` บรรทัด 375) จึงใช้ `report` ไม่ได้ ต้องอ่าน log ตรง
- **ต้องอยู่หน้าเครื่อง:** ใช่ (กดที่หน้าจอ + นั่งหน้ากล้อง · ตัวเก็บข้อมูลสั่งทาง SSH) · **เวลา:** ~25 นาที · **ความเสี่ยง:** ต่ำ อ่านอย่างเดียว · **ย้อนกลับ:** ไม่เปลี่ยนระบบ · หยุดตัวเก็บด้วย `sudo systemctl stop $S` · ลบแม่แบบด้วยปุ่ม "ลบ" ในหน้าใบหน้าของฉันเมื่อเสร็จ
- **ก่อนเริ่ม:** ทำ runbook `docs/runbooks/pi5-setup.md` ขั้น 9 แล้ว (หน้า Login V2 + บัญชี + AI) · login ที่หน้าจอด้วยบัญชีทดสอบ · SSH เข้าเป็น aipc2030 · เสียบกล้องแล้ว · ไม่มีการวัดอื่นค้าง · **หมายเหตุ:** หลัง install-accounts.sh มี `KillUserProcesses=yes` โปรเซสที่เปิดจาก SSH (แม้ใช้ setsid) จะถูกปิดเมื่อ SSH หลุด จึงเปิดตัวเก็บเป็น service ชั่วคราวด้วย `systemd-run` แทน
```sh
# SSH เป็น aipc2030 · U = บัญชีทดสอบที่ login หน้าจออยู่
U=<ชื่อบัญชีทดสอบ>; W=/home/$U/face-screen-$(date +%F); S=aipc-sampler-$(date +%H%M%S)
loginctl list-sessions --no-legend | grep $U      # ต้องเห็น session ของ U ที่ seat0
sudo -u $U mkdir -p $W
sudo systemd-run --unit=$S --uid=$U /opt/aipc-v2/scripts/pi/sample-session.sh $W/sampler.tsv 30
sleep 3; sudo tail -2 $W/sampler.tsv             # คอลัมน์ pid ต้องเป็นตัวเลข ไม่ใช่ '-'
# ที่หน้าจอ: ตั้งค่า → ใบหน้าของฉัน → ลงทะเบียน (ครั้งแรกของวัน · ห้ามลองก่อน) → ทดลองสแกน 5 ครั้ง เว้นครั้งละ ~30 วิ
# เสร็จแล้วรอ 1 นาที แล้วสรุปทาง SSH:
sudo systemctl stop $S
D=~/aipc/docs/benchmarks/$(date +%F)-pi5-card0010; mkdir -p $D
sudo cat $W/sampler.tsv > $D/sampler.tsv
sudo tail -1 /home/$U/.local/state/aipc/face-enroll.log > $D/face-enroll.log
sudo tail -5 /home/$U/.local/state/aipc/face-scans.log > $D/face-scans.log
awk -F'\t' 'NR>1 && $3!="-" && $3!="" {if($3+0>m)m=$3+0} END{printf "RSS สูงสุด %.1f MB\n", m/1024}' $D/sampler.tsv | tee $D/rss-summary.txt
# sampler อ่านทุก 0.5 วิ → 10 แถว = 5 วิหลังปิดกล้อง
awk -F'\t' 'NR>1{n++; t[n]=$1; r[n]=$3; c[n]=$4} END{for(i=2;i<=n;i++){ if(!s && c[i]==1){printf "ก่อนเปิดกล้องครั้งแรก %.1f MB\n", r[i-1]/1024; s=1} if(c[i-1]==1 && c[i]==0){j=i+10; if(j>n)j=n; printf "จบงาน %s · RSS 5 วิหลังปิดกล้อง %.1f MB\n", t[i], r[j]/1024} }}' $D/sampler.tsv | tee -a $D/rss-summary.txt
cat $D/face-enroll.log
python3 -c 'import json,sys,statistics;r=[json.loads(l) for l in open(sys.argv[1])];print("scan total_ms",[x["total_ms"] for x in r],"median",statistics.median(x["total_ms"] for x in r))' $D/face-scans.log | tee -a $D/rss-summary.txt
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน) RSS สูงสุด ≤ 415 MB (385 + 30 ตามการ์ด 0010) · RSS 5 วิหลังจบแต่ละงาน ≤ ค่าก่อนเปิดกล้อง + 60 MB · งานสุดท้าย ≤ งานแรก + 10 MB (ไม่โตต่อเนื่อง) · face-enroll.log: `result` = `enrolled`, `missing` = `[]`, `seconds` ≤ 45 · `frames_seen ÷ seconds` ≥ 5 · สแกน 5 ครั้ง total_ms median ≤ 1500 (ยังไม่รวมเวลาโหลดโมเดลและเปิดกล้อง · ถ่ายวิดีโอมือถือจากกดถึงผล 1 ครั้งไว้เทียบ จดเวลาลง README)
- **บันทึกผล:** (SSH เป็น aipc2030)
```sh
git -C ~/aipc rev-parse HEAD > $D/env.txt; readlink -f /opt/aipc-v2 >> $D/env.txt
cd ~/aipc && git add $D && git commit -m 'bench(pi5): RAM หน้าจอหลังใช้กล้อง + ลงทะเบียน 5 ท่า'
```

### V59 T1 บูต · T7 AI พัง · T12 สองบัญชี
- **ตอบข้อ audit:** evidence-2
- **ทำไมต้องทดสอบ:** แผน T1–T14 (ข้อเสนอรอบ 3 หัวข้อ 9) ยังไม่มีผลบน Pi 5 สักข้อ · Pi 4 มี T1 3/3 (เกณฑ์ 10/10) และ T7 6 วิกับโมเดล 0.5B ซึ่งใช้แทนโมเดล 4B (2.5 GB) ไม่ได้ · T12 บน Pi 4 ทดสอบแค่ home 0700 ยังไม่ได้ลอง socket · เวลาเปิดเครื่องถึงหน้า Login (BRIEF ≤ 45 วิ) ไม่เคยวัด
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ดูจอ · สมัครบัญชี · จับเวลา) · **เวลา:** ~120 นาที · **ความเสี่ยง:** รีบูตหลายครั้ง ต้องมีทางเข้าสำรอง SSH และ Ctrl+Alt+F2 · ห้ามรีบูตตอนมีคนอื่นใช้หน้าจอ · T10 (ดึงปลั๊ก) และ T13 (ดิสก์เต็ม) ไม่อยู่ใน section นี้ ทำบนการ์ดสำรองเท่านั้น · หมายเหตุ: `MemoryMax=4G` ของ aipc-llm ยังไม่มีผล (cgroup memory ปิดอยู่) ไม่กระทบ T7 · **ย้อนกลับ:** หน้า Login ไม่ขึ้น → Ctrl+Alt+F2 หรือ SSH → `sudo ~/aipc/scripts/pi/install-greeter.sh --rollback` → `sudo reboot` · ลบบัญชีทดสอบตามคำสั่งท้าย section (ถามยืนยันก่อน)
- **ก่อนเริ่ม:** ทำ runbook ขั้น 9 แล้ว · ลองทางเข้าสำรองทั้งสองทางก่อน · ไม่มีการวัดค้าง · สมัครบัญชีทดสอบ A และ B ที่หน้า Login
```sh
# ---------- T1: รีบูต 10 รอบ (ทีละรอบ · SSH เป็น aipc2030) ----------
loginctl list-sessions --no-legend     # ก่อนรีบูตทุกครั้ง: ต้องไม่มีคนอื่นใช้หน้าจอ (มี = ให้ออกจากระบบก่อน)
sudo reboot
# ที่จอ: จดว่าขึ้นหน้า Login ของ V2 ไหม (ใช่/ไม่) · SSH เข้าใหม่เป็น aipc2030 แล้วรัน:
W=~/bench-out/pi5-t-tests; mkdir -p $W
{ echo "== $(date -Is)"; systemd-analyze; systemctl is-active greetd; pgrep -u _greetd -af 'aipc[.]ui' | head -2; vcgencmd get_throttled; } >> $W/t1.txt
grep -c '^== ' $W/t1.txt               # นับรอบที่ทำแล้ว
# 2 รอบสุดท้ายแบบเปิดเครื่องจริง: sudo poweroff → รอไฟเขียวดับ → ถอดปลั๊ก 10 วิ → เสียบ แล้วจับเวลามือถือจากเสียบถึงหน้า Login

# ---------- T7: AI พังระหว่างตอบ (3 รอบ) ----------
# SSH เป็นบัญชี A ที่ login หน้าจออยู่ · ที่จอพิมพ์คำถามยาว ๆ แล้วระหว่าง AI กำลังตอบให้รัน:
echo $XDG_RUNTIME_DIR; systemctl --user is-active aipc-llm   # ต้องได้ /run/user/<uid> และ active
S=$XDG_RUNTIME_DIR/aipc/llm.sock
systemctl --user kill -s KILL aipc-llm; t0=$(date +%s)
until curl -sf --unix-socket $S http://localhost/health >/dev/null; do sleep 1; done
echo T7 กลับมาใน $(( $(date +%s) - t0 )) วิ | tee -a ~/t7.txt
systemctl --user show aipc-llm -p NRestarts | tee -a ~/t7.txt

# ---------- T12: B พยายามอ่านของ A ----------
# A login หน้าจอค้างไว้ · SSH เข้าเป็นบัญชี B:
A=<ชื่อบัญชี A>; UA=$(id -u $A)
{ ls -ld /home/$A; ls /home/$A; ls /home/$A/.local/share/aipc; cat /home/$A/.local/share/aipc/face-template.json
  curl -s --unix-socket /run/user/$UA/aipc/llm.sock http://localhost/health; echo curl exit=$?; } 2>&1 | tee ~/t12.txt
```
- **ผ่านเมื่อ:** (ประกาศก่อนรัน · ตามตาราง T ในข้อเสนอรอบ 3) T1: ขึ้นหน้า Login ของ V2 10/10 · `greetd` = `active` ทุกรอบ (`grep -c '^active' $W/t1.txt` = 10) · เปิดเครื่องจริงถึงหน้า Login ≤ 45 วิ ทั้ง 2 รอบ (systemd-analyze เป็นข้อมูลประกอบ ไม่รวมเวลา firmware) · T7: กลับมาใน ≤ 60 วิ ทั้ง 3 รอบ · NRestarts เพิ่มทีละ 1 · หน้าจอบอก "AI กำลังเริ่มใหม่" แล้วถามต่อได้โดยไม่ต้อง login ใหม่ (ใช่/ไม่ ทั้ง 3 รอบ) · T12: `ls -ld` ขึ้น `drwx------` · อีก 3 คำสั่งอ่านขึ้น `Permission denied` · `curl exit` ≠ 0
- **บันทึกผล:** (SSH เป็น aipc2030)
```sh
W=~/bench-out/pi5-t-tests
sudo cat /home/<A>/t7.txt > $W/t7.txt; sudo cat /home/<B>/t12.txt > $W/t12.txt
git -C ~/aipc rev-parse HEAD > $W/env.txt
# เขียน $W/README.md สั้น ๆ: ผลใช่/ไม่ของแต่ละรอบ T1 + เวลามือถือ + สิ่งที่เห็นบนจอตอน T7
D=~/aipc/docs/benchmarks/$(date +%F)-pi5-t-tests; cp -r $W $D
cd ~/aipc && git add $D && git commit -m 'bench(pi5): T1 บูต 10 รอบ · T7 AI พัง · T12 สองบัญชี'
```
- **ลบบัญชีทดสอบเมื่อเลิกใช้** (ทีละบัญชี · ถามยืนยันก่อนลบ · ห้ามใช้กับ aipc2030):
```sh
N=<ชื่อบัญชีทดสอบ>; id $N; ls -ld /home/$N
read -r -p "ลบบัญชี $N และ home ทั้งหมด? พิมพ์ชื่อซ้ำเพื่อยืนยัน: " x
[ "$x" = "$N" ] && [ "$N" != aipc2030 ] && { sudo loginctl terminate-user $N; sudo userdel -r $N; sudo rm -f /var/lib/aipc/recovery/$N.json; }
sudo ls /var/lib/aipc/recovery; ls /home    # ต้องไม่เหลือของ $N
```

### V60 T6 ไม่รั่ว 2 ช่วง: ใช้งานปกติ / ระหว่าง forge
- **ตอบข้อ audit:** gaps-1, evidence-2
- **ทำไมต้องทดสอบ:** ข้ออ้างที่ 1 และ T6 เขียนว่า "ไม่มีข้อมูลออกนอกเครื่อง" (`docs/reviews/2026-09-28-scope-cut.md` บรรทัด 39, 203) แต่ความต้องการอาจารย์ (ไฮบริด + `claude -p` ใน `src/aipc/skills/forge.py` บรรทัด 68–75) ทำให้ forge ต่อเน็ต · ยังไม่มีผล T6 บนเครื่องไหนเลย · บน Pi 5 มี rpi-connect (user service ของ aipc2030 · linger = yes จึงรันตลอด) ซึ่งต่อออกนอกเครื่องเสมอ จึงต้องแยกตามชื่อโปรเซส
- **ต้องอยู่หน้าเครื่อง:** ใช่ (ใช้งานหน้าจอ 30 นาที · ตัวเก็บข้อมูลสั่งทาง SSH) · **เวลา:** ~50 นาที · **ความเสี่ยง:** ต่ำ อ่านอย่างเดียว · สุ่มดูทุก 2 วิ อาจพลาดการเชื่อมต่อที่สั้นมาก (เขียนเป็นข้อจำกัดในเล่ม) · **ย้อนกลับ:** ไม่เปลี่ยนระบบ
- **ก่อนเริ่ม:** ทำหลัง runbook ขั้น 9 · บัญชีทดสอบ login หน้าจอ · SSH เป็น aipc2030 ค้างไว้ตลอด (ถ้า SSH หลุด ตัวเก็บจะหยุด) · ไม่มีการวัดอื่นค้าง · ช่วง ข ต้องมีเน็ตและ `claude` ที่ login แล้วของ aipc2030 (ดู section ความพร้อมก่อนสาธิต) · **เกณฑ์ช่วง ข เป็นเกณฑ์ใหม่** → commit ไฟล์เกณฑ์ก่อนเริ่ม (H9) · ความหมาย "ไฮบริด" ใช้ตามร่างข้ออ้างรอบ 4 ที่ Pakon ตัดสิน (ไม่ส่งอาจารย์ · 2026-10-07)
```sh
# SSH เป็น aipc2030
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-t6; mkdir -p $D
cat > $D/criteria.md <<'EOF'
# T6 ไม่รั่ว · ประกาศก่อนวัด (H9)
- ช่วง ก ใช้งานปกติ 30 นาที (แชท 5 ข้อ · ตั้งนัด · สรุปข้อความ · สแกนหน้าในหน้าตั้งค่า): การเชื่อมต่อออกนอกเครื่องจากโปรเซส python / llama-server / aipc = 0
- ช่วง ข ระหว่าง forge 1 ครั้ง: ต่อออกได้เฉพาะโปรเซส claude (หรือ node ที่ claude เปิด) · python / llama-server = 0
- วิธี: ss -tunp state established ทุก 2 วิ ด้วย root · ไม่นับ loopback · sshd และ rpi-connect รายงานแยก
EOF
git add $D && git commit -m 'bench(pi5): ประกาศเกณฑ์ T6 สองช่วงก่อนวัด'
W=~/bench-out/$(date +%F)-pi5-t6; mkdir -p $W; git rev-parse HEAD > $W/env.txt
sudo -v   # พิมพ์รหัสผ่านเองครั้งเดียว
# ก) ใช้งานปกติ 30 นาที (เริ่มใช้หน้าจอหลังสั่งบรรทัดนี้)
sudo sh -c 'end=$(( $(date +%s) + 1800 )); while [ $(date +%s) -lt $end ]; do ss -tunpH state established | sed "s/^/$(date +%T) /"; sleep 2; done' > $W/t6-normal.txt
grep -vE '127\.0\.0\.1|\[::1\]|::ffff:127\.' $W/t6-normal.txt > $W/t6-normal-external.txt
grep -o 'users:(("[^"]*"' $W/t6-normal-external.txt | sort | uniq -c | tee $W/t6-normal-by-process.txt
grep -cE 'python|llama|aipc' $W/t6-normal-external.txt     # ต้องได้ 0
# ข) ระหว่าง forge 1 ครั้ง (ไม่มี claude = ข้ามช่วงนี้)
command -v claude || echo ไม่มี claude ข้ามช่วง ข
sudo -v
sudo sh -c 'end=$(( $(date +%s) + 300 )); while [ $(date +%s) -lt $end ]; do ss -tunpH state established | sed "s/^/$(date +%T) /"; sleep 2; done' > $W/t6-forge.txt & P=$!
./.venv/bin/python -m aipc.skills.forge new 'สรุปข้อความเป็นข้อ ๆ สำหรับทดสอบ T6' --out $W/forge
wait $P
grep -vE '127\.0\.0\.1|\[::1\]|::ffff:127\.' $W/t6-forge.txt | grep -o 'users:(("[^"]*"' | sort | uniq -c | tee $W/t6-forge-by-process.txt
```
- **ผ่านเมื่อ:** ตาม `criteria.md` ที่ commit ก่อนวัด · ช่วง ก: `grep -c` = 0 · ช่วง ข: `t6-forge-by-process.txt` มีแค่ claude/node, sshd, rpi-connect/wayvnc (มี python หรือ llama = ไม่ผ่าน) · rpi-connect ที่เห็นทั้งสองช่วงให้จดเป็นข้อสังเกตแยก (ไม่ใช่โปรแกรมของเรา แต่กรรมการอาจถาม · ถ้าจะปิดก่อนสาธิตเป็นเรื่องของหมวดความปลอดภัย)
- **บันทึกผล:**
```sh
cp -r $W/* $D/
git add $D && git commit -m 'bench(pi5): T6 ไม่รั่ว ใช้งานปกติ 30 นาที + ระหว่าง forge'
```

## E · คนจริง (ซ้อมสาธิต ผู้ใช้ทดลอง)

### V61 ซ้อมสาธิต 3 รอบ (มีเน็ต 2 · ออฟไลน์ 1)
- **ตอบข้อ audit:** gaps-2
- **ทำไมต้องทดสอบ:** ไม่มี runbook วันสาธิตใน `docs/runbooks/` · ยังไม่เคยเดินเส้นทางสาธิตครบบน Pi 5 · หน้าจอออกแบบขั้นต่ำ 1280×720 (`Main.qml` บรรทัด 9–12) แต่ทดสอบแค่จอ 1920×1080 ของ Pi 4 · ไม่มีเน็ตในห้องสอบ = เดโม forge ต้องมีทางสำรอง และนาฬิกาต้องมาจาก RTC
- **ต้องอยู่หน้าเครื่อง:** ใช่ (คีย์บอร์ดที่เครื่อง · รอบออฟไลน์ SSH ผ่าน hotspot จะหลุด ใช้ Ctrl+Alt+F2 แทน) · **เวลา:** ~90 นาที (รวมถอดปลั๊ก 10 นาทีก่อนรอบ 3) · **ความเสี่ยง:** ต่ำ · **ย้อนกลับ:** เปิดเน็ตคืน `sudo nmcli radio wifi on` แล้วเสียบสาย LAN
- **ก่อนเริ่ม:** ติดตั้งรุ่นสุดท้ายแล้ว (ก่อนทำ image การ์ด) · section "ความพร้อมก่อนสาธิต" ผ่าน · มีบัญชีสาธิต 1 บัญชี · มีนาฬิกามือถือ · ใช้จอที่จะใช้วันจริง (หรือจอ 1280×720)
```sh
# เตรียมตารางจดผล (SSH เป็น aipc2030 · 1 บรรทัดต่อขั้นต่อรอบ)
D=~/aipc/docs/benchmarks/$(date +%F)-pi5-demo-rehearsal; mkdir -p $D
printf 'round,net,step,seconds,ok,note\n' > $D/rehearsal.csv
# ลำดับขั้น (จับเวลาทุกขั้น):
# 1 เปิดเครื่อง→หน้า Login  2 เข้าสู่ระบบ  3 แชทไทย 2 ข้อ (ข้อแรกหลัง login จดแยก · ข้อสองจับเวลาถึงคำแรก)
# 4 'อีก 2 นาทีเตือนส่งงาน' (ดูว่าเตือนตรงเวลา ±1 นาที)  5 'สรุปข้อความนี้: ...'
# 6 ตั้งค่า → ใบหน้าของฉัน → ทดลองสแกน  7 (มีเน็ต) forge สร้างสกิล 1 ตัวจาก terminal ผู้ดูแล (SSH)  8 ออกจากระบบ
# ก่อนรอบ 3 (ออฟไลน์ + ทดสอบ RTC): ที่เครื่อง Ctrl+Alt+F2 → login aipc2030 แล้วรัน
sudo nmcli radio wifi off    # + ถอดสาย LAN
sudo poweroff                # รอไฟเขียวดับ → ถอดปลั๊ก 10 นาที → เสียบ = เริ่มขั้น 1 ของรอบ 3
# รอบ 3 ขั้น 1: ที่หน้าจอ Ctrl+Alt+F2 → login → date แล้วเทียบนาฬิกามือถือ → Ctrl+Alt+F7 กลับหน้า Login
# รอบ 3 ขั้น 7: เปิดผลที่บันทึกไว้แทน: docs/benchmarks/2026-09-29-skill-forge/README.md
# จบรอบ 3
sudo nmcli radio wifi on
```
- **ผ่านเมื่อ:** (ประกาศก่อนซ้อม) 3/3 รอบไม่ล่ม และไม่ต้องเปิด SSH แก้ · คำแรกของ AI ≤ 10 วิ ทุกข้อที่ไม่ใช่ข้อแรกหลัง login (อ้างเกณฑ์ ADR-007 ข้อ 2 · ข้อแรกหลัง login อาจนาน ~60 วิ เพราะ prompt รายการสกิล 1,020 token และ AI เริ่มใหม่ทุก login ให้จดแยก และวันจริงถามข้อแรกทิ้งไว้ก่อนเริ่มเดโม) · การเตือนขึ้นภายใน ±1 นาที · รอบ 3: `date` ต่างจากนาฬิกามือถือ ≤ 1 นาที หลังถอดปลั๊ก 10 นาทีโดยไม่มีเน็ต · รอบ 3 ทำขั้น 1–6 และ 8 ได้ครบ
- **บันทึกผล:**
```sh
# กรอก rehearsal.csv ให้ครบ + เขียน README.md 5–10 บรรทัด: ปัญหาที่เจอ ทางแก้ที่จะใช้วันจริง
cd ~/aipc && git add $D && git commit -m 'bench(pi5): ซ้อมสาธิต 3 รอบ'
```

### V62 pilot ผู้ใช้จริง 5 คน + SUS
- **ตอบข้อ audit:** gaps-6
- **ทำไมต้องทดสอบ:** BRIEF บรรทัด 375 กำหนดผู้ใช้จริง ≥ 5 คนทำงานหลักเองได้ + SUS ≥ 70 · STATUS บรรทัด 55 และ 58 บอกว่ายังไม่เคยทดสอบกับคนจริง ≥ 5 คน · ตัวเลขสกิลทุกตัวมาจากประโยคที่ผู้พัฒนาหรือ Claude เขียนเอง · ยังไม่มีเครื่องมือในโปรเจกต์ (ใช้ CSV + สคริปต์ข้างล่าง)
- **ต้องอยู่หน้าเครื่อง:** ใช่ · **เวลา:** ~150 นาที (~30 นาทีต่อคน) · **ความเสี่ยง:** ต้องมีหนังสือยินยอมที่มีข้อใบหน้า (face-protocol ข้อ 4) · ใช้รหัส P01–P05 ไม่ใช้ชื่อจริง · ห้ามคัดไฟล์แชทของผู้ใช้ · **ย้อนกลับ:** ลบบัญชีของผู้เข้าร่วมทุกคนด้วยคำสั่งลบบัญชีทดสอบท้าย section "T1 · T7 · T12" (ถามยืนยันทีละบัญชี · ลบ `/var/lib/aipc/recovery/<ชื่อ>.json` ด้วย) แล้วตรวจ `ls /home` และ `sudo ls /var/lib/aipc/recovery`
- **ก่อนเริ่ม:** หลังหยุดเพิ่มฟีเจอร์ 9 ต.ค. · ติดตั้งรุ่นสุดท้ายแล้ว · ซ้อมสาธิตผ่าน · ไม่มีการวัดอื่น · **commit งานและเกณฑ์ก่อนคนแรก (H9)**
```sh
cd ~/aipc; D=docs/benchmarks/$(date +%F)-pi5-pilot; mkdir -p $D
cat > $D/criteria.md <<'EOF'
# pilot 5 คน · ประกาศก่อนเริ่ม (H9)
งาน 5 ข้อ ทำเองโดยไม่มีคนช่วย: 1 สมัครบัญชีและเข้าสู่ระบบ · 2 แชทถามคำถามไทย 1 ข้อ · 3 ตั้งนัด/เตือน · 4 สรุปข้อความ · 5 ลงทะเบียนใบหน้า
ผ่าน: ทุกงานมีคนทำสำเร็จเอง ≥ 4/5 คน · SUS เฉลี่ย ≥ 70 (BRIEF 5.7)
EOF
printf 'id,task,done_alone,seconds,note\n' > $D/tasks.csv
printf 'id,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10\n' > $D/sus.csv
git add $D && git commit -m 'bench(pi5): ประกาศงานและเกณฑ์ pilot ก่อนเริ่ม'
# ต่อคน: เซ็นหนังสือยินยอม → ทำ 5 งาน (จับเวลา) → แบบ SUS 10 ข้อ (คะแนน 1–5)
# กรอก tasks.csv (done_alone 1/0 · task 1–5) และ sus.csv ทันทีหลังแต่ละคน · ถ้ายินยอม จดประโยคที่พิมพ์ลง sentences.csv ด้วยมือ
# หลังคนสุดท้าย:
./.venv/bin/python - $D <<'EOF' | tee $D/summary.txt
import csv, statistics, sys
D = sys.argv[1]
s = []
for r in csv.DictReader(open(f'{D}/sus.csv', encoding='utf-8')):
    q = [int(r[f'q{i}']) for i in range(1, 11)]
    assert all(1 <= x <= 5 for x in q), r['id']
    s.append(2.5 * sum(q[i] - 1 if i % 2 == 0 else 5 - q[i] for i in range(10)))
    print(r['id'], 'SUS', s[-1])
print('SUS เฉลี่ย %.1f n=%d' % (statistics.mean(s), len(s)))
t = {}
for r in csv.DictReader(open(f'{D}/tasks.csv', encoding='utf-8')):
    t.setdefault(r['task'], []).append(r['done_alone'] == '1')
for k, v in sorted(t.items()):
    print('งาน', k, 'สำเร็จเอง', f'{sum(v)}/{len(v)}')
EOF
```
- **ผ่านเมื่อ:** ตาม `criteria.md` ที่ commit ก่อนคนแรก: ทุกงาน ≥ 4/5 คน · SUS เฉลี่ย ≥ 70 (n = 5) · ถ้าไม่ทันก่อนส่งเล่ม ให้เขียนเป็นข้อจำกัดในหัวข้อ 4.8 ตรง ๆ
- **บันทึกผล:**
```sh
git add $D && git commit -m 'bench(pi5): pilot ผู้ใช้จริง 5 คน + SUS'
# แล้วลบบัญชีผู้เข้าร่วมทุกคนตามช่อง ย้อนกลับ
```

## สิ่งที่ผู้ตรวจยืนยันไม่ได้โดยไม่มีเครื่องจริง (ดูผลตอนรัน)

- (hw) ยังไม่ได้ยืนยันบน Pi 5 ว่าการเติม cgroup_enable=memory ต่อท้าย cgroup_disable=memory ที่ firmware เติมจะเปิด memory controller ได้จริงบน kernel 6.18.50+rpt · และ user@.service มอบ memory ให้ user manager (Delegate) หรือไม่
- (hw) ไม่รู้ว่า kernel ของ Pi เปิด PSI (/proc/pressure/memory) เป็นค่าเริ่มต้นไหม · ถ้าไม่มี คอลัมน์ PSI จะเป็น '-' และต้องเขียนว่าวัดไม่ได้ (การเปิดต้องแก้ cmdline.txt อีกรอบ ไม่ได้ใส่ใน runbook)
- (hw) ไม่รู้ว่า MemorySwapMax ใช้ได้ไหม (ต้องมี memory.swap.max) · ถ้าไม่ได้ การทดสอบ 400 MB ใต้เพดาน 200 MB อาจหนีไป zram และพิมพ์ 'ไม่ถูกปิด' ทั้งที่ MemoryMax ใช้ได้
- (hw) llama.cpp commit 86ea01d: ยังไม่ได้ยืนยันว่า /v1/chat/completions คืนฟิลด์ timings, /props มี default_generation_settings.n_ctx และ total_slots, และ log มีบรรทัด 'POST /v1/chat/completions' ต่อคำขอ · ถ้าไม่มี ให้จดว่าวัดไม่ได้ ห้ามเดาค่า
- (hw) ยังไม่รู้ว่า llama-server รุ่นนี้ตั้ง slot กี่ช่องเป็นค่าเริ่มต้น และ context ต่อ slot เป็น 4096 หรือแบ่ง (ถ้าแบ่ง service จริงก็รับ prompt ยาวไม่ได้ ต้องแก้ aipc-llm-start)
- (hw) Pi OS trixie เก็บ journal ลงการ์ด (/var/log/journal) หรือใน RAM · ถ้าใน RAM SystemMaxUse ไม่มีผลกับการ์ด (section สแนปช็อตจะบอก)
- (hw) ชื่อ unit rpi-eeprom-update.service และค่าใน /etc/default/rpi-eeprom-update บน trixie ยังไม่ได้เห็นจริง · ถ้าเปิดอยู่ (อัปเดตเฟิร์มแวร์เองตอนบูต) Pakon ต้องตัดสินว่าจะปิดก่อนทำ image สอบไหม
- (hw) แบต RTC ที่ติดเครื่องเป็นรุ่นไหน (ML-2020 ชาร์จได้ หรือ CR2032 ห้ามชาร์จ) ต้องดูด้วยตาเท่านั้น
- (hw) hotspot มือถือหลุดบ่อย: section soak, RAM และโหลดโมเดล ถ้า SSH หลุดกลางทางผลจะใช้ไม่ได้ · ยังไม่มี tmux บนเครื่อง (ติดตั้งเพิ่ม = dpkg เปลี่ยน ต้องจดใน snapshot)
- (hw) llama-bench ใน soak โหลดโมเดลใหม่ทุกรอบ ไม่ใช่ 'ตอบต่อเนื่อง' ผ่าน llama-server แบบจริง · Pakon ต้องตัดสินว่ายอมรับเป็นหลักฐาน ADR-007 ข้อ 5 ได้ไหม
- (hw) นอกหมวดนี้แต่เห็นในข้อเท็จจริง: rpcbind ฟังพอร์ต 111 ที่ 0.0.0.0 และ rpi-connect เปิดอยู่ · ควรส่งให้ผู้ตรวจหมวดความปลอดภัย
- (hw) ผล measure-llm.sh รอบ 2 ยังไม่ออก · ถ้าโมเดลที่ชนะไม่ใช่ Typhoon ต้องเปลี่ยน M/T ใน section โหลดโมเดล, RAM, soak ก่อนรัน
- (llm-skills) ชื่อบรรทัด log ของ llama-server 86ea01d (n_slots, n_ctx_slot, kv_unified) และค่าเริ่มต้นของ -np ตรวจไม่ได้โดยไม่มีเครื่อง · ถ้า grep ไม่เจออะไร ให้ดู 60 บรรทัดแรกของ /tmp/ttft-cold.log เอง
- (llm-skills) -fa ของ llama-bench build นี้รับ 0/1 หรือ on/off ยังไม่รู้ จนกว่าจะรัน section ข้อมูลประกอบ (bench-flags.txt)
- (llm-skills) repo typhoon-ai/typhoon2.5-qwen3-4b-gguf มีไฟล์ Q4_0 หรือไม่ ตรวจไม่ได้จากที่นี่ · ถ้าไม่มี ส่วน Q4_0 ของ ADR-007 ต้องบันทึกว่าทำไม่ได้
- (llm-skills) ADR-007 ข้อ 4 'RAM สูงสุด ≤ 3.5 GB' ไม่ได้บอกว่านับ VmHWM (ตอนนี้ 5.64 GB รวมหน้าไฟล์โมเดลที่ mmap) หรือ RssAnon (3.2 GB) · RssAnon สูงอาจเพราะ llama.cpp คัดน้ำหนักไปจัดเรียงใหม่ในหน่วยความจำ (repack) · ต้องให้เจ้าของตัดสินก่อนใช้ตัดสิน spec และ RAM
- (llm-skills) อัตรา token ต่อตัวอักษรไทยจริงของ Typhoon ยังไม่รู้ (โค้ดเดา ÷2) · ขนาดข้อความที่เกิน context จริงจะรู้หลัง section ข้อความยาว
- (llm-skills) Qwen3-0.6B กับ Typhoon2.5 ใช้ vocab ตรงกันพอสำหรับ --model-draft หรือไม่ ต้องดูจาก spec-log บนเครื่อง
- (llm-skills) update-app.sh --apply ครั้งแรกอาจต้องใช้เน็ตโหลดไลบรารีลง wheels และขั้น 9 ของ pi5-setup (greeter/accounts/llm/reboot) ยังไม่ได้ทำบน Pi 5 · section ครบเส้น V2 จึงทำได้หลังขั้น 9 เท่านั้น · MemoryMax=4G ของ aipc-llm.service ยังไม่มีผลจนกว่าจะเปิด cgroup_enable=memory (อยู่นอกหมวดนี้)
- (llm-skills) Claude Code ตัว native รองรับ Linux aarch64 บน Pi OS trixie (page size 16K) หรือไม่ รู้ได้เมื่อรันจริงเท่านั้น
- (llm-skills) เวลาของแต่ละ section เป็นค่าประมาณจากความเร็วที่วัดไว้ (pp ~16 tok/s · tg ~4.6 tok/s) · ถ้า throttle หรือ cache หาย จะนานขึ้น
- (llm-skills) ชื่อผู้ให้คะแนนคนที่ 2 ของ ADR-007 ข้อ 1 ยังไม่มี
- (ui) รูปแบบข้อความ log เฟรมของ Qt 6 บน render loop แบบ threaded (Wayland/EGL บน Pi) ยังไม่ได้เห็นจริง audit ยืนยันแค่บนวินโดวส์ · ใช้ grep -i แล้ว แต่ถ้า frames = 0 ต้องดู ui-frames.log แล้วแก้ regex
- (ui) %{time boot} ของ QT_MESSAGE_PATTERN บน Pi ใช้นาฬิกาเดียวกับ /proc/uptime ไหม (ถ้าต่างกัน เวลาเฟรมแรกจะผิด) ต้องดูค่าจริงรอบแรก
- (ui) PySide6 wheel บน aarch64 โหลด libthai ของระบบจริงไหม และพจนานุกรม libthai ตัด 'ภาษาไทยไม่มีช่องว่างระหว่างคำ' ได้กี่จุด ต้องรันบน Pi
- (ui) Qt ได้ V3D หรือ llvmpipe และ Mesa เปิด /dev/dri/renderD128 หรือ card* ต้องดูบน Pi 5
- (ui) stderr ของหน้าจอในเซสชัน V2 ไป journal หรือ /dev/null (ui-9) ต้องดู /proc/<pid>/fd/2 หลังติดตั้งขั้น 9
- (ui) จอที่ต่อกับ Pi 5 เป็นกี่ Hz · ถ้าต่ำกว่า 50 Hz เกณฑ์ BRIEF ≥ 50 fps วัดไม่ได้
- (ui) fps และ tok/s วัดใน desktop Pi OS ไม่ใช่เซสชัน V2 (labwc -C ไม่มีแถบงาน) · หลังขั้น 9 ควรวัดซ้ำในเซสชัน V2
- (ui) เวลาเปิดเครื่องบน SSD (BRIEF บรรทัด 373 ขอทั้ง SD และ SSD) ยังไม่มีฮาร์ดแวร์ SSD
- (ui) MemoryMax=4G ของ aipc-llm.service ไม่มีผล (cgroup memory ปิด) · งบ RAM จาก section RAM เซสชันต้องอ่านคู่กับการตัดสินเรื่อง cgroup_enable=memory ในหมวดอื่น และถ้าเปลี่ยน cmdline ต้องวัดเวลาเปิดเครื่องใหม่
- (ui) raspi-config nonint gpu_has_mmu ใน aipc-session ทำงานโดยไม่ใช้ root ได้ไหม บน trixie (คัดมาจาก labwc-pi จึงน่าจะได้) ตรวจไม่ได้จากเครื่องนี้
- (security) `rpi-connect off` ถอด enable ของ user unit และปิด linger ให้ด้วยหรือไม่ ขึ้นกับรุ่นของแพ็กเกจ · runbook สั่งทั้งสองทางไว้แล้ว ให้ดูผลจริงใน after.txt
- (security) journald บน Raspberry Pi OS trixie เครื่องนี้เก็บ log ข้ามรอบบูตไหม (/var/log/journal มีไหม) · ถ้าไม่เก็บ T1 ยังวัดได้เพราะจดทีละรอบ แต่หลักฐาน error ของรอบก่อน ๆ ย้อนดูไม่ได้
- (security) รูปคอลัมน์ของ `ss -tunpH state established` บน iproute2 ของ trixie (คาดว่าไม่มีคอลัมน์ State จึง $4 = ฝั่งเครื่อง $5 = ปลายทาง) · runbook ให้ดู 3 บรรทัดก่อนเริ่มตัวเฝ้า
- (security) llama-server build 86ea01d แสดง --no-slots, --no-webui, --chat-template-file และ .sock ใน --help ไหม · section ภาพรวมตรวจให้ ต้องได้ผลก่อนรัน install-llm.sh
- (security) พอร์ต UDP 42198 และ 38670 เป็นของโปรเซสไหน (อาจเป็น avahi หรือ rpcbind/rpc.statd) และจะหายไปหลังปิด rpcbind หรือไม่
- (security) ssh บน Pi 5 ทำงานแบบ ssh.service หรือ ssh.socket · ถ้าเป็น socket การ reload หลังเขียน AllowGroups อาจต่างไป (section ภาพรวมจด is-enabled ของทั้งสองตัวไว้)
- (security) หน้าจอ V2 ลงทะเบียน/สแกนใบหน้าได้ไหมเมื่อบัญชีไม่มีกลุ่ม video/audio (ได้สิทธิ์จาก ACL ของ uaccess อย่างเดียว) · labwc ยังขึ้นไหม · ต้องวัดในขั้น ค1
- (security) ป้ายโมเดลเป็นสีเขียวภายใน 60 วิหลังบูตเย็นไหม · โมเดล 2.5 GB ต้องอ่านจาก microSD ตอน page cache ว่าง อาจเกิน 60 วิ
- (security) Claude Code ติดตั้งผ่าน install.sh บน aarch64 ได้ไหม และตัวเลือกที่ forge ส่ง (เช่น --permission-prompts, --tools "") ยังใช้ได้กับรุ่นที่ติดตั้งบน Pi หรือไม่
- (security) ค่าเริ่มต้น HOME_MODE/DIR_MODE ของ trixie บน Pi 5 (useradd/adduser ได้ 700 หรือไม่) · วัดใน section สมัคร 5 บัญชี
- (data-deploy) ยังไม่รู้ว่า PC ของเจ้าของมี Win32DiskImager และเครื่องอ่านการ์ดหรือไม่ · และการ์ดสำรองมีขนาดเป็นไบต์ ≥ การ์ดหลักไหม (การ์ด 64 GB ต่างยี่ห้อ/ล็อตมักเล็กกว่ากันเล็กน้อย)
- (data-deploy) ยังไม่รู้ว่า `llama-server --version` ของ build 86ea01d พิมพ์ commit แบบ 7 ตัวอักษรหรือไม่ (ต้องดูบนเครื่องจริง)
- (data-deploy) ยังไม่รู้ว่า aipc2030 อยู่กลุ่ม adm ไหม (journalctl -b ไม่ใช้ sudo) · ถ้าไม่อยู่ ให้เติม sudo ใน ~/t10-after.sh และใช้ ssh -t
- (data-deploy) ยังไม่รู้ว่า smoke แบบ offscreen ของ update-app ใช้เวลาเท่าไรบน Pi 5 และ apply ครั้งแรกจบใน 10 นาทีไหม (Pi 4 ไม่ได้จดเวลา)
- (data-deploy) ยังไม่รู้ว่า pip download ตอนออฟไลน์ลองซ้ำนานแค่ไหนก่อนยอมใช้ wheel ที่เก็บไว้
- (data-deploy) ยังไม่รู้ว่า doctor บนการ์ดหลักมีข้อ 'ไม่ผ่าน' อยู่แล้วหรือไม่ (get_throttled = 0xe0000 เคย throttle/soft temp limit)
- (data-deploy) ยังไม่รู้ว่าการดึงปลั๊กภายใน 5 วิหลังเห็น '+ สลับ' ทำได้จริงหรือไม่ เพราะบรรทัดนั้นพิมพ์หลังสลับและเขียน previous แล้ว (update-app.sh:142-144) · ช่วงเสี่ยงจริงคือไม่กี่วิถัดจากนั้นก่อน ext4 commit (ค่าเริ่มต้น 5 วิ)
- (data-deploy) ยังไม่รู้ว่าหน้า Login/เซสชัน labwc ของบัญชีทดสอบเปิดได้ไหมตอนผู้ใช้เหลือพื้นที่ 0 (T13) · ถ้าเข้าไม่ได้ ให้ล้างทาง SSH แล้วบันทึกเป็นข้อค้นพบ
- (data-deploy) MemoryMax=4G ใน aipc-llm.service ยังไม่มีผล (ไม่มี memory controller) · ไม่อยู่ในหมวดนี้ แต่มีผลกับ T13/T10 ถ้า AI กิน RAM จนระบบค้างระหว่างทดสอบ
- (vision-evidence) ยังไม่รู้ว่า sshd บน Pi 5 ยอมให้บัญชีที่สมัครจากหน้า Login เข้าทาง SSH ได้ไหม (T7 และ T12 ต้องใช้) · ถ้าไม่ได้ ต้องใช้ Ctrl+Alt+F2 login เป็นบัญชีนั้นแทน
- (vision-evidence) systemd-run --uid ตั้ง USER/HOME ให้ตามเอกสาร systemd แต่ยังไม่ได้ลองกับ sample-session.sh บน trixie · ถ้าคอลัมน์ pid เป็น '-' ตลอด ให้ตรวจว่าโปรเซสหน้าจอเป็น 'python -m aipc.ui --session' จริง
- (vision-evidence) ชื่อโหนด DRM ของ Pi 5 (card0/card1-HDMI-A-1) และไฟล์ /sys/class/rtc/rtc0/since_epoch ต้องดูบนเครื่องจริง
- (vision-evidence) เส้นทางเมนูในหน้าจอ (ตั้งค่า → ใบหน้าของฉัน) และข้อความ 'AI กำลังเริ่มใหม่' ตรวจจากโค้ดไม่ได้ว่าตรงกับสิ่งที่เห็นบน Pi 5
- (vision-evidence) ความเร็ว 1280×720 MJPG ≥ 15 ภาพ/วิ ของกล้องกับ OpenCV 5.0.0.93 บน Pi 5 ยังไม่รู้จนกว่าจะรัน
- (vision-evidence) อัตราเฟรมจาก 'camera check' ระหว่าง LLM ขึ้นกับความร้อน · พัดลมเกือบเต็มแล้วตอน LLM 4 threads · ผลอาจ throttle จนใช้เป็นระดับ 4 ไม่ได้
- (vision-evidence) llama-bench peak_rss 4866 MB ยังไม่แน่ใจว่าเชื่อได้ และ MemoryMax=4G ไม่มีผลเพราะ cgroup memory ปิด · ไม่อยู่ในหมวดนี้ แต่กระทบการตีความ RAM ตอน LLM + หน้าจอ + ใบหน้าพร้อมกัน
- (vision-evidence) ความหมาย 'ไฮบริด' ของอาจารย์ยังไม่ได้ยืนยันเป็นลายลักษณ์อักษร · เกณฑ์ T6 ช่วง ข ขึ้นกับเรื่องนี้
- (vision-evidence) มี claude บน Pi 5 และ login ไว้หรือยัง · ห้องสอบมีเน็ตไหม · ต้องถามเจ้าของ/อาจารย์
