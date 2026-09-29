---
id: system-command
name: สั่งงานเครื่อง
description: เปิดแอป เปิดเว็บที่กำหนด เปิดหน้าในระบบ และปรับเสียง
examples:
  - เปิดยูทูบ
  - ปรับเสียงสี่สิบ
  - เปิดหน้าตั้งค่า
worker: code
actions: open_url, open_app, open_page, set_volume, change_volume, mute, unmute
permissions: run_actions
version: 1.0
author: ระบบ
---
# สั่งงานเครื่อง (สกิล 4)

ทำงานด้วยโค้ด ไม่ผ่าน LLM: ตัวแปลคำสั่งแบบกฎใน `command.py` แปลประโยคเป็น Action ที่อนุญาต (`actions.py`)
ชื่อไม่ตรงเป๊ะ = ถามก่อน · ตัวคัดสกิลลองสกิลนี้ก่อนสกิลอื่นเสมอ จึงไม่มีคำสำคัญ (keywords)
