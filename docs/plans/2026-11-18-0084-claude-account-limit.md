# การ์ด 0084 ใช้ขีดจำกัดของบัญชี Claude · แผนลงมือ

> ทำเองใน session (CLAUDE.md: ไม่ใช้ subagent ถ้า Pakon ไม่สั่ง) · skill `executing-plans` + `test-driven-development` · ช่องติ๊ก `- [ ]`

**เป้าหมาย:** ระบบไม่ตัด Claude ด้วยเพดานของตัวเอง (รายวัน + ต่อครั้ง) · เมื่อบัญชี Claude ใช้ครบ บอกผู้ใช้ตรง ๆ

**แนวทาง:** ตัวจัด "ใช้ครบ" ฟังก์ชันเดียวใน `cloud/ask.py` ใช้ทั้งถาม Claude และสร้างสกิล · ลบ `cloud/budget.py` และทุกที่ที่เรียก ·
จำนวนครั้งต่อวันในหน้าตั้งค่านับจาก ledger

**การ์ด:** [docs/design/0084-claude-account-limit.md](../design/0084-claude-account-limit.md) (อนุมัติ 2026-11-18 · เพดานต่อครั้ง = ลบ)

## ข้อกำหนดรวม

- ข้อความเมื่อใช้ครบ ขึ้นต้นตรงตัว: `บัญชี Claude ใช้ครบโควตาแล้ว · AI ในเครื่องยังใช้ได้ · Claude แจ้งว่า: “…”` · ข้อความ Claude ตัด ≤ 200 ตัวอักษร
- จัดเป็น "ใช้ครบ" เมื่อ `is_error` เป็นจริง **และ** `result` มีคำใดคำหนึ่ง (ไม่สนตัวพิมพ์): `limit` `usage` `quota` `429` · ไม่ดู exit code/subtype
- ไม่ลบ/ไม่แก้ `~/.local/share/aipc/cloud-usage.json` ของผู้ใช้
- ไม่เพิ่ม dependency · ruff ผ่าน · เทสต์ทั้งชุดผ่านบนวินโดวส์ + Pi 5

## จุดที่ต้องระวัง (ไม่มีเทสต์อื่นครอบ)

1. ไม่มีเน็ต / JSON เสีย → ต้องเป็นข้อความเดิม "ติดต่อ Claude ไม่ได้ …" ไม่ใช่ "ใช้ครบ" → เทสต์ใน งาน 1
2. `is_error: false` แต่คำตอบปกติมีคำว่า "limit" (เช่น คำถามเรื่อง speed limit) → ต้องไม่ถูกจัดเป็นใช้ครบ → เทสต์ใน งาน 1
3. การ์ดเชื่อมต่อ/ออกจาก Claude ต้องยังแสดงเมื่อไม่มี budget → เทสต์ใน งาน 2
4. ledger ไม่มี (หน้า Login) → `callsToday` = 0 ไม่ล้ม → เทสต์ใน งาน 2

---

### งาน 1: ตัวจัด "ใช้ครบ" + ลบเพดานต่อครั้ง

**ไฟล์:** แก้ `src/aipc/cloud/ask.py` · `src/aipc/skills/forge.py` · เทสต์ `tests/test_cloud_ask_limit.py` (ใหม่) · แก้ `tests/test_forge.py:85`

**รอยต่อที่งานอื่นใช้:**
- `ask.account_limit_message(data: dict) -> str` · คืนข้อความผู้ใช้ หรือ `""` ถ้าไม่ใช่ใช้ครบ
- `ask.CloudReply.limited: bool = False`
- `forge.Reply.limited: bool = False` · `Reply.error` = ข้อความใช้ครบ เมื่อ limited

- [ ] เขียนเทสต์ (ไม่ผ่านก่อน):
  - `test_rate_limit_payload_is_limited`: `{"is_error": True, "subtype": "success", "result": "API Error: Rate limit reached"}` → ข้อความขึ้นต้น `บัญชี Claude ใช้ครบโควตาแล้ว` และมี `Rate limit reached`
  - `test_out_of_usage_and_429_are_limited`: `"You're out of extra usage"` · `"API Error: 429 …"` → ไม่ว่าง
  - `test_normal_answer_with_word_limit_is_not_limited`: `is_error: False` + `"speed limit 90"` → `""`
  - `test_other_error_is_not_limited`: `is_error: True` + `"Invalid model"` → `""`
  - `test_call_sets_limited_and_message` (ใช้ runner ปลอมของ `ask._call`): payload rate limit → `ok False` · `limited True` · `error` ขึ้นต้นข้อความใช้ครบ · ไม่ใช่ JSON → `limited False` และ error มี "ติดต่อ Claude ไม่ได้"
  - `test_no_per_call_budget_flag`: argv ของ `ask.ask` และ `ask.ask_plain` ไม่มี `--max-budget-usd`
  - `tests/test_forge.py`: เปลี่ยน flag ที่ต้องมีเป็น `("-p", "--no-session-persistence")` + assert ไม่มี `--max-budget-usd` · เพิ่ม `FakeClaude("API Error: Rate limit reached", is_error=True)` → `errors[0]` ขึ้นต้นข้อความใช้ครบ
- [ ] รันให้เห็นไม่ผ่าน: `./.venv/Scripts/python.exe -m unittest tests.test_cloud_ask_limit tests.test_forge -v`
- [ ] เขียนโค้ด: `account_limit_message` · `_call` ใช้ก่อนสร้างข้อความ error เดิม · `forge.ask_claude` เหมือนกัน · ลบ `BUDGET_USD` และ `--max-budget-usd` ทั้ง 3 จุด (`ask.py:158,212` · `forge.py:71`)
- [ ] รันผ่าน + ruff
- [ ] commit `feat(0084): บอกผู้ใช้ตรง ๆ เมื่อบัญชี Claude ใช้ครบ · ลบเพดานต่อครั้ง --max-budget-usd`

### งาน 2: ลบเพดานรายวัน

**ไฟล์:** ลบ `src/aipc/cloud/budget.py` · `tests/test_cloud_budget.py` · แก้ `src/aipc/ui/app.py` (`_cloud_client` · `_skill_forge` · ส่วนสร้าง `budget` ~บรรทัด 287–295 · `CloudUsage(` ~384) · `src/aipc/ui/backend.py` `CloudUsage` · `src/aipc/ui/qml/AipcUi/SettingsPage.qml` ~600–705 · `src/aipc/i18n/en.json` (คีย์ที่ไม่ใช้แล้ว) · `src/aipc/spikes/hybrid_eval.py` · `src/aipc/spikes/skill_intent_eval.py` · `src/aipc/spikes/settings_shots.py` · `tests/test_ui_qml.py`

**รอยต่อ:**
- `_cloud_client(ledger=None)` · `_skill_forge(ledger=None)` (ตัด `budget`)
- `CloudUsage(available: bool = False, poll_ms=…, ledger=None, …)` · `available` = ค่าที่ส่งมาตรง ๆ · `callsToday` = จำนวนรายการ ledger ที่ `time` ขึ้นต้นด้วยวันที่วันนี้ · ลบ `spentToday` `limit` `limits` `levels` `usedPercent` `setLimit`

- [ ] เขียนเทสต์ (ไม่ผ่านก่อน) ใน `tests/test_ui_qml.py` แทน `test_claude_daily_level_without_money`:
  - `test_claude_card_has_no_daily_limit`: ไม่มี item `cloudLevel_*` และ `cloudLevelText` · การ์ด `cloudUsageCard` แสดง · `callsToday` = จำนวนรายการ ledger วันนี้ (บันทึก 2 รายการวันนี้ + 1 เมื่อวาน → 2)
  - `test_old_usage_file_is_left_alone`: เขียน `cloud-usage.json` ใน `XDG_DATA_HOME` ก่อนเปิดหน้าตั้งค่า → หลังเปิด เนื้อหา byte เท่าเดิม
  - `test_calls_today_without_ledger_is_zero`: `CloudUsage(available=True)` → `callsToday == 0`
  - แก้ `test_outbound_card_lists_what_left_the_machine`: ไม่ import `Budget`
  - เทสต์ app: `_cloud_client` / `_skill_forge` เรียกได้หลายครั้งเกิน "$5" ไม่ถูกตัด (Claude ปลอมรายงาน `total_cost_usd` 3.0 ต่อครั้ง × 3 ครั้ง → ok ทั้ง 3) — C1
- [ ] รันให้เห็นไม่ผ่าน: `./.venv/Scripts/python.exe -m unittest tests.test_ui_qml -k claude -k usage -v`
- [ ] เขียนโค้ด/ลบตามรายการไฟล์ · QML: ลบแถบ % ปุ่มระดับ และป้าย "ครบวันนี้แล้ว" · ข้อความเหลือ `วันนี้ถาม Claude ไป N ครั้ง`
- [ ] `grep -rn "budget" src tests` เหลือแค่ `budget_tokens` ของ `chat/client.py`
- [ ] รันเทสต์ทั้งชุดบนวินโดวส์ + ruff
- [ ] commit `feat(0084): ลบเพดานรายวันของระบบ · หน้าตั้งค่านับครั้งจาก ledger · ไม่แตะไฟล์ใช้งานเดิมของผู้ใช้`

### งาน 3: เอกสาร + Pi

**ไฟล์:** `docs/design/0084-claude-account-limit.md` (หัวข้อ 10 คำตอบ Pakon + ความคืบหน้า + ผลเทสต์) · `docs/ARCHITECTURE.md` ถ้ามีส่วน budget (`grep -n "budget\|เพดาน" docs/ARCHITECTURE.md`) · การ์ด 0016/0017 เพิ่มบรรทัด "เพดานรายวันถูกลบโดยการ์ด 0084" (ข้อเท็จจริงอยู่ที่เดียว)

- [ ] แก้เอกสาร
- [ ] ส่งสาขาขึ้น Pi (`pi-deploy` ขั้น 1 · worktree แยก) · รันเทสต์ทั้งชุดด้วย venv ของ `/opt/aipc-v2` · บันทึกตัวเลข
- [ ] commit `docs(0084): ผลเทสต์วินโดวส์ + Pi 5`
- [ ] C3 ดูที่จอ = นัด 2026-11-23 · ไม่รวม master จนกว่า Pakon อนุมัติ (กฎเหล็กข้อ 2)
