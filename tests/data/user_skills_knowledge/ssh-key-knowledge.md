---
id: ssh-key-knowledge
name: SSH key กับรหัสผ่าน
description: ตอบว่า SSH key ต่างจากรหัสผ่านอย่างไรและทำไมปลอดภัยกว่า · ไม่ตั้งค่าเซิร์ฟเวอร์ให้ ไม่แก้ปัญหาล็อกอินจริง ไม่ใช่ key ของ GPG หรือ HTTPS
keywords: SSH key, ssh-keygen, กุญแจ SSH, ล็อกอิน SSH, private key, public key, ssh รหัสผ่าน
examples:
  - SSH key ต่างจากรหัสผ่านยังไง
  - ทำไม SSH key ปลอดภัยกว่ารหัสผ่าน
  - ใช้ key แทนรหัสผ่านตอน ssh ดีกว่าจริงไหม
  - private key กับ public key ของ ssh คืออะไร
  - ทำไมเขาแนะนำให้ปิดล็อกอิน ssh ด้วยรหัสผ่าน
  - สร้าง ssh key ยังไง
version: 1.0
kind: knowledge
worker: llm
needs: llm
learned: 2026-10-21
author: Claude (พี่ใหญ่) · claude-sonnet-5-5
generator: claude -p · 2.1.302 (Claude Code)
created: 2026-10-21
request: สร้าง “สกิลความรู้” ให้ AI ในเครื่อง (โมเดลเล็ก ไม่มีเน็ต) ตอบเรื่องนี้เองครั้งหน้า · คำถามของผู้ใช้: “SSH key ต่างจากการใช้รหัสผ่านยังไง ทำไมปลอดภัยกว่า” · คำตอบที่คุณตอบไว้เมื่อ 2026-10-21: “**ความต
---
## คำสั่งให้ AI
- รหัสผ่าน: ความลับที่พิมพ์ส่งให้เซิร์ฟเวอร์ตรวจ
- SSH key: คู่กุญแจ private key อยู่ในเครื่องเรา ไม่ส่งออก / public key วางบนเซิร์ฟเวอร์ (~/.ssh/authorized_keys) เซิร์ฟเวอร์ส่งโจทย์ เครื่องเราเซ็นตอบด้วย private key
ปลอดภัยกว่า:
1. เดายากกว่ามาก (เช่น Ed25519) รหัสผ่านคนมักสั้นหรือซ้ำ
2. brute-force/credential stuffing ไม่ได้ผล
3. ไม่มีความลับส่งผ่านเครือข่าย เซิร์ฟเวอร์ถูกเจาะก็ได้แค่ public key
4. กันฟิชชิง เพราะไม่มีรหัสให้พิมพ์
5. ปิดล็อกอินรหัสผ่านได้ (PasswordAuthentication no)
ระวัง: private key หลุด = เข้าได้ ตั้ง passphrase ห้ามแชร์ ถ้าหลุดให้ลบ public key ออกจากเซิร์ฟเวอร์
สร้าง: ssh-keygen -t ed25519 · ส่ง: ssh-copy-id user@host
